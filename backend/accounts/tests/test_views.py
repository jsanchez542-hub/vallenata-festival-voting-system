from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from accounts.attempts import ACCOUNT_FAILURE_LIMIT, ADDRESS_FAILURE_LIMIT

User = get_user_model()
PASSWORD = "vallenato-2027"


class SignUpTests(TestCase):
    url = reverse("accounts:sign-up")

    def form(self, **values):
        return {
            "first_name": "María",
            "last_name": "Pérez",
            "email": "maria@ejemplo.co",
            "password1": PASSWORD,
            "password2": PASSWORD,
            "privacy_accepted": "on",
            **values,
        }

    def test_creates_the_account_records_consent_and_signs_in(self):
        response = self.client.post(self.url, self.form(), follow=True)
        self.assertRedirects(response, reverse("festival:home"))
        user = User.objects.get()
        self.assertIsNotNone(user.privacy_accepted_at)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)
        self.assertContains(response, "Cuenta creada. Hola, María.")
        self.assertContains(response, "Salir (María)")

    def test_consent_is_required(self):
        response = self.client.post(self.url, self.form(privacy_accepted=""))
        self.assertContains(response, "Para crear la cuenta debes aceptar el tratamiento de datos.")
        self.assertFalse(User.objects.exists())

    def test_email_must_be_new_regardless_of_case(self):
        User.objects.create_user("maria@ejemplo.co", PASSWORD)
        response = self.client.post(self.url, self.form(email="MARIA@ejemplo.co"))
        self.assertContains(response, "Ya existe una cuenta con este correo.")

    def test_weak_passwords_are_rejected(self):
        response = self.client.post(self.url, self.form(password1="12345678", password2="12345678"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors["password2"])
        self.assertFalse(User.objects.exists())

    def test_returns_to_the_poll_after_signing_up(self):
        response = self.client.post(f"{self.url}?next=/polls/cancion/", self.form())
        self.assertRedirects(response, "/polls/cancion/", fetch_redirect_response=False)

    def test_ignores_redirects_to_other_sites(self):
        response = self.client.post(f"{self.url}?next=https://example.com/", self.form())
        self.assertRedirects(response, reverse("festival:home"))

    def test_signed_in_users_are_sent_home(self):
        self.client.force_login(User.objects.create_user("maria@ejemplo.co", PASSWORD))
        self.assertRedirects(self.client.get(self.url), reverse("festival:home"))


class SignInTests(TestCase):
    url = reverse("accounts:sign-in")

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("maria@ejemplo.co", PASSWORD, first_name="María")

    def setUp(self):
        cache.clear()

    def sign_in(self, password=PASSWORD, email="maria@ejemplo.co", **extra):
        return self.client.post(self.url, {"username": email, "password": password}, **extra)

    def test_signs_in_with_email_and_password(self):
        response = self.sign_in(email="Maria@Ejemplo.co", follow=True)
        self.assertRedirects(response, reverse("festival:home"))
        self.assertContains(response, "Hola, María. Ya ingresaste.")

    def test_wrong_password_shows_a_generic_message(self):
        response = self.sign_in(password="otra-clave")
        self.assertContains(response, "El correo o la contraseña no son correctos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def assertLocked(self, response):
        self.assertContains(response, "Hubo demasiados intentos fallidos.")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_locks_the_form_after_repeated_failures(self):
        for _ in range(ACCOUNT_FAILURE_LIMIT):
            self.sign_in(password="otra-clave")
        self.assertLocked(self.sign_in())

    def test_variants_of_the_email_share_one_counter(self):
        variants = ["MARIA@ejemplo.co", "maría@ejemplo.co", " Maria@Ejemplo.co "]
        for index in range(ACCOUNT_FAILURE_LIMIT):
            self.sign_in(password="otra-clave", email=variants[index % len(variants)])
        self.assertLocked(self.sign_in())

    def test_an_incomplete_submission_does_not_reset_the_count(self):
        for _ in range(ACCOUNT_FAILURE_LIMIT - 1):
            self.sign_in(password="otra-clave")
        self.sign_in(password="")
        self.assertLocked(self.sign_in())

    def test_limits_failures_from_one_address_across_accounts(self):
        for index in range(ADDRESS_FAILURE_LIMIT):
            self.sign_in(password="otra-clave", email=f"persona{index}@ejemplo.co")
        self.assertLocked(self.sign_in())

    def test_a_successful_sign_in_resets_the_failure_count(self):
        for _ in range(ACCOUNT_FAILURE_LIMIT - 1):
            self.sign_in(password="otra-clave")
        self.sign_in()
        self.client.logout()
        self.sign_in(password="otra-clave")
        response = self.sign_in(follow=True)
        self.assertContains(response, "Ya ingresaste.")


class SignOutTests(TestCase):
    url = reverse("accounts:sign-out")

    def setUp(self):
        self.client.force_login(User.objects.create_user("maria@ejemplo.co", PASSWORD))

    def test_signs_out_with_post(self):
        response = self.client.post(self.url, follow=True)
        self.assertRedirects(response, reverse("festival:home"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertContains(response, "Cerraste tu sesión.")

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
