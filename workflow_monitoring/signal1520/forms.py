from django import forms
from .models import Knowledge


class ContactForm(forms.Form):
    name = forms.CharField(label='Имя', max_length=150)
    email = forms.EmailField(label='Email')
    message = forms.CharField(
        label='Описание проблемы',
        widget=forms.Textarea(attrs={'rows': 5}),
    )


class KnowledgeForm(forms.Form):
    title = forms.CharField(label='Название', max_length=200)
    description = forms.CharField(
        label='Описание', required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )
    file = forms.FileField(label='Файл', required=False)
    existing_knowledge = forms.ModelChoiceField(
        queryset=Knowledge.objects.none(),
        required=False,
        label='Выбрать из существующих',
        empty_label='— не выбрано —',
    )
    external_link = forms.URLField(label='Ссылка на ресурс', required=False)

    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        existing = cleaned_data.get('existing_knowledge')
        link = cleaned_data.get('external_link', '').strip()

        if file and existing:
            raise forms.ValidationError(
                'Нельзя одновременно загрузить файл и выбрать из существующих.'
            )
        if not file and not existing and not link:
            raise forms.ValidationError(
                'Добавьте файл, выберите из существующих или укажите ссылку.'
            )
        return cleaned_data
