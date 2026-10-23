from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from festival.models import Poll

from .builders import add_options, create_category, create_edition, create_poll


class PollAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(
            "admin@ejemplo.co", "vallenato-2027", first_name="Administración"
        )
        cls.category = create_category(create_edition())

    def setUp(self):
        self.client.force_login(self.admin)

    def poll_form(self, option_names, **values):
        form = {
            "category": self.category.pk,
            "title": "Agrupación favorita del público",
            "slug": "agrupacion-favorita-del-publico",
            "description": "",
            "opens_at_0": "2026-10-20",
            "opens_at_1": "08:00:00",
            "closes_at_0": "2026-10-30",
            "closes_at_1": "20:00:00",
            "is_published": "on",
            "votes_per_voter": "3",
            "vote_period": "day",
            "results_visibility": "live",
            "requires_account": "on",
            "options-TOTAL_FORMS": str(len(option_names)),
            "options-INITIAL_FORMS": "0",
            "options-MIN_NUM_FORMS": "0",
            "options-MAX_NUM_FORMS": "1000",
        }
        for index, name in enumerate(option_names):
            form[f"options-{index}-name"] = name
            form[f"options-{index}-detail"] = ""
            form[f"options-{index}-position"] = str(index + 1)
        form.update(values)
        return form

    def test_a_poll_needs_two_options_to_be_published(self):
        response = self.client.post(
            reverse("admin:festival_poll_add"), self.poll_form(["Conjunto A"])
        )
        self.assertContains(response, "Para publicar la votación agrega al menos 2 opciones.")
        self.assertFalse(Poll.objects.exists())

    def test_a_draft_can_be_saved_with_fewer_options(self):
        form = self.poll_form(["Conjunto A"])
        del form["is_published"]
        response = self.client.post(reverse("admin:festival_poll_add"), form)
        self.assertRedirects(response, reverse("admin:festival_poll_changelist"))
        self.assertFalse(Poll.objects.get().is_published)

    def test_a_poll_with_two_options_is_published(self):
        response = self.client.post(
            reverse("admin:festival_poll_add"), self.poll_form(["Conjunto A", "Conjunto B"])
        )
        self.assertRedirects(response, reverse("admin:festival_poll_changelist"))
        poll = Poll.objects.get()
        self.assertTrue(poll.is_published)
        self.assertEqual(
            list(poll.options.values_list("name", flat=True)), ["Conjunto A", "Conjunto B"]
        )

    def test_closing_date_must_be_after_the_opening_date(self):
        form = self.poll_form(["Conjunto A", "Conjunto B"], closes_at_0="2026-10-19")
        response = self.client.post(reverse("admin:festival_poll_add"), form)
        self.assertContains(response, "La fecha de cierre debe ser posterior a la de apertura.")

    def test_status_filter(self):
        create_poll(self.category, title="Abierta ahora")
        create_poll(self.category, title="Sin publicar", is_published=False)
        response = self.client.get(reverse("admin:festival_poll_changelist"), {"status": "draft"})
        self.assertEqual(
            [poll.title for poll in response.context["cl"].result_list], ["Sin publicar"]
        )

    def test_admin_pages_load(self):
        poll = create_poll(self.category)
        add_options(poll, "Opción A", "Opción B")
        pages = [
            reverse("admin:index"),
            reverse("admin:festival_edition_changelist"),
            reverse("admin:festival_edition_change", args=[self.category.edition.pk]),
            reverse("admin:festival_category_changelist"),
            reverse("admin:festival_poll_changelist"),
            reverse("admin:festival_poll_change", args=[poll.pk]),
            reverse("admin:accounts_user_changelist"),
            reverse("admin:accounts_user_add"),
            reverse("admin:accounts_user_change", args=[self.admin.pk]),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
