from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView, RedirectView, TemplateView

from .forms import VoteForm, already_voted_message, vote_refusal
from .models import Category, DuplicateVote, Edition, Poll, PollStatus, Vote, sorted_for_listing

PUBLIC_STATUSES = (PollStatus.OPEN, PollStatus.UPCOMING, PollStatus.CLOSED)


def own_vote_in(user, category):
    if not user.is_authenticated:
        return None
    return (
        Vote.objects.in_category(user, category).select_related("category", "option__poll").first()
    )


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
        context["own_vote"] = own_vote_in(self.request.user, self.object.category)
        return context


class PollVotingMixin(LoginRequiredMixin):
    extra_context = {"nav_section": "polls"}

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.poll = get_object_or_404(
            Poll.objects.published().select_related("category__edition"), slug=kwargs["slug"]
        )

    def vote_form(self, data):
        return VoteForm(data, poll=self.poll, voter=self.request.user)


class VoteView(PollVotingMixin, TemplateView):
    template_name = "festival/vote_options.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        own_vote = own_vote_in(self.request.user, self.poll.category)
        context.update(
            poll=self.poll,
            options=self.poll.options.all(),
            own_vote=own_vote,
            refusal=vote_refusal(self.poll, own_vote),
            selected=self.request.GET.get("option", ""),
        )
        return context


class ConfirmVoteView(PollVotingMixin, View):
    template_name = "festival/vote_confirm.html"

    def get(self, request, *args, **kwargs):
        form = self.vote_form(request.GET)
        if not form.is_valid():
            return self.refuse(form)
        context = {
            "poll": self.poll,
            "option": form.cleaned_data["option"],
            **self.extra_context,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        form = self.vote_form(request.POST)
        if not form.is_valid():
            return self.refuse(form)
        try:
            vote = Vote.cast(request.user, form.cleaned_data["option"])
        except DuplicateVote:
            messages.error(
                request, already_voted_message(own_vote_in(request.user, self.poll.category))
            )
            return redirect(self.poll)
        return redirect(vote)

    def refuse(self, form):
        refusals = form.non_field_errors()
        messages.error(self.request, (refusals or form.errors["option"])[0])
        if refusals:
            return redirect(self.poll)
        return redirect("festival:vote", slug=self.poll.slug)


class VoteReceiptView(LoginRequiredMixin, DetailView):
    template_name = "festival/vote_receipt.html"
    context_object_name = "vote"
    slug_field = "receipt"
    slug_url_kwarg = "receipt"
    extra_context = {"nav_section": "my-votes"}

    def get_queryset(self):
        return self.request.user.votes.select_related(
            "edition", "category", "option__poll__category__edition"
        )


class MyVotesView(LoginRequiredMixin, ListView):
    template_name = "festival/my_votes.html"
    context_object_name = "votes"
    extra_context = {"nav_section": "my-votes"}

    def get_queryset(self):
        return self.request.user.votes.select_related("edition", "category", "option__poll")
