from django.db.models import Prefetch
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from .models import Category, Poll


def option_payload(option):
    return {"id": option.pk, "name": option.name, "detail": option.detail}


def poll_payload(request, poll):
    return {
        "slug": poll.slug,
        "title": poll.title,
        "status": poll.status,
        "opens_at": timezone.localtime(poll.opens_at).isoformat(),
        "closes_at": timezone.localtime(poll.closes_at).isoformat(),
        "url": request.build_absolute_uri(poll.get_absolute_url()),
        "options": [option_payload(option) for option in poll.options.all()],
    }


def category_payload(request, category):
    edition = category.edition
    return {
        "id": category.pk,
        "name": category.name,
        "description": category.description,
        "edition": {"number": edition.number, "year": edition.year, "name": edition.name},
        "polls": [poll_payload(request, poll) for poll in category.polls.all()],
    }


@require_GET
def categories(request):
    published = Poll.objects.filter(is_published=True).prefetch_related("options")
    queryset = (
        Category.objects.active()
        .select_related("edition")
        .order_by("-edition__year", "position", "name")
        .prefetch_related(Prefetch("polls", queryset=published))
    )
    payload = [category_payload(request, category) for category in queryset]
    return JsonResponse(
        {"count": len(payload), "categories": payload}, json_dumps_params={"ensure_ascii": False}
    )
