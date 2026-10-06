"""Synchronize profile roles with least-privilege Django permission groups."""

from django.apps import apps as current_apps
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.management import create_permissions
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver
from .models import Profile

ROLE_PERMISSIONS = {
    "reader": ["view_article", "view_newsletter"],
    "journalist": [
        f"{action}_{model}"
        for action in ("add", "view", "change", "delete")
        for model in ("article", "newsletter")
    ],
    "editor": [
        "view_article",
        "change_article",
        "delete_article",
        "add_newsletter",
        "view_newsletter",
        "change_newsletter",
        "delete_newsletter",
    ],
}


def assign_group(profile, using="default"):
    """Assign only the selected role group and clear inapplicable subscriptions."""
    groups = Group.objects.using(using)
    group, _ = groups.get_or_create(name=profile.role.title())
    profile.user.groups.remove(
        *groups.filter(name__in=[r.title() for r in ROLE_PERMISSIONS]).exclude(
            pk=group.pk
        )
    )
    profile.user.groups.add(group)
    if profile.role != "reader":
        profile.journalists.clear()
        profile.publishers.clear()


@receiver(post_save, sender=Profile)
def sync_profile_group(sender, instance, raw=False, using="default", **kwargs):
    """Keep registration and admin role changes synchronized with groups."""
    if not raw:
        assign_group(instance, using)


@receiver(post_migrate)
def initialize_role_groups(sender, using="default", **kwargs):
    """Create role permissions and backfill membership after migrations finish."""
    if sender.name != "news":
        return
    historical_apps = kwargs.get("apps")
    if historical_apps is not None:
        try:
            historical_apps.get_model("news", "Profile")
        except LookupError:
            return
    create_permissions(
        sender, verbosity=0, using=using, apps=historical_apps or current_apps
    )
    for role, codes in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.using(using).get_or_create(name=role.title())
        group.permissions.set(
            Permission.objects.using(using).filter(
                content_type__app_label="news", codename__in=codes
            )
        )
    for profile in Profile.objects.using(using).select_related("user").iterator():
        assign_group(profile, using)
