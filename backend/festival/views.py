from django.db.models import Count, Q
from django.urls import reverse
from django.views.generic import DetailView, ListView, RedirectView, TemplateView

from .models import Category, Edition, Poll, PollStatus, sorted_for_listing

PUBLIC_STATUSES = (PollStatus.OPEN, PollStatus.UPCOMING, PollStatus.CLOSED)


class HomeView(TemplateView):
    template_name = "festival/home.html"
    extra_context = {"nav_section": "home"}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        edition = Edition.objects.current()
        context["edition"] = edition
        context["open_polls"] = []
        context["categories"] = []
        if edition:
            open_polls = Poll.objects.published().open().filter(category__edition=edition)
            context["open_polls"] = sorted_for_listing(open_polls.for_listing())
            context["categories"] = edition.categories.active().with_poll_counts()
        return context


class EditionListView(ListView):
    template_name = "festival/edition_list.html"
    context_object_name = "editions"

    def get_queryset(self):
        active = Q(categories__is_active=True)
        return Edition.objects.annotate(
            category_count=Count("categories", filter=active, distinct=True),
            poll_count=Count(
                "categories__polls",
                filter=active & Q(categories__polls__is_published=True),
                distinct=True,
            ),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_edition"] = Edition.objects.current()
        return context


class CurrentEditionRedirectView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        edition = Edition.objects.current()
        return edition.get_absolute_url() if edition else reverse("festival:edition-list")


class EditionDetailView(DetailView):
    template_name = "festival/edition_detail.html"
    context_object_name = "edition"
    slug_field = "year"
    slug_url_kwarg = "year"
    extra_context = {"nav_section": "categories"}

    def get_queryset(self):
        return Edition.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = self.object.categories.active().with_poll_counts()
        return context


class CategoryDetailView(DetailView):
    template_name = "festival/category_detail.html"
    context_object_name = "category"
    extra_context = {"nav_section": "categories"}

    def get_queryset(self):
        return Category.objects.active().select_related("edition")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        polls = Poll.objects.published().filter(category=self.object).for_listing()
        context["polls"] = sorted_for_listing(polls)
        return context


class PollListView(ListView):
    template_name = "festival/poll_list.html"
    context_object_name = "polls"
    extra_context = {"nav_section": "polls"}

    def get(self, request, *args, **kwargs):
        self.edition = Edition.objects.current()
        status = request.GET.get("status", "")
        self.status = PollStatus(status) if status in PUBLIC_STATUSES else None
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        polls = Poll.objects.published().filter(category__edition=self.edition)
        if self.status:
            polls = polls.in_status(self.status)
        return sorted_for_listing(polls.for_listing())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["edition"] = self.edition
        context["status"] = self.status
        return context


class PollDetailView(DetailView):
    template_name = "festival/poll_detail.html"
    context_object_name = "poll"
    extra_context = {"nav_section": "polls"}

    def get_queryset(self):
        return Poll.objects.published().select_related("category__edition")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["options"] = self.object.options.all()
        return context
