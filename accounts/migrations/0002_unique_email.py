"""Normalize existing addresses before adding the unique email constraint."""

from django.db import migrations, models


def normalize_emails(apps, schema_editor):
    """Stop safely on duplicate addresses rather than deleting or merging users."""
    User = apps.get_model("accounts", "User")
    users = list(User.objects.using(schema_editor.connection.alias).all())
    seen = set()
    for user in users:
        email = (user.email or "").strip().lower()
        if email and email in seen:
            raise RuntimeError(
                "Duplicate account emails exist. Resolve duplicate addresses in "
                "Django admin, then run migrate again. No accounts were removed."
            )
        if email:
            seen.add(email)
    for user in users:
        User.objects.using(schema_editor.connection.alias).filter(
            pk=user.pk
        ).update(email=(user.email or "").strip().lower() or None)


class Migration(migrations.Migration):
    """Allow legacy empty addresses while enforcing unique nonempty emails."""

    dependencies = [("accounts", "0001_initial")]
    operations = [
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                "email address", max_length=254, blank=True, null=True
            ),
        ),
        migrations.RunPython(normalize_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                "email address",
                max_length=254,
                blank=True,
                null=True,
                unique=True,
            ),
        ),
    ]
