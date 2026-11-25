from django.contrib.admin.models import ADDITION, LogEntry
from django.test import TestCase
from django.urls import reverse

from .builders import create_admin, create_category, create_edition


class ChangeLogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = create_admin()

    def setUp(self):
        self.client.force_login(self.admin)

    def test_admin_changes_appear_in_the_change_log(self):
        category = create_category(create_edition(), name="Música")
        response = self.client.post(
            reverse("admin:festival_category_change", args=[category.pk]),
            {
                "edition": category.edition.pk,
                "name": "Música y canciones",
                "description": "",
                "position": "1",
                "is_active": "on",
            },
        )
        self.assertRedirects(response, reverse("admin:festival_category_changelist"))
        response = self.client.get(reverse("admin:admin_logentry_changelist"))
        self.assertContains(response, "Cambió")
        self.assertContains(response, "Música y canciones (2027)")

    def test_the_change_log_cannot_be_edited(self):
        entry = LogEntry.objects.create(
            user=self.admin, action_flag=ADDITION, object_repr="Edición 61", change_message=""
        )
        self.assertEqual(self.client.get(reverse("admin:admin_logentry_add")).status_code, 403)
        delete_url = reverse("admin:admin_logentry_delete", args=[entry.pk])
        self.assertEqual(self.client.get(delete_url).status_code, 403)
