"""Configure the custom account application."""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Keep the legacy integer account primary keys."""

    default_auto_field = "django.db.models.AutoField"
    name = "accounts"
