const TOAST_DURATION_MS = 6000;

function setUpMenu() {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector("#site-nav");
  if (!toggle || !nav) return;

  const setOpen = (isOpen) => {
    nav.dataset.open = String(isOpen);
    toggle.setAttribute("aria-expanded", String(isOpen));
  };
  toggle.addEventListener("click", () => setOpen(nav.dataset.open !== "true"));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && nav.dataset.open === "true") {
      setOpen(false);
      toggle.focus();
    }
  });
}

function dismissToasts() {
  document.querySelectorAll(".toast").forEach((toast) => {
    setTimeout(() => toast.remove(), TOAST_DURATION_MS);
  });
}

setUpMenu();
dismissToasts();
