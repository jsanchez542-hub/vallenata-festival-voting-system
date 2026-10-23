from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView, RedirectURLMixin
from django.shortcuts import redirect
from django.views.generic import CreateView

from .forms import SignInForm, SignUpForm


class SignUpView(RedirectURLMixin, CreateView):
    form_class = SignUpForm
    template_name = "accounts/sign_up.html"
    next_page = "festival:home"
    extra_context = {"nav_section": "sign-up"}

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[self.redirect_field_name] = self.get_redirect_url()
        return context

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, f"Cuenta creada. Hola, {user.display_name}.")
        return redirect(self.get_success_url())


class SignInView(LoginView):
    form_class = SignInForm
    template_name = "accounts/sign_in.html"
    redirect_authenticated_user = True
    extra_context = {"nav_section": "sign-in"}

    def form_valid(self, form):
        messages.success(self.request, f"Hola, {form.get_user().display_name}. Ya ingresaste.")
        return super().form_valid(form)


class SignOutView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, "Cerraste tu sesión.")
        return response
