from datetime import date, datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from festival.models import Category, Edition, Option, Poll, ResultsVisibility, VotePeriod

EDITION = {
    "number": 60,
    "year": 2027,
    "name": "Festival de la Leyenda Vallenata",
    "city": "Valledupar",
    "starts_on": date(2027, 4, 28),
    "ends_on": date(2027, 5, 1),
}

CATEGORIES = [
    ("Música", "Canciones y agrupaciones de la edición."),
    ("Piloneras y vestuario", "Presentaciones de baile y su vestuario."),
    ("Presentaciones", "Momentos destacados de las tarimas."),
]

POLLS = [
    {
        "category": "Música",
        "title": "Canción favorita del público",
        "slug": "cancion-favorita-del-publico",
        "description": "Escoge la canción que más te gustó de las presentadas en tarima.",
        "opens_in_days": -2,
        "closes_in_days": 9,
        "options": [
            ("Canción A", "Aire: paseo"),
            ("Canción B", "Aire: merengue"),
            ("Canción C", "Aire: son"),
            ("Canción D", "Aire: puya"),
        ],
    },
    {
        "category": "Música",
        "title": "Agrupación favorita del público",
        "slug": "agrupacion-favorita-del-publico",
        "description": "Escoge la agrupación que más disfrutaste durante el Festival.",
        "opens_in_days": -1,
        "closes_in_days": 6,
        "votes_per_voter": 3,
        "vote_period": VotePeriod.DAY,
        "results_visibility": ResultsVisibility.LIVE,
        "options": [
            ("Conjunto A", "Categoría profesional"),
            ("Conjunto B", "Categoría aficionado"),
            ("Conjunto C", "Categoría juvenil"),
            ("Conjunto D", "Categoría infantil"),
        ],
    },
    {
        "category": "Piloneras y vestuario",
        "title": "Vestuario más destacado",
        "slug": "vestuario-mas-destacado",
        "description": (
            "Escoge el vestuario que más te llamó la atención en el Desfile de Piloneras."
        ),
        "opens_in_days": 4,
        "closes_in_days": 12,
        "options": [
            ("Vestuario A", "Piloneras mayores"),
            ("Vestuario B", "Piloneras juveniles"),
            ("Vestuario C", "Piloneras infantiles"),
        ],
    },
    {
        "category": "Presentaciones",
        "title": "Presentación más recordada",
        "slug": "presentacion-mas-recordada",
        "description": "Escoge la presentación que más recuerdas de esta edición.",
        "opens_in_days": -12,
        "closes_in_days": -1,
        "options": [
            ("Presentación A", "Tarima Francisco el Hombre"),
            ("Presentación B", "Parque de la Leyenda Vallenata"),
            ("Presentación C", "Plaza Alfonso López"),
        ],
    },
]


def at_hour(day, hour):
    return timezone.make_aware(datetime.combine(day, time(hour)))


class Command(BaseCommand):
    help = (
        "Loads the 60th edition with the prototype's sample categories, polls and options. "
        "Poll dates are relative to today, so running it again keeps the same mix of open, "
        "upcoming and closed polls."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        edition, _ = Edition.objects.update_or_create(year=EDITION["year"], defaults=EDITION)
        categories = {}
        for position, (name, description) in enumerate(CATEGORIES, start=1):
            categories[name], _ = Category.objects.update_or_create(
                edition=edition,
                name=name,
                defaults={"description": description, "position": position, "is_active": True},
            )
        for spec in POLLS:
            poll, _ = Poll.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "category": categories[spec["category"]],
                    "title": spec["title"],
                    "description": spec["description"],
                    "opens_at": at_hour(today + timedelta(days=spec["opens_in_days"]), 8),
                    "closes_at": at_hour(today + timedelta(days=spec["closes_in_days"]), 20),
                    "is_published": True,
                    "closed_early": False,
                    "votes_per_voter": spec.get("votes_per_voter", 1),
                    "vote_period": spec.get("vote_period", VotePeriod.TOTAL),
                    "results_visibility": spec.get(
                        "results_visibility", ResultsVisibility.AFTER_CLOSE
                    ),
                    "requires_account": True,
                },
            )
            for position, (name, detail) in enumerate(spec["options"], start=1):
                Option.objects.update_or_create(
                    poll=poll, name=name, defaults={"detail": detail, "position": position}
                )
        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {edition}: {len(CATEGORIES)} categories and {len(POLLS)} polls."
            )
        )
