from datetime import date, datetime, timedelta
from unittest import mock

from django.test import SimpleTestCase
from django.utils import timezone

from festival.models import Edition, Poll, VotePeriod
from festival.templatetags.festival_display import (
    datetime_label,
    edition_dates,
    poll_window,
    relative_phrase,
    vote_allowance,
)

NO_BREAK_SPACE = chr(0xA0)
NOW = timezone.make_aware(datetime(2026, 10, 23, 10, 0))


class RelativePhraseTests(SimpleTestCase):
    def test_phrases(self):
        cases = [
            (timedelta(days=1), "mañana"),
            (timedelta(days=2), "pasado mañana"),
            (timedelta(days=9), "en 9 días"),
            (timedelta(days=-3), "hace 3 días"),
            (timedelta(hours=3), "en 3 horas"),
            (timedelta(minutes=1), "en 1 minuto"),
            (timedelta(seconds=10), "ahora"),
        ]
        for offset, expected in cases:
            with self.subTest(offset=offset):
                self.assertEqual(relative_phrase(NOW + offset, NOW), expected)


@mock.patch("festival.templatetags.festival_display.timezone.now", return_value=NOW)
class PollWindowTests(SimpleTestCase):
    def poll(self, **values):
        defaults = {
            "opens_at": NOW - timedelta(days=2),
            "closes_at": NOW + timedelta(days=9),
            "is_published": True,
        }
        return Poll(**{**defaults, **values})

    def test_open_poll_says_when_it_closes(self, _now):
        self.assertEqual(poll_window(self.poll()), "Cierra en 9 días")

    def test_upcoming_poll_says_when_it_opens(self, _now):
        poll = self.poll(opens_at=NOW + timedelta(days=4), closes_at=NOW + timedelta(days=8))
        self.assertEqual(poll_window(poll), "Abre en 4 días")

    def test_closed_poll_shows_the_closing_date_in_bogota_time(self, _now):
        poll = self.poll(opens_at=NOW - timedelta(days=9), closes_at=NOW - timedelta(days=1))
        self.assertEqual(
            poll_window(poll), f"Cerró el 22 de octubre, 10:00{NO_BREAK_SPACE}a.{NO_BREAK_SPACE}m."
        )

    def test_poll_closed_early(self, _now):
        self.assertEqual(poll_window(self.poll(closed_early=True)), "Cerrada antes de tiempo")


class LabelTests(SimpleTestCase):
    def test_datetime_label_uses_lowercase_months(self):
        evening = timezone.make_aware(datetime(2026, 11, 1, 20, 0))
        self.assertEqual(
            datetime_label(evening), f"1 de noviembre, 8:00{NO_BREAK_SPACE}p.{NO_BREAK_SPACE}m."
        )

    def test_edition_dates_within_one_year(self):
        edition = Edition(starts_on=date(2027, 4, 28), ends_on=date(2027, 5, 1))
        self.assertEqual(edition_dates(edition), "del 28 de abril al 1 de mayo de 2027")

    def test_edition_dates_across_years(self):
        edition = Edition(starts_on=date(2027, 12, 30), ends_on=date(2028, 1, 2))
        self.assertEqual(
            edition_dates(edition), "del 30 de diciembre de 2027 al 2 de enero de 2028"
        )

    def test_vote_allowance(self):
        self.assertEqual(vote_allowance(Poll(votes_per_voter=1)), "1 voto en total")
        self.assertEqual(
            vote_allowance(Poll(votes_per_voter=3, vote_period=VotePeriod.DAY)), "3 votos por día"
        )
