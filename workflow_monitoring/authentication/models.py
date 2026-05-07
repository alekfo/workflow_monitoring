from django.db import models
from django.contrib.auth.models import User

def avatar_directory_path(instance: "Profile", filename: str) -> str:
    return "user/user_{pk}//avatar/{filename}".format(
        pk=instance.user.pk,
        filename=filename
    )

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    organization = models.ForeignKey(
        'signal1520.Organization',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members',
        verbose_name='Организация',
    )
    bio = models.TextField(max_length=500, blank=True)
    agreement_accepted = models.BooleanField(default=False)
    consent_given_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата согласия на обработку ПД')
    consent_ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP при согласии')
    consent_policy_version = models.CharField(max_length=20, null=True, blank=True, verbose_name='Версия политики')

    avatar = models.ImageField(null=True, blank=True, upload_to=avatar_directory_path)
    knowledge_file_limit = models.PositiveSmallIntegerField(
        'Лимит файлов инструкций',
        default=10,
    )

    class Meta:
        permissions = [
            ("can_view_users_list", "Может просматривать список пользователей"),
        ]