from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, F, Q
from django.urls import reverse
from django.utils import timezone

MIN_OPTIONS_TO_PUBLISH = 2


class PollStatus(models.TextChoices):
    DRAFT = "draft", "Borrador"
    UPCOMING = "upcoming", "Próxima"
    OPEN = "open", "Abierta"
    CLOSED = "closed", "Cerrada"


class VotePeriod(models.TextChoices):
    TOTAL = "total", "En total"
    DAY = "day", "Por día"


class ResultsVisibility(models.TextChoices):
    HIDDEN = "hidden", "Solo la organización"
    AFTER_CLOSE = "after_close", "Al cierre de la votación"
    LIVE = "live", "En vivo"


def open_condition(now, prefix=""):
    return Q(
        **{
            f"{prefix}is_published": True,
            f"{prefix}closed_early": False,
            f"{prefix}opens_at__lte": now,
            f"{prefix}closes_at__gt": now,
        }
    )


class EditionQuerySet(models.QuerySet):
    def current(self, today=None):
        today = today or timezone.localdate()
        upcoming = self.filter(ends_on__gte=today).order_by("ends_on").first()
        return upcoming or self.order_by("-ends_on").first()


class Edition(models.Model):
    number = models.PositiveSmallIntegerField("número", unique=True)
    year = models.PositiveSmallIntegerField("año", unique=True)
    name = models.CharField("nombre", max_length=120, default="Festival de la Leyenda Vallenata")
    city = models.CharField("ciudad", max_length=80, default="Valledupar")
    starts_on = models.DateField("empieza el")
    ends_on = models.DateField("termina el")

    objects = EditionQuerySet.as_manager()

    class Meta:
        verbose_name = "edición"
        verbose_name_plural = "ediciones"
        ordering = ["-year"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__gte=F("starts_on")),
                name="edition_ends_after_it_starts",
                violation_error_message="La edición no puede terminar antes de empezar.",
            ),
        ]

    def __str__(self):
        return f"{self.number} {self.name} ({self.year})"

    def get_absolute_url(self):
        return reverse("festival:edition-detail", args=[self.year])

    @property
    def short_name(self):
        return f"Edición {self.number}"


class CategoryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def with_poll_counts(self, now=None):
        now = now or timezone.now()
        return self.annotate(
            poll_count=Count("polls", filter=Q(polls__is_published=True)),
            open_poll_count=Count("polls", filter=open_condition(now, prefix="polls__")),
        )


class Category(models.Model):
    edition = models.ForeignKey(
        Edition, models.PROTECT, related_name="categories", verbose_name="edición"
    )
    name = models.CharField("nombre", max_length=80)
    description = models.CharField("descripción", max_length=200, blank=True)
    position = models.PositiveSmallIntegerField("orden", default=1)
    is_active = models.BooleanField(
        "activa", default=True, help_text="Las categorías inactivas no se muestran en el sitio."
    )

    objects = CategoryQuerySet.as_manager()

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["position", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["edition", "name"],
                name="unique_category_name_per_edition",
                violation_error_message="Esta edición ya tiene una categoría con ese nombre.",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.edition.year})"

    def get_absolute_url(self):
        return reverse("festival:category-detail", args=[self.pk])


class PollQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, category__is_active=True)

    def open(self, now=None):
        return self.filter(open_condition(now or timezone.now()))

    def upcoming(self, now=None):
        return self.filter(
            is_published=True, closed_early=False, opens_at__gt=now or timezone.now()
        )

    def closed(self, now=None):
        ended = Q(closed_early=True) | Q(closes_at__lte=now or timezone.now())
        return self.filter(ended, is_published=True)

    def in_status(self, status, now=None):
        filters = {
            PollStatus.OPEN: self.open,
            PollStatus.UPCOMING: self.upcoming,
            PollStatus.CLOSED: self.closed,
        }
        return filters[status](now)

    def for_listing(self):
        return self.select_related("category__edition").annotate(option_count=Count("options"))


class Poll(models.Model):
    category = models.ForeignKey(
        Category, models.PROTECT, related_name="polls", verbose_name="categoría"
    )
    title = models.CharField("título", max_length=120)
    slug = models.SlugField(
        "dirección",
        max_length=140,
        unique=True,
        help_text="Final de la dirección web de la votación. Se completa a partir del título.",
    )
    description = models.CharField("descripción", max_length=300, blank=True)
    opens_at = models.DateTimeField("abre el")
    closes_at = models.DateTimeField("cierra el")
    is_published = models.BooleanField(
        "publicada",
        default=False,
        help_text=f"Para publicarla necesita al menos {MIN_OPTIONS_TO_PUBLISH} opciones.",
    )
    closed_early = models.BooleanField(
        "cerrada antes de tiempo",
        default=False,
        help_text="Cierra la votación aunque no haya llegado la fecha de cierre.",
    )
    votes_per_voter = models.PositiveSmallIntegerField(
        "votos por persona", default=1, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    vote_period = models.CharField(
        "periodo de los votos", max_length=10, choices=VotePeriod, default=VotePeriod.TOTAL
    )
    results_visibility = models.CharField(
        "resultados visibles",
        max_length=12,
        choices=ResultsVisibility,
        default=ResultsVisibility.AFTER_CLOSE,
    )
    requires_account = models.BooleanField("exige cuenta para votar", default=True)

    objects = PollQuerySet.as_manager()

    class Meta:
        verbose_name = "votación"
        verbose_name_plural = "votaciones"
        ordering = ["opens_at", "title"]
        constraints = [
            models.CheckConstraint(
                condition=Q(closes_at__gt=F("opens_at")),
                name="poll_closes_after_it_opens",
                violation_error_message="La fecha de cierre debe ser posterior a la de apertura.",
            ),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("festival:poll-detail", args=[self.slug])

    @property
    def status(self):
        return self.status_at(timezone.now())

    def status_at(self, moment):
        if not self.is_published:
            return PollStatus.DRAFT
        if self.closed_early or moment >= self.closes_at:
            return PollStatus.CLOSED
        if moment < self.opens_at:
            return PollStatus.UPCOMING
        return PollStatus.OPEN


class Option(models.Model):
    poll = models.ForeignKey(Poll, models.CASCADE, related_name="options", verbose_name="votación")
    name = models.CharField("nombre", max_length=120)
    detail = models.CharField(
        "detalle",
        max_length=160,
        blank=True,
        help_text="Dato corto para reconocer la opción, por ejemplo el aire o la categoría.",
    )
    position = models.PositiveSmallIntegerField("orden", default=1)

    class Meta:
        verbose_name = "opción"
        verbose_name_plural = "opciones"
        ordering = ["position", "pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "name"],
                name="unique_option_name_per_poll",
                violation_error_message="Esta votación ya tiene una opción con ese nombre.",
            ),
        ]

    def __str__(self):
        return self.name


STATUS_RANK = {
    PollStatus.OPEN: 0,
    PollStatus.UPCOMING: 1,
    PollStatus.DRAFT: 2,
    PollStatus.CLOSED: 3,
}


def sorted_for_listing(polls, now=None):
    now = now or timezone.now()

    def listing_key(poll):
        status = poll.status_at(now)
        if status == PollStatus.UPCOMING:
            return STATUS_RANK[status], poll.opens_at.timestamp()
        if status == PollStatus.CLOSED:
            return STATUS_RANK[status], -poll.closes_at.timestamp()
        return STATUS_RANK[status], poll.closes_at.timestamp()

    return sorted(polls, key=listing_key)
