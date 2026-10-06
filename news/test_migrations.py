"""Verify that the role migration preserves legacy account and article data."""

from django.db import connection
from django.conf import settings
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ExistingAccountMigrationTests(TransactionTestCase):
    """Exercise the upgrade path from the original news schema."""

    def test_existing_authors_and_readers_receive_roles(self):
        """Backfill roles, preserve content and require approval for legacy stories."""
        executor = MigrationExecutor(connection)
        executor.migrate(
            [("news", "0001_initial"), ("accounts", "0001_initial")]
        )
        try:
            state = executor.loader.project_state(
                [("news", "0001_initial")]
            ).apps
            User = state.get_model(*settings.AUTH_USER_MODEL.split("."))
            Article = state.get_model("news", "Article")
            author = User.objects.create(username="legacy_author")
            reader = User.objects.create(username="legacy_reader")
            story = Article.objects.create(
                title="Legacy",
                summary="Summary",
                body="Body",
                author_id=author.pk,
            )
            executor = MigrationExecutor(connection)
            executor.migrate([("news", "0003_existing_account_roles")])
            apps = executor.loader.project_state(
                [("news", "0003_existing_account_roles")]
            ).apps
            Profile = apps.get_model("news", "Profile")
            self.assertEqual(
                Profile.objects.get(user_id=author.pk).role, "journalist"
            )
            self.assertEqual(
                Profile.objects.get(user_id=reader.pk).role, "reader"
            )
            preserved = apps.get_model("news", "Article").objects.get(
                pk=story.pk
            )
            self.assertEqual(preserved.body, "Body")
            self.assertFalse(preserved.approved)
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
