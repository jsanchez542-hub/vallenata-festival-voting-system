from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from festival.models import ResultsVisibility, Vote
from festival.templatetags.festival_display import count_label, percent_label, votes_label

from .builders import (
    CLOSED_WINDOW,
    add_options,
    cast_votes,
    create_category,
    create_edition,
    create_poll,
    create_voter,
)

UPCOMING = {"opens_in": timedelta(days=2), "closes_in": timedelta(days=9)}


def create_staff(email="organizacion@ejemplo.co"):
    return get_user_model().objects.create_user(email, is_staff=True)


class ResultsVisibilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = create_category(create_edition())
        cls.staff = create_staff()
        cls.public = AnonymousUser()

    def poll(self, visibility, **timing):
        return create_poll(self.category, results_visibility=visibility, **timing)

    def test_live_results_are_public_once_the_poll_opens(self):
        self.assertFalse(
            self.poll(ResultsVisibility.LIVE, **UPCOMING).results_visible_to(self.public)
        )
        self.assertTrue(self.poll(ResultsVisibility.LIVE).results_visible_to(self.public))
        self.assertTrue(
            self.poll(ResultsVisibility.LIVE, **CLOSED_WINDOW).results_visible_to(self.public)
        )

    def test_after_close_results_wait_for_the_poll_to_close(self):
        self.assertFalse(self.poll(ResultsVisibility.AFTER_CLOSE).results_visible_to(self.public))
        closed = self.poll(ResultsVisibility.AFTER_CLOSE, **CLOSED_WINDOW)
        self.assertTrue(closed.results_visible_to(self.public))
        closed_early = self.poll(ResultsVisibility.AFTER_CLOSE, closed_early=True)
        self.assertTrue(closed_early.results_visible_to(self.public))

    def test_hidden_results_are_only_for_the_organization(self):
        poll = self.poll(ResultsVisibility.HIDDEN, **CLOSED_WINDOW)
        self.assertFalse(poll.results_visible_to(self.public))
        self.assertFalse(poll.results_visible_to(create_voter()))
        self.assertTrue(poll.results_visible_to(self.staff))

    def test_the_organization_sees_the_count_before_the_public(self):
        poll = self.poll(ResultsVisibility.AFTER_CLOSE)
        self.assertTrue(poll.results_visible_to(self.staff))
        self.assertFalse(poll.results_are_public())


class TallyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.poll = create_poll(create_category(create_edition()), **CLOSED_WINDOW)
        cls.first, cls.second, cls.third = add_options(cls.poll, "Opción A", "Opción B", "Opción C")

    def test_counts_shares_and_leader_follow_the_option_order(self):
        cast_votes(self.first, 1)
        cast_votes(self.second, 2)
        tally = self.poll.tally()
        self.assertEqual(tally.total, 3)
        self.assertEqual([row.option for row in tally.rows], [self.first, self.second, self.third])
        self.assertEqual([row.votes for row in tally.rows], [1, 2, 0])
        self.assertAlmostEqual(tally.rows[1].share, 66.667, places=2)
        self.assertEqual([row.is_leading for row in tally.rows], [False, True, False])

    def test_a_tie_marks_every_leader(self):
        cast_votes(self.first, 2)
        cast_votes(self.third, 2)
        self.assertEqual([row.is_leading for row in self.poll.tally().rows], [True, False, True])

    def test_without_votes_nobody_leads(self):
        tally = self.poll.tally()
        self.assertEqual(tally.total, 0)
        self.assertEqual({row.share for row in tally.rows}, {0.0})
        self.assertFalse(any(row.is_leading for row in tally.rows))

    def test_one_query_counts_every_option(self):
        with self.assertNumQueries(1):
            self.poll.tally()


class ResultsLabelTests(SimpleTestCase):
    def test_counts_and_shares_use_spanish_separators(self):
        self.assertEqual(count_label(1234), "1.234")
        self.assertEqual(votes_label(1), "1 voto")
        self.assertEqual(votes_label(1234), "1.234 votos")
        self.assertEqual(percent_label(66.666), "66,7 %")


class ResultsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = create_category(create_edition(), name="Presentaciones")
        cls.staff = create_staff()

    def results_url(self, poll):
        return reverse("festival:poll-results", args=[poll.slug])

    def closed_poll(self, **overrides):
        poll = create_poll(
            self.category, title="Presentación más recordada", **CLOSED_WINDOW, **overrides
        )
        first, second = add_options(poll, "Presentación A", "Presentación B")
        cast_votes(first, 1)
        cast_votes(second, 2)
        return poll

    def test_a_closed_poll_shows_its_count(self):
        response = self.client.get(self.results_url(self.closed_poll()))
        self.assertContains(response, "2 votos (66,7 %)")
        self.assertContains(response, "1 voto (33,3 %)")
        self.assertContains(response, "3 votos válidos.")
        self.assertContains(response, 'class="result-bar result-bar--leading"', count=1)
        self.assertContains(response, "--value: 66.67")
        self.assertNotContains(response, "Conteo parcial")

    def test_after_close_hides_the_count_while_the_poll_is_open(self):
        poll = create_poll(self.category)
        first, _ = add_options(poll, "Presentación A", "Presentación B")
        cast_votes(first, 1)
        response = self.client.get(self.results_url(poll))
        self.assertContains(response, "Los resultados se publicarán al cierre")
        self.assertNotContains(response, "result-list")

    def test_live_results_are_marked_as_partial(self):
        poll = create_poll(self.category, results_visibility=ResultsVisibility.LIVE)
        first, _ = add_options(poll, "Presentación A", "Presentación B")
        cast_votes(first, 1)
        response = self.client.get(self.results_url(poll))
        self.assertContains(response, "1 voto (100,0 %)")
        self.assertContains(response, "1 voto válido. Conteo parcial: la votación sigue abierta.")

    def test_hidden_results_show_only_to_the_organization(self):
        poll = self.closed_poll(results_visibility=ResultsVisibility.HIDDEN)
        response = self.client.get(self.results_url(poll))
        self.assertContains(
            response, "Los resultados de esta votación los conoce solo la organización."
        )
        self.assertNotContains(response, "result-list")
        self.client.force_login(self.staff)
        response = self.client.get(self.results_url(poll))
        self.assertContains(response, "Lo ves porque eres de la organización.")
        self.assertContains(response, "2 votos (66,7 %)")

    def test_an_upcoming_poll_has_no_results_yet(self):
        response = self.client.get(self.results_url(create_poll(self.category, **UPCOMING)))
        self.assertContains(response, "La votación todavía no abre, por eso no hay resultados.")

    def test_drafts_and_inactive_categories_have_no_results_page(self):
        draft = create_poll(self.category, is_published=False, **CLOSED_WINDOW)
        inactive = create_poll(
            create_category(self.category.edition, is_active=False), **CLOSED_WINDOW
        )
        for poll in (draft, inactive):
            with self.subTest(poll=poll.title):
                self.assertEqual(self.client.get(self.results_url(poll)).status_code, 404)

    def test_the_page_runs_two_queries_whatever_the_number_of_options(self):
        poll = self.closed_poll()
        with self.assertNumQueries(2):
            self.client.get(self.results_url(poll))


class ResultsLinkTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = create_category(create_edition(), name="Música")

    def results_url(self, poll):
        return reverse("festival:poll-results", args=[poll.slug])

    def test_a_closed_poll_links_to_its_results(self):
        poll = create_poll(self.category, **CLOSED_WINDOW)
        add_options(poll, "Canción A", "Canción B")
        link = f'href="{self.results_url(poll)}"'
        self.assertContains(self.client.get(poll.get_absolute_url()), link)
        self.assertContains(self.client.get(self.category.get_absolute_url()), link)

    def test_a_voter_reaches_live_results_from_the_poll_and_the_receipt(self):
        poll = create_poll(self.category, results_visibility=ResultsVisibility.LIVE)
        option, _ = add_options(poll, "Canción A", "Canción B")
        voter = create_voter()
        vote = Vote.cast(voter, option)
        self.client.force_login(voter)
        link = f'href="{self.results_url(poll)}"'
        self.assertContains(self.client.get(poll.get_absolute_url()), link)
        self.assertContains(self.client.get(vote.get_absolute_url()), link)

    def test_after_close_results_are_not_offered_while_the_poll_is_open(self):
        poll = create_poll(self.category)
        option, _ = add_options(poll, "Canción A", "Canción B")
        voter = create_voter()
        vote = Vote.cast(voter, option)
        self.client.force_login(voter)
        self.assertNotContains(self.client.get(poll.get_absolute_url()), self.results_url(poll))
        self.assertNotContains(self.client.get(vote.get_absolute_url()), self.results_url(poll))
