from datetime import date, timedelta
from itertools import count

from django.utils import timezone

from festival.models import Category, Edition, Option, Poll

_sequence = count(1)


def create_edition(**overrides):
    number = overrides.pop("number", 60)
    year = overrides.pop("year", 1967 + number)
    values = {
        "starts_on": date(year, 4, 28),
        "ends_on": date(year, 5, 1),
        **overrides,
    }
    return Edition.objects.create(number=number, year=year, **values)


def create_category(edition, **overrides):
    values = {"name": f"Categoría {next(_sequence)}", "description": "", **overrides}
    return Category.objects.create(edition=edition, **values)


def create_poll(category, opens_in=timedelta(days=-1), closes_in=timedelta(days=5), **overrides):
    now = timezone.now()
    serial = next(_sequence)
    values = {
        "title": f"Votación {serial}",
        "slug": f"votacion-{serial}",
        "opens_at": now + opens_in,
        "closes_at": now + closes_in,
        "is_published": True,
        **overrides,
    }
    return Poll.objects.create(category=category, **values)


def add_options(poll, *names):
    return [
        Option.objects.create(poll=poll, name=name, position=position)
        for position, name in enumerate(names, start=1)
    ]
