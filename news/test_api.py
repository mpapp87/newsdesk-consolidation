"""Exercise token authentication, subscriptions, newsletters and publication APIs."""

from unittest.mock import patch
import requests
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from .models import Article, ApprovedArticleLog, Newsletter, Profile, Publisher
from .services import post_approved_article


@override_settings(
    APPROVAL_API_KEY="test-service-key",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class NewsAPITests(TestCase):
    """Verify successful and denied requests through real token authentication."""

    def setUp(self):
        """Create distinct roles, overlapping follows and approved/draft stories."""
        self.client = APIClient()
        self.users = {}
        for name, role in [
            ("reader", "reader"),
            ("writer", "journalist"),
            ("other", "journalist"),
            ("editor", "editor"),
        ]:
            user = get_user_model().objects.create_user(
                name, name + "@example.com", "TestPass149!"
            )
            Profile.objects.create(user=user, role=role)
            self.users[name] = user
        self.publisher = Publisher.objects.create(name="Daily")
        self.publisher.journalists.add(self.users["writer"])
        self.publisher.editors.add(self.users["editor"])
        self.story = Article.objects.create(
            title="Approved",
            summary="Summary",
            body="Body",
            author=self.users["writer"],
            publisher=self.publisher,
            approved=True,
        )
        self.draft = Article.objects.create(
            title="Draft", body="Hidden", author=self.users["writer"]
        )
        self.unrelated = Article.objects.create(
            title="Other", body="Other", author=self.users["other"], approved=True
        )
        self.payload = {
            "title": "New story",
            "content": "News content",
            "publisher": self.publisher.pk,
        }

    def authenticate(self, name):
        """Set an actual DRF token header rather than bypassing authentication."""
        token, _ = Token.objects.get_or_create(user=self.users[name])
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def test_token_login_and_missing_or_invalid_authentication(self):
        """Reject unauthenticated API access and issue tokens for valid passwords."""
        self.assertEqual(self.client.get("/api/articles/").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid")
        self.assertEqual(self.client.get("/api/articles/").status_code, 401)
        self.client.credentials()
        self.assertEqual(
            self.client.post(
                "/api/token/", {"username": "reader", "password": "wrong"}
            ).status_code,
            400,
        )
        response = self.client.post(
            "/api/token/", {"username": "reader", "password": "TestPass149!"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("token", response.data)

    def test_subscription_feed_is_scoped_and_deduplicated(self):
        """Return a reader's approved follows only, even with supplied user IDs."""
        self.authenticate("reader")
        self.assertEqual(self.client.get("/api/articles/subscribed/").data, [])
        profile = self.users["reader"].profile
        profile.journalists.add(self.users["writer"])
        profile.publishers.add(self.publisher)
        response = self.client.get("/api/articles/subscribed/?user=999")
        self.assertEqual([item["id"] for item in response.data], [self.story.pk])
        self.assertNotIn("email", response.data[0]["author"])
        self.authenticate("writer")
        self.assertEqual(self.client.get("/api/articles/subscribed/").status_code, 403)

    def test_only_journalists_create_and_cannot_spoof_approval(self):
        """Keep submitted authorship and approval flags under server control."""
        for role in ("reader", "editor"):
            self.authenticate(role)
            self.assertEqual(
                self.client.post("/api/articles/", self.payload).status_code, 403
            )
        self.authenticate("writer")
        response = self.client.post(
            "/api/articles/",
            {**self.payload, "approved": True, "author": self.users["other"].pk},
        )
        self.assertEqual(response.status_code, 201)
        story = Article.objects.get(pk=response.data["id"])
        self.assertEqual(story.author, self.users["writer"])
        self.assertFalse(story.approved)
        self.assertEqual(story.body, "News content")
        self.assertEqual(
            self.client.post("/api/articles/", {"title": ""}).status_code, 400
        )
        self.authenticate("other")
        self.assertEqual(
            self.client.post("/api/articles/", self.payload).status_code, 400
        )

    def test_article_visibility_update_and_delete_permissions(self):
        """Protect drafts and reject reader or non-owner edits and deletion."""
        self.authenticate("reader")
        self.assertEqual(
            self.client.get(f"/api/articles/{self.draft.pk}/").status_code, 404
        )
        for role in ("reader", "other"):
            self.authenticate(role)
            self.assertEqual(
                self.client.put(
                    f"/api/articles/{self.story.pk}/", self.payload
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.delete(f"/api/articles/{self.story.pk}/").status_code, 403
            )
        self.authenticate("writer")
        self.assertEqual(
            self.client.put(
                f"/api/articles/{self.story.pk}/", self.payload
            ).status_code,
            200,
        )
        self.story.refresh_from_db()
        self.assertFalse(self.story.approved)
        self.authenticate("editor")
        self.assertEqual(
            self.client.delete(f"/api/articles/{self.story.pk}/").status_code, 204
        )

    @patch("news.services.requests.post")
    def test_editor_approval_emails_and_posts_to_local_api(self, post):
        """Deliver reader mail and make the required requests-module POST."""
        post.return_value.status_code = 201
        post.return_value.json.return_value = {
            "logged": True,
            "article_id": self.draft.pk,
        }
        self.users["reader"].profile.journalists.add(self.users["writer"])
        for role in ("reader", "writer"):
            self.authenticate(role)
            self.assertEqual(
                self.client.post(f"/api/articles/{self.draft.pk}/approve/").status_code,
                403,
            )
        self.authenticate("editor")
        response = self.client.post(f"/api/articles/{self.draft.pk}/approve/")
        self.assertTrue(response.data["api_logged"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(post.call_args.kwargs["json"], {"article_id": self.draft.pk})
        self.assertEqual(
            post.call_args.kwargs["headers"], {"X-Approval-Key": "test-service-key"}
        )
        self.client.post(f"/api/articles/{self.draft.pk}/approve/")
        self.assertEqual(len(mail.outbox), 1)

    @patch("news.services.requests.post", side_effect=requests.ConnectionError)
    def test_publication_post_failure_can_be_retried(self, post):
        """Keep approval and expose the API failure without claiming delivery."""
        self.authenticate("editor")
        response = self.client.post(f"/api/articles/{self.draft.pk}/approve/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["api_logged"])
        self.draft.refresh_from_db()
        self.assertTrue(self.draft.approved)
        self.assertFalse(post_approved_article(self.draft))

    def test_approval_receiver_validates_secret_state_and_duplicates(self):
        """Reject forged/unapproved events and deduplicate legitimate deliveries."""
        url = "/api/approved/"
        self.assertEqual(
            self.client.post(
                url, {"article_id": self.story.pk}, format="json"
            ).status_code,
            403,
        )
        self.client.credentials(HTTP_X_APPROVAL_KEY="test-service-key")
        self.assertEqual(
            self.client.post(
                url, {"article_id": self.draft.pk}, format="json"
            ).status_code,
            404,
        )
        for bad in ("wrong", True, -1):
            self.assertEqual(
                self.client.post(url, {"article_id": bad}, format="json").status_code,
                400,
            )
        self.assertEqual(self.client.post(url, [], format="json").status_code, 400)
        self.assertEqual(
            self.client.post(
                url, {"article_id": self.story.pk}, format="json"
            ).status_code,
            201,
        )
        self.assertEqual(
            self.client.post(
                url, {"article_id": self.story.pk}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(ApprovedArticleLog.objects.count(), 1)

    def test_newsletter_crud_permissions_and_draft_filtering(self):
        """Allow curation by authors/editors and prevent draft leakage to readers."""
        payload = {
            "title": "Weekly",
            "description": "Curated stories",
            "articles": [self.story.pk],
        }
        self.authenticate("reader")
        self.assertEqual(
            self.client.post("/api/newsletters/", payload, format="json").status_code,
            403,
        )
        self.authenticate("writer")
        self.assertEqual(
            self.client.post(
                "/api/newsletters/",
                {**payload, "articles": [self.draft.pk]},
                format="json",
            ).status_code,
            400,
        )
        response = self.client.post("/api/newsletters/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        pk = response.data["id"]
        for role in ("reader", "other"):
            self.authenticate(role)
            self.assertEqual(
                self.client.patch(
                    f"/api/newsletters/{pk}/", {"title": "Changed"}
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.delete(f"/api/newsletters/{pk}/").status_code, 403
            )
        self.story.approved = False
        self.story.save()
        self.authenticate("reader")
        self.assertEqual(
            self.client.get(f"/api/newsletters/{pk}/").data["articles"], []
        )
        self.authenticate("editor")
        self.assertEqual(
            self.client.patch(
                f"/api/newsletters/{pk}/", {"title": "Edited"}
            ).status_code,
            200,
        )
        self.assertEqual(self.client.delete(f"/api/newsletters/{pk}/").status_code, 204)
        self.assertFalse(Newsletter.objects.filter(pk=pk).exists())

    def test_newsletter_html_journey(self):
        """Create, view, edit and delete newsletters through app-owned templates."""
        self.client.force_login(self.users["writer"])
        response = self.client.post(
            "/newsletters/new/",
            {
                "title": "HTML news",
                "description": "Collection",
                "articles": [self.story.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        newsletter = Newsletter.objects.get(title="HTML news")
        self.assertContains(
            self.client.get(newsletter.get_absolute_url()), self.story.title
        )
        self.client.force_login(self.users["reader"])
        self.assertEqual(
            self.client.post(f"/newsletters/{newsletter.pk}/edit/", {}).status_code, 403
        )
        self.client.force_login(self.users["editor"])
        self.assertEqual(
            self.client.post(
                f"/newsletters/{newsletter.pk}/edit/",
                {
                    "title": "Edited",
                    "description": "Collection",
                    "articles": [self.story.pk],
                },
            ).status_code,
            302,
        )
        self.assertEqual(
            self.client.post(f"/newsletters/{newsletter.pk}/delete/").status_code, 302
        )

    def test_groups_and_custom_user_relationships_follow_roles(self):
        """Synchronize permission groups and clear subscriptions on role changes."""
        reader = self.users["reader"]
        self.assertEqual(reader._meta.label, "accounts.User")
        self.assertTrue(reader.groups.filter(name="Reader").exists())
        self.assertTrue(reader.has_perm("news.view_article"))
        self.assertFalse(reader.has_perm("news.add_article"))
        self.assertTrue(self.users["writer"].has_perm("news.add_article"))
        self.assertTrue(self.users["editor"].has_perm("news.change_article"))
        self.assertIsNone(reader.independent_articles)
        reader.profile.journalists.add(self.users["writer"])
        reader.profile.role = "journalist"
        reader.profile.save()
        self.assertFalse(reader.profile.journalists.exists())
        self.assertFalse(reader.groups.filter(name="Reader").exists())
        self.assertTrue(reader.groups.filter(name="Journalist").exists())
        self.assertIsNone(reader.journalist_subscriptions)
