"""Verify that email uniqueness can be introduced without losing legacy users."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class EmailMigrationTests(TransactionTestCase):
    """Exercise duplicate rejection and normalization on real migration state."""

    def test_duplicates_stop_upgrade_and_can_be_corrected_without_data_loss(
        self,
    ):
        """Preserve identities, reject case variants and retain legacy empty emails."""
        executor = MigrationExecutor(connection)
        executor.migrate([("accounts", "0001_initial")])
        apps = executor.loader.project_state(
            [("accounts", "0001_initial")]
        ).apps
        User = apps.get_model("accounts", "User")
        first = User.objects.create(
            username="first", email="Example@example.com"
        )
        second = User.objects.create(
            username="second", email=" example@EXAMPLE.com "
        )
        empty = User.objects.create(username="empty", email="")
        try:
            with self.assertRaisesRegex(
                RuntimeError, "Duplicate account emails"
            ):
                MigrationExecutor(connection).migrate(
                    [("accounts", "0002_unique_email")]
                )
            self.assertEqual(User.objects.count(), 3)
            self.assertEqual(
                User.objects.get(pk=first.pk).email, "Example@example.com"
            )
        finally:
            User.objects.filter(pk=second.pk).update(
                email="different@example.com"
            )
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
        from django.contrib.auth import get_user_model

        CurrentUser = get_user_model()
        self.assertEqual(
            CurrentUser.objects.get(pk=first.pk).email, "example@example.com"
        )
        self.assertIsNone(CurrentUser.objects.get(pk=empty.pk).email)
        self.assertEqual(CurrentUser.objects.count(), 3)
