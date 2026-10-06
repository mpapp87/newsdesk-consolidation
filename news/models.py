"""Persist news, account roles, subscriptions and publication notifications."""

from django.contrib.auth import get_user_model

User = get_user_model()
from django.db import models
from django.urls import reverse


class Publisher(models.Model):
    """Represent a news organization managed by its editors in the application."""

    name = models.CharField(max_length=200, unique=True)
    editors = models.ManyToManyField(
        User,
        blank=True,
        related_name="edited_publishers",
        limit_choices_to={"profile__role": "editor"},
    )
    journalists = models.ManyToManyField(
        User,
        blank=True,
        related_name="publishers",
        limit_choices_to={"profile__role": "journalist"},
    )

    def __str__(self):
        """Return the organization name for forms and administration."""
        return self.name


class Profile(models.Model):
    """Store an account role and the sources a reader chooses to follow."""

    ROLE_CHOICES = [
        ("reader", "Reader"),
        ("journalist", "Journalist"),
        ("editor", "Editor"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="reader")
    journalists = models.ManyToManyField(
        User,
        blank=True,
        related_name="reader_subscribers",
        limit_choices_to={"profile__role": "journalist"},
    )
    publishers = models.ManyToManyField(
        Publisher, blank=True, related_name="reader_subscribers"
    )

    def __str__(self):
        """Return the account name and its selected role."""
        return f"{self.user.username} ({self.get_role_display()})"


class Article(models.Model):
    """Store a draft published by its publisher editor or independent author."""

    CATEGORY_CHOICES = [
        ("world", "World"),
        ("business", "Business"),
        ("technology", "Technology"),
        ("science", "Science"),
        ("sports", "Sports"),
        ("culture", "Culture"),
    ]
    title = models.CharField(max_length=200)
    summary = models.TextField()
    body = models.TextField()
    source_url = models.URLField(blank=True)
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, default="world"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="articles")
    publisher = models.ForeignKey(
        Publisher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="articles",
    )
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_articles",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Order articles from newest to oldest."""

        ordering = ["-published_at"]

    def __str__(self):
        """Return the article headline."""
        return self.title

    def get_absolute_url(self):
        """Return the internal URL for this article."""
        return reverse("news:article_detail", args=[self.pk])


class Comment(models.Model):
    """Store an authenticated reader's discussion of a published article."""

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="comments"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Display comments in chronological order."""

        ordering = ["created_at"]

    def __str__(self):
        """Identify the commenter and article in administration."""
        return f"Comment by {self.author} on {self.article}"


class SavedArticle(models.Model):
    """Record a user's saved article without duplicate bookmarks."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="saved_articles"
    )
    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="saved_by"
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Enforce one bookmark per user and article."""

        constraints = [
            models.UniqueConstraint(
                fields=["user", "article"], name="unique_saved_article"
            )
        ]


class PublicationEmail(models.Model):
    """Track a private notification and allow failed deliveries to be retried."""

    article = models.ForeignKey(
        Article, on_delete=models.CASCADE, related_name="notifications"
    )
    reader = models.ForeignKey(User, on_delete=models.CASCADE)
    recipient = models.EmailField()
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Send at most one tracked publication notification per reader."""

        constraints = [
            models.UniqueConstraint(
                fields=["article", "reader"], name="unique_publication_email"
            )
        ]


class Newsletter(models.Model):
    """Group approved articles into a curated publication owned by its creator."""

    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="newsletters"
    )
    publisher = models.ForeignKey(
        Publisher,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="newsletters",
    )
    articles = models.ManyToManyField(Article, related_name="newsletters", blank=True)

    class Meta:
        """List the most recently created newsletters first."""

        ordering = ["-created_at"]

    def __str__(self):
        """Return the newsletter title in forms and administration."""
        return self.title

    def get_absolute_url(self):
        """Return the newsletter's HTML detail URL."""
        return reverse("news:newsletter_detail", args=[self.pk])


class ApprovedArticleLog(models.Model):
    """Record an idempotent receipt of a publication POST to the local API."""

    article = models.OneToOneField(
        Article, on_delete=models.CASCADE, related_name="approval_log"
    )
    received_at = models.DateTimeField(auto_now_add=True)
