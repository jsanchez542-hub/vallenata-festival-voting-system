from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from .builders import add_options, create_category, create_edition, create_poll


class PublicPagesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.edition = create_edition(number=60)
        cls.music = create_category(cls.edition, name="Música", position=1)
        cls.stage = create_category(cls.edition, name="Presentaciones", position=2)
        cls.hidden = create_category(cls.edition, name="Oculta", is_active=False)
        cls.song = create_poll(cls.music, title="Canción favorita del público")
        add_options(cls.song, "Canción A", "Canción B")
        cls.upcoming = create_poll(
            cls.music,
            title="Vestuario más destacado",
            opens_in=timedelta(days=4),
            closes_in=timedelta(days=12),
        )
        cls.closed = create_poll(
            cls.stage,
            title="Presentación más recordada",
            opens_in=timedelta(days=-12),
            closes_in=timedelta(days=-1),
        )
        cls.draft = create_poll(cls.music, title="Borrador interno", is_published=False)
        cls.hidden_poll = create_poll(cls.hidden, title="Votación oculta")

    def test_home_lists_only_open_polls_of_the_current_edition(self):
        response = self.client.get(reverse("festival:home"))
        self.assertContains(response, "Canción favorita del público")
        self.assertNotContains(response, "Vestuario más destacado")
        self.assertNotContains(response, "Presentación más recordada")
        self.assertNotContains(response, "Borrador interno")
        self.assertNotContains(response, "Votación oculta")
        self.assertContains(response, "2 votaciones, 1 abierta")

    def test_home_does_not_repeat_queries_per_poll_or_category(self):
        with self.assertNumQueries(3):
            self.client.get(reverse("festival:home"))

    def test_poll_list_filters_by_status(self):
        url = reverse("festival:poll-list")
        response = self.client.get(url, {"status": "closed"})
        self.assertEqual([poll.title for poll in response.context["polls"]], [self.closed.title])
        response = self.client.get(url, {"status": "draft"})
        self.assertEqual(len(response.context["polls"]), 3)

    def test_poll_detail_shows_options_in_order_and_the_rules(self):
        response = self.client.get(self.song.get_absolute_url())
        self.assertContains(response, "Opciones (2)")
        content = response.content.decode()
        self.assertLess(content.index("Canción A"), content.index("Canción B"))
        self.assertContains(response, "1 voto en total")
        self.assertContains(response, "Al cierre de la votación")

    def test_anonymous_visitor_is_invited_to_sign_in_and_come_back(self):
        response = self.client.get(self.song.get_absolute_url())
        sign_in = reverse("accounts:sign-in")
        self.assertContains(response, f'href="{sign_in}?next={self.song.get_absolute_url()}"')

    def test_signed_in_visitor_is_told_that_voting_is_not_available_yet(self):
        user = get_user_model().objects.create_user("votante@ejemplo.co", "vallenato-2027")
        self.client.force_login(user)
        response = self.client.get(self.song.get_absolute_url())
        self.assertContains(response, "El registro de votos todavía no está habilitado")
        self.assertNotContains(response, "Ingresar para votar")

    def test_drafts_and_polls_in_inactive_categories_are_not_found(self):
        for poll in (self.draft, self.hidden_poll):
            with self.subTest(poll=poll.title):
                self.assertEqual(self.client.get(poll.get_absolute_url()).status_code, 404)

    def test_category_page_lists_its_published_polls(self):
        response = self.client.get(self.music.get_absolute_url())
        titles = [poll.title for poll in response.context["polls"]]
        self.assertEqual(titles, [self.song.title, self.upcoming.title])

    def test_inactive_category_is_not_found(self):
        self.assertEqual(self.client.get(self.hidden.get_absolute_url()).status_code, 404)

    def test_categories_link_goes_to_the_current_edition(self):
        response = self.client.get(reverse("festival:category-list"))
        self.assertRedirects(response, self.edition.get_absolute_url())

    def test_edition_page_lists_active_categories_with_counts(self):
        response = self.client.get(self.edition.get_absolute_url())
        self.assertEqual(list(response.context["categories"]), [self.music, self.stage])
        self.assertContains(response, "2 votaciones, 1 abierta")

    def test_edition_list_counts_only_public_content(self):
        response = self.client.get(reverse("festival:edition-list"))
        edition = response.context["editions"][0]
        self.assertEqual((edition.category_count, edition.poll_count), (2, 3))

    @override_settings(DEBUG=False)
    def test_missing_page_uses_the_site_layout(self):
        response = self.client.get("/polls/no-existe/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "No encontramos esta página", status_code=404)


class EmptySiteTests(TestCase):
    def test_pages_render_before_any_edition_exists(self):
        self.assertContains(self.client.get(reverse("festival:home")), "Votaciones del público")
        self.assertContains(self.client.get(reverse("festival:poll-list")), "Votaciones")
        self.assertRedirects(
            self.client.get(reverse("festival:category-list")), reverse("festival:edition-list")
        )
