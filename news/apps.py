"""Register the news Django application."""

from django.apps import AppConfig


class NewsConfig(AppConfig):
    """Configure the news application and its default primary keys."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "news"

    def ready(self):
        """Connect role synchronization after Django has loaded the models."""
        from . import signals  # noqa: F401
