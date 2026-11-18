from django import forms
from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION, LogEntry
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404, HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .exports import results_csv
from .forms import OptionInlineFormSet
from .models import Category, Edition, Option, Poll, PollStatus, Vote

ACTION_LABELS = {ADDITION: "Creó", CHANGE: "Cambió", DELETION: "Borró"}


class CategoryInline(admin.TabularInline):
    model = Category
    fields = ("name", "description", "position", "is_active")
    extra = 0


@admin.register(Edition)
class EditionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "city", "starts_on", "ends_on", "category_count")
    inlines = [CategoryInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(category_count=Count("categories"))

    @admin.display(description="categorías", ordering="category_count")
    def category_count(self, edition):
        return edition.category_count


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "edition", "position", "is_active", "poll_count")
    list_editable = ("position", "is_active")
    list_filter = ("edition", "is_active")
    list_select_related = ("edition",)
    search_fields = ("name", "description")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(poll_count=Count("polls"))

    @admin.display(description="votaciones", ordering="poll_count")
    def poll_count(self, category):
        return category.poll_count


class PollStatusFilter(admin.SimpleListFilter):
    title = "estado"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return PollStatus.choices

    def queryset(self, request, queryset):
        if self.value() == PollStatus.DRAFT:
            return queryset.filter(is_published=False)
        if self.value() in PollStatus.values:
            return queryset.in_status(self.value())
        return queryset


class OptionInline(admin.TabularInline):
    model = Option
    formset = OptionInlineFormSet
    fields = ("name", "detail", "position", "vote_count")
    readonly_fields = ("vote_count",)

    def get_extra(self, request, obj=None, **kwargs):
        return 0 if obj else 2

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(vote_count=Count("votes"))

    @admin.display(description="votos")
    def vote_count(self, option):
        # The empty rows for new options are not saved yet, so they carry no count.
        return getattr(option, "vote_count", 0)


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "status_label",
        "opens_at",
        "closes_at",
        "option_count",
        "vote_count",
    )
    list_filter = (PollStatusFilter, "category__edition")
    list_select_related = ("category__edition",)
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("results_links",)
    inlines = [OptionInline]
    fieldsets = (
        (None, {"fields": ("category", "title", "slug", "description")}),
        ("Calendario", {"fields": ("opens_at", "closes_at", "is_published", "closed_early")}),
        ("Resultados", {"fields": ("results_visibility", "results_links")}),
    )

    def get_queryset(self, request):
        # Both counts join through the options, so each one needs distinct to avoid multiplying.
        return (
            super()
            .get_queryset(request)
            .annotate(
                option_count=Count("options", distinct=True),
                vote_count=Count("options__votes", distinct=True),
            )
        )

    def get_urls(self):
        export = self.admin_site.admin_view(self.export_results)
        return [
            path("<path:object_id>/results.csv", export, name="festival_poll_results_csv"),
            *super().get_urls(),
        ]

    def export_results(self, request, object_id):
        poll = self.get_object(request, object_id)
        if poll is None:
            raise Http404
        if not self.has_view_permission(request, poll):
            raise PermissionDenied
        response = HttpResponse(results_csv(poll), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="resultados-{poll.slug}.csv"'
        return response

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "description":
            kwargs["widget"] = forms.Textarea(attrs={"rows": 3})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "category":
            kwargs["queryset"] = Category.objects.select_related("edition")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    @admin.display(description="estado")
    def status_label(self, poll):
        return poll.status.label

    @admin.display(description="opciones", ordering="option_count")
    def option_count(self, poll):
        return poll.option_count

    @admin.display(description="votos", ordering="vote_count")
    def vote_count(self, poll):
        return poll.vote_count

    @admin.display(description="conteo")
    def results_links(self, poll):
        if not poll.pk:
            return "Disponible después de guardar la votación."
        return format_html(
            '<a href="{}">Ver la página de resultados</a><br>'
            '<a href="{}">Exportar resultados (CSV)</a>',
            reverse("festival:poll-results", args=[poll.slug]),
            reverse("admin:festival_poll_results_csv", args=[poll.pk]),
        )


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("receipt", "cast_at", "voter", "edition", "category", "option")
    list_filter = ("edition", "category")
    list_select_related = ("voter", "edition", "category", "option")
    search_fields = ("receipt", "voter__email", "option__name")
    fields = ("receipt", "cast_at", "voter", "edition", "category", "option")
    readonly_fields = ("receipt", "cast_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogEntry)
class ChangeLogAdmin(admin.ModelAdmin):
    list_display = ("action_time", "user", "action_label", "content_type", "object_repr", "detail")
    list_filter = ("action_flag", "content_type")
    list_select_related = ("user", "content_type")
    search_fields = ("object_repr", "change_message", "user__email")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="acción", ordering="action_flag")
    def action_label(self, entry):
        return ACTION_LABELS[entry.action_flag]

    @admin.display(description="detalle")
    def detail(self, entry):
        return entry.get_change_message()
