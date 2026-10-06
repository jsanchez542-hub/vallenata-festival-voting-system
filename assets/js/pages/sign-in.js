import { boot, renderBreadcrumb } from "../ui/chrome.js";
import { clearErrors, readForm, showErrors, safeNextPath, pageParams } from "../ui/forms.js";
import { mount, notice } from "../ui/dom.js";
import { signIn } from "../data/auth.js";

const context = boot();
if (context) renderBreadcrumb([{ label: "Inicio", href: "index.html" }, { label: "Ingresar" }]);
const params = pageParams();
const next = safeNextPath(params.get("next"));

if (context?.user && params.get("reason") !== "admin") {
  location.replace(next ?? "polls.html");
}

const form = document.querySelector("#sign-in-form");
const alertSlot = document.querySelector("#form-alert");

if (params.get("reason") === "admin") {
  mount(alertSlot, notice("warning", "Esta sección es solo para administración. Ingresa con una cuenta de administración para continuar."));
}

document.querySelectorAll("[data-demo-account]").forEach((button) => {
  button.addEventListener("click", () => {
    form.elements.email.value = button.dataset.email;
    form.elements.password.value = button.dataset.password;
    form.elements.email.focus();
  });
});

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  clearErrors(form);
  const { email, password } = readForm(form);
  const errors = {};
  if (!email.trim()) errors.email = "Escribe tu correo.";
  if (!password) errors.password = "Escribe tu contraseña.";
  if (Object.keys(errors).length > 0) {
    showErrors(form, errors);
    return;
  }
  const result = signIn(email, password);
  if (!result.ok) {
    mount(alertSlot, notice("danger", result.error));
    return;
  }
  const fallback = result.user.role === "admin" ? "admin/dashboard.html" : "polls.html?status=open";
  location.assign(next ?? fallback);
});
