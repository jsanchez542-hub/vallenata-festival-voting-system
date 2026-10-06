import { boot, renderBreadcrumb } from "../ui/chrome.js";
import { clearErrors, readForm, showErrors, safeNextPath, pageParams } from "../ui/forms.js";
import { showToast } from "../ui/dom.js";
import { registerUser } from "../data/auth.js";

const context = boot();
if (context) renderBreadcrumb([{ label: "Inicio", href: "index.html" }, { label: "Crear cuenta" }]);

if (context?.user) {
  location.replace("polls.html");
}

const form = document.querySelector("#sign-up-form");

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  clearErrors(form);
  const result = registerUser(readForm(form));
  if (!result.ok) {
    showErrors(form, result.errors);
    return;
  }
  showToast(`Cuenta creada. Bienvenido, ${result.user.name.split(" ")[0]}.`);
  const next = safeNextPath(pageParams().get("next")) ?? "polls.html?status=open";
  setTimeout(() => location.assign(next), 500);
});
