def org_slug(request):
    """Кладёт org_slug в контекст каждого шаблона автоматически."""
    try:
        slug = request.resolver_match.kwargs.get('org_slug', '')
    except AttributeError:
        slug = ''
    return {'org_slug': slug}
