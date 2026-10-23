import math
import re

from django import template
from django.utils import timezone
from django.utils.formats import date_format

from festival.models import PollStatus, VotePeriod

register = template.Library()

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR
NAMED_DAYS = {-2: "anteayer", -1: "ayer", 0: "hoy", 1: "mañana", 2: "pasado mañana"}
NO_BREAK_SPACE = chr(0xA0)
MERIDIEM_SPACES = re.compile(r"\s([ap])\.\s?m\.")


def counted(amount, singular, plural):
    return f"{amount} {singular if amount == 1 else plural}"


def relative_phrase(moment, now):
    seconds = (moment - now).total_seconds()
    distance = abs(seconds)
    if distance >= DAY:
        days = math.floor(seconds / DAY + 0.5)
        if days in NAMED_DAYS:
            return NAMED_DAYS[days]
        amount, singular, plural = abs(days), "día", "días"
    elif distance >= HOUR:
        amount, singular, plural = math.floor(distance / HOUR + 0.5), "hora", "horas"
    else:
        amount, singular, plural = math.floor(distance / MINUTE + 0.5), "minuto", "minutos"
        if amount == 0:
            return "ahora"
    text = counted(amount, singular, plural)
    return f"en {text}" if seconds > 0 else f"hace {text}"


def spanish_date(value, pattern):
    # Django's Spanish catalog capitalizes month names, but Spanish writes them in lowercase.
    return date_format(value, pattern).lower()


@register.filter
def datetime_label(moment):
    text = spanish_date(timezone.localtime(moment), r"j \d\e F, g:i a")
    return MERIDIEM_SPACES.sub(rf"{NO_BREAK_SPACE}\1.{NO_BREAK_SPACE}m.", text)


@register.filter
def poll_window(poll):
    now = timezone.now()
    status = poll.status_at(now)
    if status == PollStatus.OPEN:
        return f"Cierra {relative_phrase(poll.closes_at, now)}"
    if status == PollStatus.UPCOMING:
        return f"Abre {relative_phrase(poll.opens_at, now)}"
    if status == PollStatus.CLOSED and poll.closed_early:
        return "Cerrada antes de tiempo"
    if status == PollStatus.CLOSED:
        return f"Cerró el {datetime_label(poll.closes_at)}"
    return "Sin publicar"


@register.filter
def vote_allowance(poll):
    period = "en total" if poll.vote_period == VotePeriod.TOTAL else "por día"
    return f"{counted(poll.votes_per_voter, 'voto', 'votos')} {period}"


@register.filter
def edition_dates(edition):
    end = spanish_date(edition.ends_on, r"j \d\e F \d\e Y")
    if edition.starts_on.year == edition.ends_on.year:
        start = spanish_date(edition.starts_on, r"j \d\e F")
    else:
        start = spanish_date(edition.starts_on, r"j \d\e F \d\e Y")
    return f"del {start} al {end}"
