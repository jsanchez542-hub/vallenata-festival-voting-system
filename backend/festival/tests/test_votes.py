import threading
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection
from django.db.models import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from festival.models import DuplicateVote, Vote

from .builders import add_options, create_category, create_edition, create_poll, create_voter


def build_ballot(test):
    test.edition = create_edition(number=60)
    test.music = create_category(test.edition, name="Música")
    test.costume = create_category(test.edition, name="Piloneras y vestuario")
    test.song = create_poll(test.music, title="Canción favorita del público")
    test.song_a, test.song_b = add_options(test.song, "Canción A", "Canción B")
    test.band = create_poll(test.music, title="Agrupación favorita del público")
    (test.band_a,) = add_options(test.band, "Conjunto A")
    test.dress = create_poll(test.costume, title="Vestuario más destacado")
    (test.dress_a,) = add_options(test.dress, "Vestuario A")
    test.voter = create_voter("votante@ejemplo.co")


class VoteModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_ballot(cls)

    def test_cast_takes_the_edition_and_category_from_the_option(self):
        vote = Vote.cast(self.voter, self.song_a)
        self.assertEqual(
            (vote.edition, vote.category, vote.option), (self.edition, self.music, self.song_a)
        )

    def test_receipts_follow_the_prototype_format(self):
        self.assertRegex(Vote.cast(self.voter, self.song_a).receipt, r"^FVL-[2-9A-HJKMNP-Z]{8}$")

    def test_the_database_rejects_a_second_vote_in_the_category(self):
        Vote.cast(self.voter, self.song_a)
        with self.assertRaises(IntegrityError):
            Vote.objects.create(
                voter=self.voter,
                edition=self.edition,
                category=self.music,
                option=self.band_a,
                receipt="FVL-OTRO0000",
            )

    def test_cast_reports_a_second_vote_in_the_category(self):
        Vote.cast(self.voter, self.song_a)
        with self.assertRaises(DuplicateVote):
            Vote.cast(self.voter, self.band_a)
        self.assertEqual(Vote.objects.count(), 1)

    def test_an_option_with_votes_cannot_be_deleted(self):
        Vote.cast(self.voter, self.song_a)
        with self.assertRaises(ProtectedError):
            self.song_a.delete()

    def test_a_poll_with_votes_cannot_move_to_another_category(self):
        Vote.cast(self.voter, self.song_a)
        self.song.category = self.costume
        with self.assertRaisesMessage(ValidationError, "no se puede pasar a otra categoría"):
            self.song.full_clean()

    def test_a_category_with_votes_cannot_move_to_another_edition(self):
        Vote.cast(self.voter, self.song_a)
        self.music.edition = create_edition(number=59)
        with self.assertRaisesMessage(ValidationError, "no se puede pasar a otra edición"):
            self.music.full_clean()


class VotingFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_ballot(cls)
        cls.closed = create_poll(
            cls.costume, opens_in=timedelta(days=-9), closes_in=timedelta(days=-1)
        )
        cls.upcoming = create_poll(
            cls.costume, opens_in=timedelta(days=3), closes_in=timedelta(days=9)
        )
        add_options(cls.closed, "Opción cerrada")
        add_options(cls.upcoming, "Opción próxima")

    def setUp(self):
        self.client.force_login(self.voter)

    def confirm_url(self, poll):
        return reverse("festival:vote-confirm", args=[poll.slug])

    def vote(self, poll, option, client=None):
        return (client or self.client).post(
            self.confirm_url(poll), {"option": option.pk}, follow=True
        )

    def test_cp01_choosing_an_option_asks_for_confirmation_without_saving(self):
        options_page = self.client.get(reverse("festival:vote", args=[self.song.slug]))
        self.assertContains(options_page, "Continuar a la confirmación")
        response = self.client.get(self.confirm_url(self.song), {"option": self.song_b.pk})
        self.assertContains(response, "Vas a votar por")
        self.assertContains(response, "Canción B")
        self.assertFalse(Vote.objects.exists())

    def test_cp01_confirming_records_the_vote_and_shows_the_receipt(self):
        response = self.vote(self.song, self.song_b)
        vote = Vote.objects.get()
        self.assertRedirects(response, vote.get_absolute_url())
        self.assertContains(response, "Voto registrado")
        self.assertContains(response, vote.receipt)
        self.assertEqual((vote.voter, vote.option), (self.voter, self.song_b))

    def test_cp02_a_second_vote_in_the_same_poll_is_refused(self):
        self.vote(self.song, self.song_a)
        response = self.vote(self.song, self.song_b)
        self.assertRedirects(response, self.song.get_absolute_url())
        self.assertContains(
            response, "Ya votaste en la categoría Música de esta edición, por Canción A"
        )
        self.assertEqual(Vote.objects.get().option, self.song_a)

    def test_cp02_a_vote_in_another_poll_of_the_category_is_refused(self):
        self.vote(self.song, self.song_a)
        options_page = self.client.get(reverse("festival:vote", args=[self.band.slug]))
        self.assertContains(options_page, "Ya votaste en la categoría Música")
        self.assertNotContains(options_page, "Continuar a la confirmación")
        self.vote(self.band, self.band_a)
        self.assertEqual(Vote.objects.count(), 1)

    def test_cp02_the_poll_page_shows_the_vote_instead_of_the_button(self):
        self.vote(self.song, self.song_a)
        response = self.client.get(self.band.get_absolute_url())
        self.assertContains(
            response, "Ya votaste en Música por <strong>Canción A</strong>, en Canción favorita"
        )
        self.assertNotContains(response, reverse("festival:vote", args=[self.band.slug]))

    def test_cp03_a_vote_in_another_category_is_accepted(self):
        self.vote(self.song, self.song_a)
        self.vote(self.dress, self.dress_a)
        self.assertEqual(Vote.objects.filter(voter=self.voter).count(), 2)

    def test_cp03_another_voter_can_vote_in_the_same_category(self):
        self.vote(self.song, self.song_a)
        neighbour = Client()
        neighbour.force_login(create_voter())
        self.vote(self.song, self.song_a, client=neighbour)
        self.assertEqual(Vote.objects.filter(category=self.music).count(), 2)

    def test_cp04_anonymous_visitors_are_sent_to_sign_in(self):
        self.client.logout()
        sign_in = reverse("accounts:sign-in")
        options_url = reverse("festival:vote", args=[self.song.slug])
        self.assertRedirects(self.client.get(options_url), f"{sign_in}?next={options_url}")
        response = self.client.post(self.confirm_url(self.song), {"option": self.song_a.pk})
        self.assertRedirects(response, f"{sign_in}?next={self.confirm_url(self.song)}")
        self.assertFalse(Vote.objects.exists())

    def test_cp04_a_post_without_the_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.voter)
        response = client.post(self.confirm_url(self.song), {"option": self.song_a.pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Vote.objects.exists())

    def test_cp05_closed_and_upcoming_polls_refuse_votes(self):
        for poll, message in (
            (self.closed, "Esta votación ya cerró y no recibe más votos."),
            (self.upcoming, "Esta votación todavía no abre."),
        ):
            with self.subTest(poll=poll.title):
                self.assertContains(
                    self.client.get(reverse("festival:vote", args=[poll.slug])), message
                )
                response = self.vote(poll, poll.options.get())
                self.assertRedirects(response, poll.get_absolute_url())
                self.assertContains(response, message)
        self.assertFalse(Vote.objects.exists())

    def test_cp05_drafts_and_polls_in_inactive_categories_are_not_found(self):
        draft = create_poll(self.music, is_published=False)
        hidden = create_poll(create_category(self.edition, is_active=False))
        for poll in (draft, hidden):
            with self.subTest(poll=poll.title):
                self.assertEqual(
                    self.client.get(reverse("festival:vote", args=[poll.slug])).status_code, 404
                )
                self.assertEqual(
                    self.client.post(self.confirm_url(poll), {"option": 1}).status_code, 404
                )

    def test_cp06_an_option_from_another_poll_is_refused(self):
        for option in (self.dress_a, self.band_a):
            with self.subTest(option=option.name):
                response = self.vote(self.song, option)
                self.assertRedirects(response, reverse("festival:vote", args=[self.song.slug]))
                self.assertContains(response, "La opción enviada no pertenece a esta votación.")
        for value in ("999999", "uno", ""):
            with self.subTest(value=value):
                self.client.post(self.confirm_url(self.song), {"option": value})
        self.assertFalse(Vote.objects.exists())

    def test_cp07_my_votes_lists_only_the_voters_votes(self):
        self.vote(self.song, self.song_a)
        other = Client()
        other.force_login(create_voter())
        self.vote(self.dress, self.dress_a, client=other)
        response = self.client.get(reverse("festival:my-votes"))
        self.assertEqual([vote.option for vote in response.context["votes"]], [self.song_a])
        self.assertContains(response, Vote.objects.get(voter=self.voter).receipt)

    def test_cp07_my_votes_requires_signing_in(self):
        self.client.logout()
        url = reverse("festival:my-votes")
        self.assertRedirects(self.client.get(url), f"{reverse('accounts:sign-in')}?next={url}")

    def test_a_receipt_is_only_visible_to_its_voter(self):
        self.vote(self.song, self.song_a)
        receipt = Vote.objects.get().get_absolute_url()
        other = Client()
        other.force_login(create_voter())
        self.assertEqual(other.get(receipt).status_code, 404)


class VoteAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        build_ballot(cls)
        cls.admin = get_user_model().objects.create_superuser("admin@ejemplo.co", "vallenato-2027")
        cls.vote = Vote.cast(cls.voter, cls.song_a)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_cp08_votes_are_listed_and_can_only_be_viewed(self):
        changelist = self.client.get(reverse("admin:festival_vote_changelist"))
        self.assertContains(changelist, self.vote.receipt)
        self.assertNotContains(changelist, reverse("admin:festival_vote_add"))
        detail = self.client.get(reverse("admin:festival_vote_change", args=[self.vote.pk]))
        self.assertContains(detail, "Canción A")
        self.assertNotContains(detail, 'name="_save"')
        self.assertEqual(self.client.get(reverse("admin:festival_vote_add")).status_code, 403)
        self.assertEqual(
            self.client.post(
                reverse("admin:festival_vote_delete", args=[self.vote.pk])
            ).status_code,
            403,
        )

    def test_an_option_with_votes_cannot_be_renamed_in_the_poll_form(self):
        url = reverse("admin:festival_poll_change", args=[self.song.pk])
        form = self.client.get(url).context["adminform"].form
        data = {
            "category": self.music.pk,
            "title": self.song.title,
            "slug": self.song.slug,
            "description": "",
            "opens_at_0": form["opens_at"].value().strftime("%Y-%m-%d"),
            "opens_at_1": "08:00:00",
            "closes_at_0": form["closes_at"].value().strftime("%Y-%m-%d"),
            "closes_at_1": "20:00:00",
            "is_published": "on",
            "results_visibility": "after_close",
            "options-TOTAL_FORMS": "2",
            "options-INITIAL_FORMS": "2",
            "options-MIN_NUM_FORMS": "0",
            "options-MAX_NUM_FORMS": "1000",
        }
        for index, option in enumerate((self.song_a, self.song_b)):
            data.update(
                {
                    f"options-{index}-id": option.pk,
                    f"options-{index}-poll": self.song.pk,
                    f"options-{index}-name": option.name,
                    f"options-{index}-detail": "",
                    f"options-{index}-position": option.position,
                }
            )
        data["options-0-name"] = "Canción A renombrada"
        response = self.client.post(url, data)
        self.assertContains(
            response, "La opción «Canción A» ya tiene votos y no se puede renombrar ni borrar."
        )
        self.song_a.refresh_from_db()
        self.assertEqual(self.song_a.name, "Canción A")


class SimultaneousVotesTests(TransactionTestCase):
    requests = 8

    def test_cp09_simultaneous_requests_leave_a_single_vote(self):
        build_ballot(self)
        url = reverse("festival:vote-confirm", args=[self.song.slug])
        barrier = threading.Barrier(self.requests)
        statuses = []

        def vote():
            try:
                client = Client()
                client.force_login(self.voter)
                barrier.wait()
                statuses.append(client.post(url, {"option": self.song_a.pk}).status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=vote) for _ in range(self.requests)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(statuses, [302] * self.requests)
        self.assertEqual(Vote.objects.filter(voter=self.voter, category=self.music).count(), 1)
