from django.db import models
from django.contrib.auth.models import User

def avatar_directory_path(instance: "Profile", filename: str) -> str:
    return "user/user_{pk}//avatar/{filename}".format(
        pk=instance.user.pk,
        filename=filename
    )

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(max_length=500, blank=True)
    agreement_accepted = models.BooleanField(default=False)

    avatar = models.ImageField(null=True, blank=True, upload_to=avatar_directory_path)
    knowledge_file_limit = models.PositiveSmallIntegerField(
        'Лимит файлов инструкций',
        default=10,
    )

    class Meta:
        permissions = [
            ("can_view_users_list", "Может просматривать список пользователей"),
        ]