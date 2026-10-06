"""Extend Django users without replacing existing account tables or passwords."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Expose role-specific news relationships through a normalized profile.

    Reuse the original auth_user table so existing article ownership and password
    hashes remain valid. Reader subscription joins live on the one-to-one profile;
    empty/nonapplicable relationships are exposed as None for other roles.
    """

    email = models.EmailField(
        "email address", unique=True, null=True, blank=True
    )

    def clean(self):
        """Use a consistent identity for email validation and storage."""
        super().clean()
        self.email = (self.email or "").strip().lower() or None

    def save(self, *args, **kwargs):
        """Normalize email on ordinary account writes, including manager creates."""
        self.email = (self.email or "").strip().lower() or None
        super().save(*args, **kwargs)

    class Meta(AbstractUser.Meta):
        """Reuse legacy tables and support the staged existing-database upgrade."""

        db_table = "auth_user"
        swappable = "AUTH_USER_MODEL"

    @property
    def role(self):
        """Return the assigned role, or None for an unassigned admin account."""
        profile = getattr(self, "profile", None)
        return profile.role if profile else None

    @property
    def publisher_subscriptions(self):
        """Return the reader's publisher relationship, or None for other roles."""
        return self.profile.publishers if self.role == "reader" else None

    @property
    def journalist_subscriptions(self):
        """Return the reader's journalist relationship, or None for other roles."""
        return self.profile.journalists if self.role == "reader" else None

    @property
    def independent_articles(self):
        """Return independent articles for journalists, or None for other roles."""
        return (
            self.articles.filter(publisher__isnull=True)
            if self.role == "journalist"
            else None
        )

    @property
    def independent_newsletters(self):
        """Return independent newsletters for journalists, or None otherwise."""
        return (
            self.newsletters.filter(publisher__isnull=True)
            if self.role == "journalist"
            else None
        )
