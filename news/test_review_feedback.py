"""Exercise the review corrections through registration and publication views."""

from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from .models import (
    Article,
    ApprovedArticleLog,
    Profile,
    Publisher,
    PublicationEmail,
)

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class ReviewFeedbackTests(TestCase):
    """Protect independent publishing, publisher ownership and email identities."""

    def setUp(self):
        """Create separate active accounts and two publisher organizations."""
        self.users = {}
        for name, role in (
            ("reader", "reader"),
            ("writer", "journalist"),
            ("editor", "editor"),
            ("othereditor", "editor"),
            ("otherwriter", "journalist"),
        ):
            user = User.objects.create_user(name, name + "@example.com")
            Profile.objects.create(user=user, role=role)
            self.users[name] = user
        self.publisher = Publisher.objects.create(name="Daily News")
        self.publisher.editors.add(self.users["editor"])
        self.publisher.journalists.add(self.users["writer"])
        self.draft = Article.objects.create(
            title="Independent report",
            summary="Summary",
            body="Story",
            author=self.users["writer"],
        )

    def test_registration_rejects_email_case_and_whitespace_duplicates(self):
        """Show useful form errors and never create duplicate subscriber accounts."""
        for email in (
            "reader@example.com",
            "READER@EXAMPLE.COM",
            " reader@example.com ",
        ):
            response = self.client.post(
                "/register/",
                {
                    "username": "duplicate",
                    "email": email,
                    "role": "reader",
                    "password1": "StrongExample913!",
                    "password2": "StrongExample913!",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("email", response.context["form"].errors)
        self.assertFalse(User.objects.filter(username="duplicate").exists())

    def test_database_rejects_duplicate_normalized_email(self):
        """Back form validation with a unique index to protect concurrent saves."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("duplicate", "READER@EXAMPLE.COM")
        user = User.objects.create_user("new", " NEW@Example.COM ")
        self.assertEqual(user.email, "new@example.com")

    def test_editor_creates_and_manages_publisher_without_admin(self):
        """Create an organization and allow its journalists to select it."""
        editor = self.users["editor"]
        self.assertFalse(editor.is_staff)
        self.client.force_login(editor)
        response = self.client.post(
            "/publishers/",
            {
                "name": "Community News",
                "journalists": [self.users["writer"].pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        publisher = Publisher.objects.get(name="Community News")
        self.assertTrue(publisher.editors.filter(pk=editor.pk).exists())
        self.client.force_login(self.users["writer"])
        response = self.client.get("/article/new/")
        self.assertIn(
            publisher, response.context["form"].fields["publisher"].queryset
        )
        for role in ("writer", "reader"):
            self.client.force_login(self.users[role])
            self.assertEqual(
                self.client.post("/publishers/", {"name": "Bad"}).status_code,
                403,
            )
        self.client.force_login(self.users["othereditor"])
        self.assertEqual(
            self.client.post(
                f"/publishers/{publisher.pk}/", {"name": "Takeover"}
            ).status_code,
            404,
        )
        self.client.force_login(editor)
        response = self.client.post(
            f"/publishers/{publisher.pk}/",
            {
                "name": "Renamed News",
                "journalists": [self.users["otherwriter"].pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        publisher.refresh_from_db()
        self.assertEqual(publisher.name, "Renamed News")
        self.assertFalse(
            publisher.journalists.filter(pk=self.users["writer"].pk).exists()
        )

    def test_publisher_members_cannot_be_forged_as_readers(self):
        """Reject submitted non-journalist membership IDs."""
        self.client.force_login(self.users["editor"])
        response = self.client.post(
            "/publishers/",
            {
                "name": "Invalid",
                "journalists": [self.users["reader"].pk],
            },
        )
        self.assertIn("journalists", response.context["form"].errors)
        self.assertFalse(Publisher.objects.filter(name="Invalid").exists())

    @patch("news.views.post_approved_article", return_value=True)
    def test_independent_author_publishes_and_notifies_once(self, post):
        """Only the owner self-publishes; repeat requests do not duplicate mail."""
        from django.core import mail

        self.users["reader"].profile.journalists.add(self.users["writer"])
        url = f"/article/{self.draft.pk}/approve/"
        for name in ("reader", "editor", "otherwriter"):
            self.client.force_login(self.users[name])
            self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.users["writer"])
        self.assertContains(
            self.client.get(self.draft.get_absolute_url()), "Publish article"
        )
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.draft.refresh_from_db()
        self.assertTrue(self.draft.approved)
        self.assertIsNone(self.draft.approved_by)
        self.client.post(url)
        self.assertEqual(len(mail.outbox), 1)
        self.client.post(
            f"/article/{self.draft.pk}/edit/",
            {
                "title": "Revised",
                "summary": "Summary",
                "body": "New body",
                "category": "world",
                "publisher": "",
            },
        )
        self.draft.refresh_from_db()
        self.assertFalse(self.draft.approved)
        self.assertContains(
            self.client.get(self.draft.get_absolute_url()), "Publish article"
        )

    def test_publisher_editor_permissions_apply_to_html_and_api(self):
        """Unrelated editors cannot see drafts, edit, approve or delete them."""
        self.draft.publisher = self.publisher
        self.draft.save()
        self.client.force_login(self.users["othereditor"])
        self.assertEqual(
            self.client.get(self.draft.get_absolute_url()).status_code, 404
        )
        self.assertNotContains(
            self.client.get("/dashboard/"), self.draft.title
        )
        for action in ("edit", "delete", "approve"):
            self.assertEqual(
                self.client.post(
                    f"/article/{self.draft.pk}/{action}/"
                ).status_code,
                403,
            )
        client = APIClient()
        client.force_authenticate(self.users["othereditor"])
        self.assertEqual(
            client.post(f"/api/articles/{self.draft.pk}/approve/").status_code,
            403,
        )
        client.force_authenticate(self.users["writer"])
        self.assertEqual(
            client.post(f"/api/articles/{self.draft.pk}/approve/").status_code,
            403,
        )

    @patch("news.api.post_approved_article", return_value=True)
    def test_independent_api_publish(self, post):
        """Apply the same independent ownership rule to API publication."""
        client = APIClient()
        client.force_authenticate(self.users["editor"])
        self.assertEqual(
            client.post(f"/api/articles/{self.draft.pk}/approve/").status_code,
            403,
        )
        client.force_authenticate(self.users["writer"])
        self.assertEqual(
            client.post(f"/api/articles/{self.draft.pk}/approve/").status_code,
            200,
        )
        self.draft.refresh_from_db()
        self.assertTrue(self.draft.approved)

    def test_retry_control_only_for_pending_delivery(self):
        """Distinguish publication success from a remaining delivery problem."""
        self.draft.approved = True
        self.draft.save()
        self.client.force_login(self.users["writer"])
        self.assertContains(
            self.client.get(self.draft.get_absolute_url()),
            "Retry pending delivery",
        )
        ApprovedArticleLog.objects.create(article=self.draft)
        response = self.client.get(self.draft.get_absolute_url())
        self.assertNotContains(response, "Retry pending delivery")
        self.assertContains(response, "No retry is needed")
        PublicationEmail.objects.create(
            article=self.draft,
            reader=self.users["reader"],
            recipient="reader@example.com",
        )
        self.assertContains(
            self.client.get(self.draft.get_absolute_url()),
            "Retry pending delivery",
        )

    def test_article_subscriptions_are_scoped_and_idempotent(self):
        """Follow article sources without disturbing existing subscriptions."""
        self.draft.publisher = self.publisher
        self.draft.approved = True
        self.draft.save()
        self.client.force_login(self.users["reader"])
        url = f"/article/{self.draft.pk}/subscribe/"
        self.assertEqual(self.client.get(url).status_code, 405)
        for source in ("journalist", "publisher"):
            for _ in range(2):
                self.assertEqual(
                    self.client.post(
                        url, {"source": source, "action": "subscribe"}
                    ).status_code,
                    302,
                )
        profile = self.users["reader"].profile
        self.assertEqual(profile.journalists.count(), 1)
        self.assertEqual(profile.publishers.count(), 1)
        self.assertContains(
            self.client.get(self.draft.get_absolute_url()), "Unsubscribe from"
        )
        self.client.post(
            url, {"source": "journalist", "action": "unsubscribe"}
        )
        self.assertFalse(profile.journalists.exists())
        self.assertTrue(profile.publishers.exists())
        self.client.force_login(self.users["writer"])
        self.assertEqual(
            self.client.post(
                url, {"source": "journalist", "action": "subscribe"}
            ).status_code,
            403,
        )
        self.draft.approved = False
        self.draft.save()
        self.client.force_login(self.users["reader"])
        self.assertEqual(
            self.client.post(
                url, {"source": "journalist", "action": "subscribe"}
            ).status_code,
            404,
        )
