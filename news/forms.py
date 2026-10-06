"""Validate role registration, article submissions and reader subscriptions."""

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()
from django.db import transaction
from .models import Article, Comment, Profile, Publisher


class RegisterForm(UserCreationForm):
    """Extend Django registration with a required email and news role."""

    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=Profile.ROLE_CHOICES)

    def clean_email(self):
        """Reject case-insensitive duplicates before creating an account."""
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )
        return email

    class Meta:
        """Expose only public registration fields, never staff privileges."""

        model = User
        fields = ("username", "email", "role", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        """Save the account and role together; reject deferred profile creation."""
        if not commit:
            raise ValueError(
                "RegisterForm must save the account and profile together."
            )
        user = super().save(commit=True)
        Profile.objects.create(user=user, role=self.cleaned_data["role"])
        return user


class ArticleForm(forms.ModelForm):
    """Accept article content without exposing authorship or approval fields."""

    class Meta:
        """Define editable content and a readable body input."""

        model = Article
        fields = (
            "title",
            "summary",
            "body",
            "source_url",
            "category",
            "publisher",
        )
        widgets = {"body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, author=None, **kwargs):
        """Restrict publisher selection to organizations of the article author."""
        super().__init__(*args, **kwargs)
        self.fields["publisher"].queryset = (
            Publisher.objects.filter(journalists=author)
            if author
            else Publisher.objects.none()
        )


class CommentForm(forms.ModelForm):
    """Validate reader comments while setting author and article in the view."""

    class Meta:
        """Expose the comment body only."""

        model = Comment
        fields = ("body",)
        widgets = {
            "body": forms.Textarea(
                attrs={"rows": 3, "placeholder": "Join the discussion..."}
            )
        }


class SubscriptionForm(forms.ModelForm):
    """Let readers choose journalists and publishers for publication emails."""

    class Meta:
        """Exclude role and user fields from subscription changes."""

        model = Profile
        fields = ("journalists", "publishers")


class NewsletterForm(forms.ModelForm):
    """Validate a curated set of approved articles and an allowed publisher."""

    class Meta:
        """Expose newsletter content without accepting another author's ID."""

        from .models import Newsletter

        model = Newsletter
        fields = ("title", "description", "publisher", "articles")

    def __init__(self, *args, author=None, **kwargs):
        """Offer approved articles and publishers appropriate to the author role."""
        super().__init__(*args, **kwargs)
        self.fields["articles"].queryset = Article.objects.filter(
            approved=True
        )
        if author and getattr(author, "role", None) == "editor":
            self.fields["publisher"].queryset = Publisher.objects.filter(
                editors=author
            )
        else:
            self.fields["publisher"].queryset = (
                Publisher.objects.filter(journalists=author)
                if author
                else Publisher.objects.none()
            )


class PublisherForm(forms.ModelForm):
    """Let an editor create an organization and select registered journalists."""

    class Meta:
        """Keep editor ownership controlled by the authenticated view."""

        model = Publisher
        fields = ("name", "journalists")

    def __init__(self, *args, **kwargs):
        """List only active journalists, never readers or editors."""
        super().__init__(*args, **kwargs)
        self.fields["journalists"].queryset = User.objects.filter(
            is_active=True, profile__role="journalist"
        ).order_by("username")
