"""Test core browsing and author ownership behavior."""

from unittest.mock import patch
from django.contrib.auth import get_user_model

User = get_user_model()
from django.test import TestCase
from django.urls import reverse
from .models import Article, Comment, SavedArticle, Profile


class NewsApplicationTests(TestCase):
    """Verify existing browsing, author ownership and external-news features."""

    def setUp(self):
        """Create a journalist, a reader and an approved test article."""
        self.user = User.objects.create_user(username="michael", password="testpass123")
        self.other = User.objects.create_user(username="other", password="testpass123")
        Profile.objects.create(user=self.user, role="journalist")
        Profile.objects.create(user=self.other, role="reader")
        self.article = Article.objects.create(
            title="Test headline",
            summary="Short summary",
            body="Article body",
            category="technology",
            author=self.user,
            approved=True,
        )

    def test_home_lists_articles(self):
        """Display approved article headlines on the home page."""
        response = self.client.get(reverse("news:home"))
        self.assertContains(response, "Test headline")

    def test_search_filters_articles(self):
        """Filter published articles by matching search text."""
        response = self.client.get(reverse("news:home"), {"q": "headline"})
        self.assertContains(response, "Test headline")
        response = self.client.get(reverse("news:home"), {"q": "missing"})
        self.assertNotContains(response, "Test headline")

    def test_create_requires_login(self):
        """Redirect anonymous article submissions to login."""
        response = self.client.get(reverse("news:article_create"))
        self.assertEqual(response.status_code, 302)

    def test_logged_in_user_can_create_article(self):
        """Allow the authenticated journalist to submit an article."""
        self.client.login(username="michael", password="testpass123")
        response = self.client.post(
            reverse("news:article_create"),
            {
                "title": "New story",
                "summary": "Summary",
                "body": "Body",
                "source_url": "",
                "category": "world",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Article.objects.filter(title="New story", author=self.user).exists()
        )

    def test_user_cannot_edit_another_users_article(self):
        """Reject edits by an account that does not own the article."""
        self.client.login(username="other", password="testpass123")
        response = self.client.get(
            reverse("news:article_update", args=[self.article.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_comment_and_save(self):
        """Allow a reader to comment on and save an approved story."""
        self.client.login(username="other", password="testpass123")
        self.client.post(
            reverse("news:add_comment", args=[self.article.pk]), {"body": "Great story"}
        )
        self.assertTrue(
            Comment.objects.filter(article=self.article, body="Great story").exists()
        )
        self.client.post(reverse("news:toggle_save", args=[self.article.pk]))
        self.assertTrue(
            SavedArticle.objects.filter(user=self.other, article=self.article).exists()
        )

    @patch("news.views.fetch_external_news")
    def test_external_news_view(self, mock_fetch):
        """Render normalized external stories without making network calls."""
        mock_fetch.return_value = [
            {
                "title": "API story",
                "url": "https://example.com",
                "author": "author",
                "created_at": "",
            }
        ]
        response = self.client.get(reverse("news:external_news"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "API story")
