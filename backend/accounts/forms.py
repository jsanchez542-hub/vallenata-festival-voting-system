from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    BaseUserCreationForm,
    UserChangeForm,
)
from django.core.exceptions import ValidationError
from django.utils import timezone

from .attempts import SignInAttempts
from .models import User

PASSWORD_HINT = "Mínimo 8 caracteres. No puede ser solo números ni una contraseña común."


class PrototypeInputMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "input"


class SignUpForm(PrototypeInputMixin, BaseUserCreationForm):
    privacy_accepted = forms.BooleanField(
        label="Acepto el tratamiento de mis datos personales",
        error_messages={"required": "Para crear la cuenta debes aceptar el tratamiento de datos."},
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
        widgets = {
            "first_name": forms.TextInput(attrs={"autocomplete": "given-name"}),
            "last_name": forms.TextInput(attrs={"autocomplete": "family-name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email"}),
        }
        help_texts = {"email": "Lo usarás para ingresar."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.pop("autofocus", None)
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True
        self.fields["password1"].help_text = PASSWORD_HINT
        self.fields["password2"].label = "Confirma la contraseña"
        self.fields["password2"].help_text = ""

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con este correo.", code="duplicate_email")
        return email

    def save(self, commit=True):
        self.instance.privacy_accepted_at = timezone.now()
        return super().save(commit)


class SignInForm(PrototypeInputMixin, AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "El correo o la contraseña no son correctos.",
        "locked": "Hubo demasiados intentos fallidos. Espera dos minutos y vuelve a intentarlo.",
    }

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.fields["username"].widget.input_type = "email"

    def clean(self):
        attempts = SignInAttempts(self.request, self.cleaned_data.get("username", ""))
        if not attempts.start():
            raise ValidationError(self.error_messages["locked"], code="locked")
        cleaned_data = super().clean()
        if self.user_cache is not None:
            attempts.succeeded()
        return cleaned_data


class UserAdminCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email", "first_name", "last_name")


class UserAdminChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
