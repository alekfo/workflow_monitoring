from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .models import Profile

class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ['bio', 'agreement_accepted', 'avatar_preview', 'avatar', 'knowledge_file_limit']
    readonly_fields = ['avatar_preview']

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-width: 150px; max-height: 150px;" />',
                obj.avatar.url
            )
        return "Нет аватарки"

class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]

# Отменяем стандартную регистрацию User и регистрируем кастомную
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
