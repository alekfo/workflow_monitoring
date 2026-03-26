from django import forms
from django.core import validators
from django.contrib.auth.models import User
from django.contrib.auth.models import Group
from django.forms.widgets import ClearableFileInput

from .models import Profile

class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = "bio", "agreement_accepted", "avatar"
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4, 'cols': 40}),
            'avatar': forms.ClearableFileInput(attrs={'class': 'form-control'})
        }
        labels = {
            'bio': 'О себе',
            'avatar': 'Аватарка'
        }
