"""Expose news records and organization membership in Django administration."""

from django.contrib import admin
from .models import Article, Comment, Profile, PublicationEmail, Publisher, SavedArticle


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Display articles read-only so admin edits cannot bypass editorial review."""

    list_display = ("title", "author", "approved", "publisher")

    def has_add_permission(self, request):
        """Require article submission through the journalist workflow."""
        return False

    def has_change_permission(self, request, obj=None):
        """Require content changes and approvals through the newsroom."""
        return False


@admin.register(PublicationEmail)
class PublicationEmailAdmin(admin.ModelAdmin):
    """Display notification delivery status without allowing manual fabrication."""

    list_display = ("article", "reader", "sent_at")

    def has_add_permission(self, request):
        """Only the publication service may create notification records."""
        return False

    def has_change_permission(self, request, obj=None):
        """Preserve notification delivery records as service-managed data."""
        return False


admin.site.register([Comment, SavedArticle, Profile, Publisher])
