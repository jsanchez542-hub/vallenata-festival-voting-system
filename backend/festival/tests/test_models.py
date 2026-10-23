from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from festival.models import Edition, Poll, PollStatus, sorted_for_listing

from .builders import create_category, create_edition, create_poll


class PollStatusTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = create_category(create_edition())

    def test_unpublished_poll_is_a_draft(self):
        poll = create_poll(self.category, is_published=False)
        self.assertEqual(poll.status, PollStatus.DRAFT)

    def test_status_follows_the_voting_window(self):
        poll = create_poll(self.category)
        self.assertEqual(poll.status_at(poll.opens_at - timedelta(seconds=1)), PollStatus.UPCOMING)
        self.assertEqual(poll.status_at(poll.opens_at), PollStatus.OPEN)
        self.assertEqual(poll.status_at(poll.closes_at), PollStatus.CLOSED)

    def test_closing_early_overrides_the_closing_date(self):
        poll = create_poll(self.category, closed_early=True)
        self.assertEqual(poll.status, PollStatus.CLOSED)


class PollQuerySetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = create_category(create_edition())
        cls.open_poll = create_poll(category)
        cls.upcoming_poll = create_poll(
            category, opens_in=timedelta(days=2), closes_in=timedelta(days=4)
        )
        cls.closed_poll = create_poll(
            category, opens_in=timedelta(days=-5), closes_in=timedelta(days=-1)
        )
        cls.closed_early_poll = create_poll(category, closed_early=True)
        cls.draft_poll = create_poll(category, is_published=False)
        hidden_category = create_category(category.edition, is_active=False)
        cls.poll_in_hidden_category = create_poll(hidden_category)

    def test_status_filters_match_the_status_property(self):
        for status in (PollStatus.OPEN, PollStatus.UPCOMING, PollStatus.CLOSED):
            with self.subTest(status=status):
                filtered = set(Poll.objects.in_status(status))
                expected = {poll for poll in Poll.objects.all() if poll.status == status}
                self.assertEqual(filtered, expected)

    def test_published_excludes_drafts_and_inactive_categories(self):
        published = set(Poll.objects.published())
        self.assertNotIn(self.draft_poll, published)
        self.assertNotIn(self.poll_in_hidden_category, published)
        self.assertIn(self.open_poll, published)

    def test_listing_puts_open_polls_first_and_closed_polls_last(self):
        polls = sorted_for_listing(Poll.objects.published())
        self.assertEqual(polls[0], self.open_poll)
        self.assertEqual(polls[1], self.upcoming_poll)
        self.assertEqual(set(polls[2:]), {self.closed_poll, self.closed_early_poll})


class ConstraintTests(TestCase):
    def test_poll_cannot_close_before_it_opens(self):
        category = create_category(create_edition())
        poll = Poll(
            category=category,
            title="Fechas al revés",
            slug="fechas-al-reves",
            opens_at=timezone.now(),
            closes_at=timezone.now() - timedelta(hours=1),
        )
        with self.assertRaisesMessage(
            ValidationError, "La fecha de cierre debe ser posterior a la de apertura."
        ):
            poll.full_clean()
        with self.assertRaises(IntegrityError), transaction.atomic():
            poll.save()

    def test_edition_cannot_end_before_it_starts(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_edition(starts_on=date(2027, 5, 1), ends_on=date(2027, 4, 28))

    def test_category_names_are_unique_within_an_edition(self):
        edition = create_edition()
        create_category(edition, name="Música")
        create_category(create_edition(number=61), name="Música")
        with self.assertRaises(IntegrityError), transaction.atomic():
            create_category(edition, name="Música")


class CurrentEditionTests(TestCase):
    def test_current_edition_is_the_next_one_to_finish(self):
        create_edition(number=59)
        upcoming = create_edition(number=60)
        create_edition(number=61)
        self.assertEqual(Edition.objects.current(today=date(2027, 1, 15)), upcoming)

    def test_falls_back_to_the_latest_edition_when_all_have_ended(self):
        create_edition(number=59)
        latest = create_edition(number=60)
        self.assertEqual(Edition.objects.current(today=date(2030, 1, 1)), latest)

    def test_there_is_no_current_edition_without_editions(self):
        self.assertIsNone(Edition.objects.current())
