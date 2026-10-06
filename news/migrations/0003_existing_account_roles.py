"""Give existing accounts roles without discarding their articles or bookmarks."""

from django.db import migrations
from django.conf import settings


def assign_existing_roles(apps, schema_editor):
    """Assign existing authors as journalists and other accounts as readers."""
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Profile = apps.get_model("news", "Profile")
    Article = apps.get_model("news", "Article")
    alias = schema_editor.connection.alias
    authors = set(Article.objects.using(alias).values_list("author_id", flat=True))
    for user in User.objects.using(alias).all().iterator():
        Profile.objects.using(alias).get_or_create(
            user_id=user.pk,
            defaults={"role": "journalist" if user.pk in authors else "reader"},
        )


class Migration(migrations.Migration):
    """Backfill profiles; retain them on reversal to avoid deleting user data."""

    dependencies = [("news", "0002_article_approved_article_approved_at_and_more")]
    operations = [
        migrations.RunPython(assign_existing_roles, migrations.RunPython.noop)
    ]
