import csv
import io

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from festival.exports import spreadsheet_text

from .builders import (
    CLOSED_WINDOW,
    add_options,
    cast_votes,
    create_category,
    create_edition,
    create_poll,
    create_voter,
)


def create_admin():
    return get_user_model().objects.create_superuser(
        "admin@ejemplo.co", "vallenato-2027", first_name="Administración"
    )


class ResultsAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = create_admin()
        category = create_category(create_edition())
        cls.poll = create_poll(category, slug="presentacion-mas-recordada", **CLOSED_WINDOW)
        first, second, _ = add_options(
            cls.poll, "Presentación A", "Presentación B", "Presentación C"
        )
        cast_votes(first, 1)
        cast_votes(second, 3)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_the_poll_list_counts_options_and_votes_without_multiplying_them(self):
        response = self.client.get(reverse("admin:festival_poll_changelist"))
        poll = response.context["cl"].result_list[0]
        self.assertEqual((poll.option_count, poll.vote_count), (3, 4))

    def test_the_poll_form_shows_votes_per_option_and_the_results_links(self):
        response = self.client.get(reverse("admin:festival_poll_change", args=[self.poll.pk]))
        self.assertContains(response, reverse("festival:poll-results", args=[self.poll.slug]))
        self.assertContains(
            response, reverse("admin:festival_poll_results_csv", args=[self.poll.pk])
        )
        formset = response.context["inline_admin_formsets"][0].formset
        self.assertEqual([form.instance.vote_count for form in formset.forms], [1, 3, 0])

    def test_results_export_as_a_csv_that_excel_reads(self):
        response = self.client.get(reverse("admin:festival_poll_results_csv", args=[self.poll.pk]))
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn(
            'filename="resultados-presentacion-mas-recordada.csv"', response["Content-Disposition"]
        )
        text = response.content.decode("utf-8")
        self.assertTrue(text.startswith(chr(0xFEFF)))
        self.assertEqual(
            list(csv.reader(io.StringIO(text[1:]))),
            [
                ["Opción", "Votos", "Porcentaje"],
                ["Presentación A", "1", "25.00"],
                ["Presentación B", "3", "75.00"],
                ["Presentación C", "0", "0.00"],
                ["Total de votos válidos", "4", ""],
            ],
        )

    def test_an_option_name_is_not_read_as_a_formula(self):
        self.poll.options.filter(name="Presentación C").update(name="=1+1")
        response = self.client.get(reverse("admin:festival_poll_results_csv", args=[self.poll.pk]))
        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8")[1:])))
        self.assertEqual(rows[3][0], "'=1+1")

    def test_only_the_organization_can_export(self):
        url = reverse("admin:festival_poll_results_csv", args=[self.poll.pk])
        self.client.force_login(create_voter())
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])


class SpreadsheetTextTests(SimpleTestCase):
    def test_formula_characters_get_a_leading_quote(self):
        for value in ("=1+1", "+57", "-3", "@SUM(A1)", "\tA", "\rA"):
            with self.subTest(value=value):
                self.assertEqual(spreadsheet_text(value), f"'{value}")
        self.assertEqual(spreadsheet_text("Canción A"), "Canción A")
