from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import MIN_OPTIONS_TO_PUBLISH, Option, PollStatus, Vote

STATUS_REFUSALS = {
    PollStatus.UPCOMING: "Esta votación todavía no abre.",
    PollStatus.CLOSED: "Esta votación ya cerró y no recibe más votos.",
}


def already_voted_message(vote):
    return (
        f"Ya votaste en la categoría {vote.category.name} de esta edición, por "
        f"{vote.option.name}. Se permite un voto por categoría."
    )


def vote_refusal(poll, own_vote):
    if poll.status in STATUS_REFUSALS:
        return STATUS_REFUSALS[poll.status]
    if own_vote:
        return already_voted_message(own_vote)
    return None


class VoteForm(forms.Form):
    option = forms.ModelChoiceField(
        queryset=Option.objects.none(),
        error_messages={
            "required": "Elige una opción para continuar.",
            "invalid_choice": "La opción enviada no pertenece a esta votación.",
        },
    )

    def __init__(self, *args, poll, voter, **kwargs):
        super().__init__(*args, **kwargs)
        self.poll = poll
        self.voter = voter
        self.fields["option"].queryset = poll.options.select_related("poll__category")

    def clean(self):
        cleaned_data = super().clean()
        own_vote = (
            Vote.objects.in_category(self.voter, self.poll.category)
            .select_related("category", "option")
            .first()
        )
        refusal = vote_refusal(self.poll, own_vote)
        if refusal:
            raise ValidationError(refusal)
        return cleaned_data


class OptionInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        self.check_options_with_votes()
        if not self.instance.is_published:
            return
        kept = [
            form
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        ]
        if len(kept) < MIN_OPTIONS_TO_PUBLISH:
            raise ValidationError(
                f"Para publicar la votación agrega al menos {MIN_OPTIONS_TO_PUBLISH} opciones."
            )

    def check_options_with_votes(self):
        saved = [form for form in self.forms if form.instance.pk and form.cleaned_data]
        voted = set(
            Vote.objects.filter(option__in=[form.instance.pk for form in saved]).values_list(
                "option_id", flat=True
            )
        )
        for form in saved:
            if form.instance.pk not in voted:
                continue
            if form.cleaned_data.get("DELETE") or "name" in form.changed_data:
                raise ValidationError(
                    f"La opción «{form.initial['name']}» ya tiene votos y no se puede "
                    "renombrar ni borrar."
                )
