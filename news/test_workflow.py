"""Verify role boundaries, editorial approval, email retries and template discovery."""

from pathlib import Path
from smtplib import SMTPException
from unittest.mock import patch
from django.contrib.auth import get_user_model

User = get_user_model()
from django.core import mail
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Article, Profile, Publisher, PublicationEmail


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class RoleWorkflowTests(TestCase):
    """Exercise the reader, journalist and editor journeys through real views."""

    def setUp(self):
        """Create independent role accounts, an organization and a pending story."""
        self.users = {}
        for role in ("reader", "journalist", "editor"):
            user = User.objects.create_user(
                role, f"{role}@example.com", "ExamplePass923!"
            )
            Profile.objects.create(user=user, role=role)
            self.users[role] = user
        self.publisher = Publisher.objects.create(name="Example News")
        self.publisher.journalists.add(self.users["journalist"])
        self.publisher.editors.add(self.users["editor"])
        self.article = Article.objects.create(
            title="Pending story",
            summary="Summary",
            body="Body",
            author=self.users["journalist"],
            publisher=self.publisher,
        )
        self.payload = {
            "title": "Updated story",
            "summary": "Summary",
            "body": "Body",
            "category": "world",
            "publisher": self.publisher.pk,
        }

    def test_registration_persists_each_role_without_staff_access(self):
        """Register every supported role without granting Django admin access."""
        for role in self.users:
            with self.subTest(role=role):
                self.client.logout()
                response = self.client.post(
                    reverse("news:register"),
                    {
                        "username": "new_" + role,
                        "email": role + "2@example.com",
                        "role": role,
                        "password1": "StrongSecret498!",
                        "password2": "StrongSecret498!",
                        "is_staff": "on",
                    },
                )
                self.assertEqual(response.status_code, 302)
                user = User.objects.get(username="new_" + role)
                self.assertEqual(user.profile.role, role)
                self.assertFalse(user.is_staff)
                self.assertFalse(user.is_superuser)

    def test_invalid_or_missing_role_is_rejected(self):
        """Reject unsupported roles and registration without a role selection."""
        for role in ("", "publisher", "admin"):
            response = self.client.post(
                reverse("news:register"),
                {
                    "username": "invalid",
                    "email": "a@example.com",
                    "role": role,
                    "password1": "StrongSecret498!",
                    "password2": "StrongSecret498!",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("role", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="invalid").exists())

    def test_reader_cannot_submit_edit_delete_or_approve(self):
        """Reject reader writes even when they bypass navigation and POST directly."""
        self.client.force_login(self.users["reader"])
        for route in (
            "article_create",
            "article_update",
            "article_delete",
            "approve_article",
        ):
            args = [] if route == "article_create" else [self.article.pk]
            self.assertEqual(
                self.client.post(
                    reverse("news:" + route, args=args), self.payload
                ).status_code,
                403,
            )
        self.article.refresh_from_db()
        self.assertFalse(self.article.approved)

    def test_journalist_ownership_and_approval_are_enforced(self):
        """Allow own drafts but reject another journalist's content and approval."""
        other = User.objects.create_user("otherwriter")
        Profile.objects.create(user=other, role="journalist")
        self.client.force_login(other)
        for route in ("article_update", "article_delete", "approve_article"):
            self.assertEqual(
                self.client.post(
                    reverse("news:" + route, args=[self.article.pk]),
                    self.payload,
                ).status_code,
                403,
            )
        self.client.force_login(self.users["journalist"])
        response = self.client.post(
            reverse("news:article_create"),
            {**self.payload, "approved": "on", "author": other.pk},
        )
        self.assertEqual(response.status_code, 302)
        created = Article.objects.get(title="Updated story")
        self.assertFalse(created.approved)
        self.assertEqual(created.author, self.users["journalist"])
        self.assertEqual(
            self.client.post(
                reverse("news:approve_article", args=[created.pk])
            ).status_code,
            403,
        )

    def test_unrelated_publisher_is_rejected(self):
        """Prevent a journalist from submitting under an unrelated publisher."""
        unrelated = Publisher.objects.create(name="Unrelated")
        self.client.force_login(self.users["journalist"])
        response = self.client.post(
            reverse("news:article_create"),
            {**self.payload, "publisher": unrelated.pk},
        )
        self.assertIn("publisher", response.context["form"].errors)

    def test_drafts_are_hidden_from_public_readers_and_other_journalists(self):
        """Hide pending content from list, detail, comments and saved-story writes."""
        self.assertNotContains(
            self.client.get(reverse("news:home")), self.article.title
        )
        self.assertEqual(
            self.client.get(self.article.get_absolute_url()).status_code, 404
        )
        self.client.force_login(self.users["reader"])
        self.assertEqual(
            self.client.get(self.article.get_absolute_url()).status_code, 404
        )
        for route in ("add_comment", "toggle_save"):
            self.assertEqual(
                self.client.post(
                    reverse("news:" + route, args=[self.article.pk]),
                    {"body": "Hidden"},
                ).status_code,
                404,
            )
        self.client.force_login(self.users["journalist"])
        self.assertEqual(
            self.client.get(self.article.get_absolute_url()).status_code, 200
        )

    def test_approval_emails_matching_readers_once_privately(self):
        """Deduplicate overlapping subscriptions and exclude non-subscribers."""
        profile = self.users["reader"].profile
        profile.journalists.add(self.users["journalist"])
        profile.publishers.add(self.publisher)
        publisher_reader = User.objects.create_user(
            "publisherreader", "publisherreader@example.com"
        )
        second = Profile.objects.create(user=publisher_reader)
        second.publishers.add(self.publisher)
        self.client.force_login(self.users["editor"])
        url = reverse("news:approve_article", args=[self.article.pk])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.article.refresh_from_db()
        self.assertTrue(self.article.approved)
        self.assertEqual(self.article.approved_by, self.users["editor"])
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(
            {tuple(m.to) for m in mail.outbox},
            {("reader@example.com",), ("publisherreader@example.com",)},
        )
        self.assertIn(self.article.get_absolute_url(), mail.outbox[0].body)
        self.assertIn(self.article.title, mail.outbox[0].body)
        self.assertIn(self.article.body, mail.outbox[0].body)
        self.client.post(url)
        self.assertEqual(len(mail.outbox), 2)
        self.client.logout()
        self.assertContains(
            self.client.get(reverse("news:home")), self.article.title
        )

    def test_smtp_failure_preserves_approval_and_can_be_retried(self):
        """Keep failed notifications queued without duplicating successful mail."""
        self.users["reader"].profile.journalists.add(self.users["journalist"])
        self.client.force_login(self.users["editor"])
        url = reverse("news:approve_article", args=[self.article.pk])
        with patch(
            "django.core.mail.send_mail",
            side_effect=SMTPException("Unavailable"),
        ):
            response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.article.refresh_from_db()
        self.assertTrue(self.article.approved)
        self.assertIsNone(PublicationEmail.objects.get().sent_at)
        self.client.post(url)
        self.assertIsNotNone(PublicationEmail.objects.get().sent_at)
        self.assertEqual(len(mail.outbox), 1)

    def test_unsubscribe_prevents_retry_delivery(self):
        """Respect a reader's subscription removal before a failed email is retried."""
        self.users["reader"].profile.journalists.add(self.users["journalist"])
        self.client.force_login(self.users["editor"])
        url = reverse("news:approve_article", args=[self.article.pk])
        with patch(
            "django.core.mail.send_mail", side_effect=OSError("Offline")
        ):
            self.client.post(url)
        self.users["reader"].profile.journalists.clear()
        self.client.post(url)
        self.assertEqual(len(mail.outbox), 0)

    def test_editing_requires_fresh_approval(self):
        """Remove public visibility when an approved story changes."""
        self.article.approved = True
        self.article.save()
        self.client.force_login(self.users["journalist"])
        self.client.post(
            reverse("news:article_update", args=[self.article.pk]),
            self.payload,
        )
        self.article.refresh_from_db()
        self.assertFalse(self.article.approved)
        self.assertIsNone(self.article.approved_by)

    def test_editor_can_manage_content_but_cannot_submit(self):
        """Give editors review, edit and delete access without journalist authorship."""
        self.client.force_login(self.users["editor"])
        self.assertEqual(
            self.client.get(reverse("news:dashboard")).status_code, 200
        )
        self.assertEqual(
            self.client.post(
                reverse("news:article_update", args=[self.article.pk]),
                self.payload,
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(
                reverse("news:article_create"), self.payload
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("news:article_delete", args=[self.article.pk])
            ).status_code,
            302,
        )
        self.assertFalse(Article.objects.filter(pk=self.article.pk).exists())

    def test_role_specific_navigation_and_subscriptions(self):
        """Show role-appropriate links and reject attempted role changes in preferences."""
        self.client.force_login(self.users["reader"])
        response = self.client.get(reverse("news:home"))
        self.assertContains(response, "Subscriptions")
        self.assertNotContains(response, "Submit article")
        self.client.post(
            reverse("news:subscriptions"),
            {
                "journalists": [self.users["journalist"].pk],
                "publishers": [self.publisher.pk],
                "role": "editor",
            },
        )
        self.users["reader"].profile.refresh_from_db()
        self.assertEqual(self.users["reader"].profile.role, "reader")
        self.assertTrue(self.users["reader"].profile.publishers.exists())
        self.client.force_login(self.users["journalist"])
        self.assertContains(
            self.client.get(reverse("news:home")), "Submit article"
        )
        self.assertEqual(
            self.client.post(reverse("news:subscriptions"), {}).status_code,
            403,
        )

    def test_mutations_require_post(self):
        """Return method errors for approval, bookmark and comment GET requests."""
        self.client.force_login(self.users["editor"])
        for route in ("approve_article", "toggle_save", "add_comment"):
            self.assertEqual(
                self.client.get(
                    reverse("news:" + route, args=[self.article.pk])
                ).status_code,
                405,
            )

    def test_news_templates_are_loaded_from_application(self):
        """Resolve every news template inside the app while keeping auth shared."""
        root = Path(__file__).resolve().parent
        for name in (
            "home",
            "article_detail",
            "article_form",
            "article_confirm_delete",
            "external_news",
            "saved_articles",
            "dashboard",
            "subscriptions",
        ):
            self.assertEqual(
                Path(get_template(f"news/{name}.html").origin.name),
                root / "templates" / "news" / f"{name}.html",
            )
        self.assertEqual(
            Path(get_template("registration/register.html").origin.name),
            root.parent / "templates/registration/register.html",
        )
