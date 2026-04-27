from django import forms
from .models import Knowledge


class KnowledgeForm(forms.ModelForm):
    class Meta:
        model = Knowledge
        fields = ['title', 'description', 'file', 'external_link']

    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        link = cleaned_data.get('external_link', '').strip()
        if not file and not link:
            raise forms.ValidationError('Добавьте файл или ссылку — хотя бы одно поле обязательно.')
        return cleaned_data
