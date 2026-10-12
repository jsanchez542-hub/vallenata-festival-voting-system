import { boot, renderBreadcrumb } from "../ui/chrome.js";
import { el, mount } from "../ui/dom.js";
import { pageParams } from "../ui/forms.js";
import { pollRow } from "../ui/poll-views.js";
import { listCategories, listPolls, getCategory } from "../data/polls.js";

const context = boot();

const NO_FILTERS = { status: "", categoryId: "" };

let current = NO_FILTERS;

function filtersFromUrl() {
  const params = pageParams();
  return { status: params.get("status") ?? "", categoryId: params.get("category") ?? "" };
}

function buildHref({ status, categoryId }) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (categoryId) params.set("category", categoryId);
  const query = params.toString();
  return query ? `polls.html?${query}` : "polls.html";
}

function isPlainClick(event) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

function withTransition(update) {
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (document.startViewTransition && !reduceMotion) {
    const transition = document.startViewTransition(update);
    transition.ready.catch(() => {});
    return transition.updateCallbackDone;
  }
  update();
  return Promise.resolve();
}

function applyFilters(filters, { push }) {
  current = filters;
  if (push) history.pushState(null, "", buildHref(filters));
  return withTransition(() => {
    syncFilters(filters);
    renderContext(filters);
    renderList(filters);
  });
}

function enhanceFilters() {
  document.querySelectorAll(".segmented__item").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (!isPlainClick(event)) return;
      event.preventDefault();
      const status = link.dataset.status;
      if (status !== current.status) applyFilters({ ...current, status }, { push: true });
    });
  });

  const select = document.querySelector("#category-filter");
  select.append(...listCategories({ activeOnly: true }).map((category) => el("option", { value: category.id }, category.name)));
  select.addEventListener("change", () => applyFilters({ ...current, categoryId: select.value }, { push: true }));
}

function syncFilters(filters) {
  document.querySelectorAll(".segmented__item").forEach((link) => {
    const status = link.dataset.status;
    link.href = buildHref({ ...filters, status });
    if (status === filters.status) link.setAttribute("aria-current", "true");
    else link.removeAttribute("aria-current");
  });
  document.querySelector("#category-filter").value = filters.categoryId;
}

function renderContext(filters) {
  const category = filters.categoryId ? getCategory(filters.categoryId) : null;
  const lead = document.querySelector("#page-lead");
  lead.textContent = category ? `Categoría: ${category.name}` : "";
  lead.hidden = !category;
  renderBreadcrumb([
    { label: "Inicio", href: "index.html" },
    { label: "Votaciones", href: "polls.html" },
    ...(category ? [{ label: category.name }] : []),
  ]);
}

function renderList(filters) {
  const polls = listPolls({ status: filters.status || undefined, categoryId: filters.categoryId || undefined });
  const target = document.querySelector("#poll-list");
  const heading = document.querySelector("#poll-count");
  heading.textContent = polls.length === 1 ? "1 votación" : `${polls.length} votaciones`;

  if (polls.length === 0) {
    mount(
      target,
      el(
        "li",
        {},
        el(
          "div",
          { class: "empty-state" },
          el("h3", {}, "No hay votaciones con estos filtros"),
          el("p", {}, "Prueba con otro estado o con todas las categorías."),
          el(
            "a",
            {
              class: "button button--outline",
              href: "polls.html",
              onclick: (event) => {
                if (!isPlainClick(event)) return;
                event.preventDefault();
                applyFilters(NO_FILTERS, { push: true }).then(() => document.querySelector(".segmented__item[aria-current]")?.focus());
              },
            },
            "Quitar filtros",
          ),
        ),
      ),
    );
    return;
  }
  mount(target, polls.map((poll) => pollRow(poll)));
}

if (context) {
  current = filtersFromUrl();
  enhanceFilters();
  syncFilters(current);
  renderContext(current);
  renderList(current);
  addEventListener("popstate", () => applyFilters(filtersFromUrl(), { push: false }));
}
