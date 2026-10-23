from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import MIN_OPTIONS_TO_PUBLISH


class OptionInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
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
