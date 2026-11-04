import json

from django.test import TestCase
from django.urls import reverse

from .builders import add_options, create_category, create_edition, create_poll


class CategoriesApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        edition = create_edition(number=60)
        cls.music = create_category(edition, name="Música", position=1)
        cls.song = create_poll(cls.music, title="Canción favorita del público")
        add_options(cls.song, "Canción A", "Canción B")
        create_poll(cls.music, title="Borrador interno", is_published=False)
        hidden = create_category(edition, name="Oculta", is_active=False)
        create_poll(hidden, title="Votación oculta")
        cls.url = reverse("festival:api-categories")

    def test_cp10_returns_categories_with_their_polls_and_options(self):
        response = self.client.get(self.url)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = json.loads(response.content)
        self.assertEqual(payload["count"], 1)
        category = payload["categories"][0]
        self.assertEqual((category["name"], category["edition"]["year"]), ("Música", 2027))
        poll = category["polls"][0]
        self.assertEqual((poll["title"], poll["status"]), ("Canción favorita del público", "open"))
        self.assertEqual([option["name"] for option in poll["options"]], ["Canción A", "Canción B"])
        self.assertTrue(poll["url"].endswith(self.song.get_absolute_url()))

    def test_cp10_leaves_out_drafts_and_inactive_categories(self):
        content = self.client.get(self.url).content.decode()
        self.assertNotIn("Borrador interno", content)
        self.assertNotIn("Oculta", content)

    def test_keeps_accents_unescaped(self):
        self.assertIn("Música".encode(), self.client.get(self.url).content)

    def test_runs_three_queries_however_many_rows_it_returns(self):
        with self.assertNumQueries(3):
            self.client.get(self.url)

    def test_only_answers_get(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
