from django.core.exceptions import ObjectDoesNotExist


def org_slug(request):
    """Кладёт org_slug в контекст каждого шаблона автоматически.

    На страницах вне org-контекста (/accounts/...) берётся организация пользователя,
    чтобы общий каркас (логотип, меню, футер) мог строить ссылки. Пустая строка —
    организации нет: меню показывает только «Мой профиль» и «Настройки».
    """
    try:
        slug = request.resolver_match.kwargs.get('org_slug', '')
    except AttributeError:
        slug = ''
    if not slug:
        try:
            organization = request.user.profile.organization
            slug = organization.slug if organization else ''
        except (AttributeError, ObjectDoesNotExist):
            slug = ''
    return {'org_slug': slug}
