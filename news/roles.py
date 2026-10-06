"""Centralize role checks used by views, forms and navigation."""


def has_role(user, role):
    """Return whether an authenticated user has the requested profile role."""
    return (
        user.is_authenticated
        and hasattr(user, "profile")
        and user.profile.role == role
    )


def can_edit(user, article):
    """Allow article owners and assigned publisher editors to manage stories."""
    if hasattr(article, "approved") and has_role(user, "editor"):
        return (
            bool(article.publisher_id)
            and article.publisher.editors.filter(pk=user.pk).exists()
        )
    return has_role(user, "editor") or (
        has_role(user, "journalist") and article.author_id == user.pk
    )


def navigation(request):
    """Expose role-specific navigation flags without granting permissions."""
    return {
        f"is_{role}": has_role(request.user, role)
        for role in ("reader", "journalist", "editor")
    }


def can_publish(user, article):
    """Let publisher editors approve, or independent journalists self-publish."""
    if article.publisher_id:
        return (
            has_role(user, "editor")
            and article.publisher.editors.filter(pk=user.pk).exists()
        )
    return has_role(user, "journalist") and article.author_id == user.pk
