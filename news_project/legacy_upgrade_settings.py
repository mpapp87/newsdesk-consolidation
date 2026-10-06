"""Record the account bridge before changing an existing auth.User database.

Run only: manage.py migrate accounts --settings=news_project.legacy_upgrade_settings
Then use the normal settings for all remaining migrations and application use.
"""

from .settings import *  # noqa: F403

AUTH_USER_MODEL = "auth.User"
