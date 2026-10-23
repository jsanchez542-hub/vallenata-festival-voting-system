from django import forms
from django.contrib import admin
from django.db.models import Count

from .forms import OptionInlineFormSet
from .models import Category, Edition, Option, Poll, PollStatus


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
    fields = ("name", "detail", "position")

    def get_extra(self, request, obj=None, **kwargs):
        return 0 if obj else 2


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "status_label", "opens_at", "closes_at", "option_count")
    list_filter = (PollStatusFilter, "category__edition")
    list_select_related = ("category__edition",)
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [OptionInline]
    fieldsets = (
        (None, {"fields": ("category", "title", "slug", "description")}),
        ("Calendario", {"fields": ("opens_at", "closes_at", "is_published", "closed_early")}),
        (
            "Reglas",
            {
                "fields": (
                    "votes_per_voter",
                    "vote_period",
                    "results_visibility",
                    "requires_account",
                )
            },
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(option_count=Count("options"))

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
