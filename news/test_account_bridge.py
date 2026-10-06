"""Check the documented upgrade in fresh processes against a legacy database."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
from django.test import SimpleTestCase


class AccountBridgeTests(SimpleTestCase):
    """Verify that swapping the account model preserves stored account identity."""

    def test_legacy_auth_tables_survive_staged_upgrade(self):
        """Upgrade real legacy tables without copying accounts or losing hashes."""
        root = Path(__file__).resolve().parent.parent
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            database = str(temp / "legacy.sqlite3")
            common = f"\nDATABASES = {{'default': {{'ENGINE': 'django.db.backends.sqlite3', 'NAME': {database!r}}}}}\nEMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'\n"
            (temp / "old_settings.py").write_text(
                "from news_project.legacy_upgrade_settings import *\nINSTALLED_APPS = [a for a in INSTALLED_APPS if a != 'accounts']\n"
                + common
            )
            (temp / "bridge_settings.py").write_text(
                "from news_project.legacy_upgrade_settings import *\n" + common
            )
            (temp / "new_settings.py").write_text(
                "from news_project.settings import *\n" + common
            )
            env = {**os.environ, "PYTHONPATH": str(temp) + os.pathsep + str(root)}
            commands = [
                ["migrate", "auth", "--settings=old_settings", "--noinput"],
                ["migrate", "news", "0003", "--settings=old_settings", "--noinput"],
                [
                    "shell",
                    "--settings=old_settings",
                    "-c",
                    "from django.contrib.auth import get_user_model; from news.models import Profile, Article; u=get_user_model().objects.create_user('legacy', password='LegacyPass321!'); Profile.objects.create(user=u, role='journalist'); Article.objects.create(title='Keep me', body='Saved content', author=u)",
                ],
                ["migrate", "accounts", "0001", "--settings=bridge_settings", "--noinput"],
                ["migrate", "--settings=new_settings", "--noinput"],
                [
                    "shell",
                    "--settings=new_settings",
                    "-c",
                    "from django.contrib.auth import get_user_model; from news.models import Article; u=get_user_model().objects.get(username='legacy'); assert u.check_password('LegacyPass321!'); assert u.role == 'journalist'; assert Article.objects.get(title='Keep me').author_id == u.pk; assert u.groups.filter(name='Journalist').exists(); assert u._meta.label == 'accounts.User'",
                ],
            ]
            for command in commands:
                result = subprocess.run(
                    [sys.executable, str(root / "manage.py"), *command],
                    cwd=root,
                    env=env,
                    text=True,
                    capture_output=True,
                    timeout=40,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
