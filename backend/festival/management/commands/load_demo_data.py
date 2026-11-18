from datetime import date, datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from festival.models import Category, Edition, Option, Poll, ResultsVisibility, Vote, new_receipt

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
        "sample_votes": [13, 10, 7, 4],
    },
    {
        "category": "Música",
        "title": "Agrupación favorita del público",
        "slug": "agrupacion-favorita-del-publico",
        "description": "Escoge la agrupación que más disfrutaste durante el Festival.",
        "opens_in_days": -1,
        "closes_in_days": 6,
        "results_visibility": ResultsVisibility.LIVE,
        "options": [
            ("Conjunto A", "Categoría profesional"),
            ("Conjunto B", "Categoría aficionado"),
            ("Conjunto C", "Categoría juvenil"),
            ("Conjunto D", "Categoría infantil"),
        ],
        "sample_votes": [21, 19, 10, 6],
    },
    {
        "category": "Piloneras y vestuario",
        "title": "Vestuario más destacado",
        "slug": "vestuario-mas-destacado",
        "description": (
            "Escoge el vestuario que más te llamó la atención en el Desfile de Piloneras."
        ),
        "opens_in_days": -1,
        "closes_in_days": 8,
        "options": [
            ("Vestuario A", "Piloneras mayores"),
            ("Vestuario B", "Piloneras juveniles"),
            ("Vestuario C", "Piloneras infantiles"),
        ],
    },
    {
        "category": "Piloneras y vestuario",
        "title": "Comparsa favorita del desfile",
        "slug": "comparsa-favorita-del-desfile",
        "description": "Escoge la comparsa que mejor bailó en el Desfile de Piloneras.",
        "opens_in_days": 4,
        "closes_in_days": 12,
        "options": [
            ("Comparsa A", "Grupo de adultos"),
            ("Comparsa B", "Grupo juvenil"),
            ("Comparsa C", "Grupo infantil"),
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
        "sample_votes": [32, 27, 15],
    },
]


# Sample votes are a tenth of the prototype's, so the results keep its proportions. They come
# from accounts without a usable password, so nobody can sign in with them.
SAMPLE_VOTER_EMAIL = "votante.ejemplo.{:03d}@ejemplo.invalid"
SAMPLE_VOTER_NAME = "Votante de ejemplo"


def at_hour(day, hour):
    return timezone.make_aware(datetime.combine(day, time(hour)))


def sample_voters(first, last):
    voter_model = get_user_model()
    emails = [SAMPLE_VOTER_EMAIL.format(number) for number in range(first, last + 1)]
    existing = set(voter_model.objects.filter(email__in=emails).values_list("email", flat=True))
    missing = []
    for email in emails:
        if email not in existing:
            voter = voter_model(email=email, first_name=SAMPLE_VOTER_NAME)
            voter.set_unusable_password()
            missing.append(voter)
    voter_model.objects.bulk_create(missing)
    by_email = {voter.email: voter for voter in voter_model.objects.filter(email__in=emails)}
    return [by_email[email] for email in emails]


def cast_sample_votes(poll, options, counts, first_voter, now):
    category = poll.category
    total = sum(counts)
    voters = sample_voters(first_voter, first_voter + total - 1)
    ballots = [option for option, count in zip(options, counts, strict=True) for _ in range(count)]
    voted = set(Vote.objects.filter(category=category).values_list("voter_id", flat=True))
    step = (min(poll.closes_at, now) - poll.opens_at) / (total + 1)
    votes = [
        Vote(
            voter=voter,
            edition_id=category.edition_id,
            category=category,
            option=option,
            receipt=new_receipt(),
            cast_at=poll.opens_at + step * position,
        )
        for position, (voter, option) in enumerate(zip(voters, ballots, strict=True), start=1)
        if voter.pk not in voted
    ]
    Vote.objects.bulk_create(votes)
    return len(votes)


class Command(BaseCommand):
    help = (
        "Loads the 60th edition with the prototype's sample categories, polls, options and votes. "
        "Poll dates are relative to today, so running it again keeps the same mix of open, "
        "upcoming and closed polls."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        today = timezone.localdate()
        edition, _ = Edition.objects.update_or_create(year=EDITION["year"], defaults=EDITION)
        categories = {}
        for position, (name, description) in enumerate(CATEGORIES, start=1):
            categories[name], _ = Category.objects.update_or_create(
                edition=edition,
                name=name,
                defaults={"description": description, "position": position, "is_active": True},
            )
        next_voter = {}
        cast = 0
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
                    "results_visibility": spec.get(
                        "results_visibility", ResultsVisibility.AFTER_CLOSE
                    ),
                },
            )
            poll_options = [
                Option.objects.update_or_create(
                    poll=poll, name=name, defaults={"detail": detail, "position": position}
                )[0]
                for position, (name, detail) in enumerate(spec["options"], start=1)
            ]
            counts = spec.get("sample_votes")
            if counts:
                # Each category needs its own voters for every poll, because of the voting rule.
                first_voter = next_voter.get(poll.category_id, 1)
                next_voter[poll.category_id] = first_voter + sum(counts)
                cast += cast_sample_votes(poll, poll_options, counts, first_voter, now)
        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {edition}: {len(CATEGORIES)} categories, {len(POLLS)} polls "
                f"and {cast} new sample votes."
            )
        )
