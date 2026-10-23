from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

User = get_user_model()
PASSWORD = "vallenato-2027"


class UserManagerTests(TestCase):
    def test_emails_are_stored_in_lowercase(self):
        user = User.objects.create_user("Maria.Votante@Ejemplo.CO", PASSWORD)
        self.assertEqual(user.email, "maria.votante@ejemplo.co")

    def test_the_same_email_cannot_be_registered_twice(self):
        User.objects.create_user("maria@ejemplo.co", PASSWORD)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("MARIA@ejemplo.co", PASSWORD)

    def test_sign_in_ignores_email_case(self):
        user = User.objects.create_user("maria@ejemplo.co", PASSWORD)
        self.assertEqual(authenticate(username="Maria@Ejemplo.co", password=PASSWORD), user)

    def test_superuser_flags(self):
        admin = User.objects.create_superuser("admin@ejemplo.co", PASSWORD)
        self.assertTrue(admin.is_staff and admin.is_superuser)
        with self.assertRaises(ValueError):
            User.objects.create_superuser("otro@ejemplo.co", PASSWORD, is_staff=False)

    def test_display_name_falls_back_to_the_email(self):
        self.assertEqual(User(email="maria@ejemplo.co").display_name, "maria@ejemplo.co")
        self.assertEqual(User(email="maria@ejemplo.co", first_name="María").display_name, "María")
