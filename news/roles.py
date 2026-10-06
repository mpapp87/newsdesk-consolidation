"""Centralize role checks used by views, forms and navigation."""


def has_role(user, role):
    """Check a role without granting permissions to anonymous users.

    :param user: Django user or anonymous user from the current request.
    :param str role: Expected profile role: reader, journalist, or editor.
    :return: Whether the authenticated user has that profile role.
    :rtype: bool
    """
    return (
        user.is_authenticated and hasattr(user, "profile") and user.profile.role == role
    )


def can_edit(user, article):
    """Allow editors to manage articles and journalists to manage their own."""
    return has_role(user, "editor") or (
        has_role(user, "journalist") and article.author_id == user.pk
    )


def navigation(request):
    """Expose role-specific navigation flags without granting permissions."""
    return {
        f"is_{role}": has_role(request.user, role)
        for role in ("reader", "journalist", "editor")
    }
