"""Validate API input and expose public news resources without account secrets."""

from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Article, Newsletter, Publisher


class UserSerializer(serializers.ModelSerializer):
    """Expose a username and role while keeping email and password private."""

    role = serializers.CharField(read_only=True)

    class Meta:
        """Limit user responses to public identity fields."""

        model = get_user_model()
        fields = ("id", "username", "role")
        read_only_fields = fields


class PublisherSerializer(serializers.ModelSerializer):
    """Expose publisher membership without permitting API membership changes."""

    class Meta:
        """List organization identities and journalist/editor IDs."""

        model = Publisher
        fields = ("id", "name", "journalists", "editors")
        read_only_fields = fields


class ArticleSerializer(serializers.ModelSerializer):
    """Map the brief's content and creation names onto preserved database fields."""

    content = serializers.CharField(source="body")
    created_at = serializers.DateTimeField(source="published_at", read_only=True)
    author = UserSerializer(read_only=True)

    class Meta:
        """Protect authorship and editorial approval from submitted JSON."""

        model = Article
        fields = (
            "id",
            "title",
            "summary",
            "content",
            "source_url",
            "category",
            "author",
            "publisher",
            "created_at",
            "approved",
            "approved_at",
        )
        read_only_fields = ("approved", "approved_at")
        extra_kwargs = {"summary": {"required": False}}

    def validate_publisher(self, value):
        """Require the article author to belong to the selected publisher."""
        author = self.instance.author if self.instance else self.context["request"].user
        if value and not value.journalists.filter(pk=author.pk).exists():
            raise serializers.ValidationError(
                "The author does not belong to this publisher."
            )
        return value


class NewsletterSerializer(serializers.ModelSerializer):
    """Validate newsletter selections and hide articles returned to draft."""

    author = UserSerializer(read_only=True)
    articles = serializers.PrimaryKeyRelatedField(
        queryset=Article.objects.filter(approved=True), many=True
    )

    class Meta:
        """Expose only curated content and immutable authorship."""

        model = Newsletter
        fields = (
            "id",
            "title",
            "description",
            "created_at",
            "author",
            "publisher",
            "articles",
        )
        read_only_fields = ("created_at",)

    def validate_publisher(self, value):
        """Restrict publication to the creator's organization memberships."""
        author = self.instance.author if self.instance else self.context["request"].user
        members = (
            value.editors
            if value and author.role == "editor"
            else value.journalists if value else None
        )
        if members is not None and not members.filter(pk=author.pk).exists():
            raise serializers.ValidationError(
                "The author does not belong to this publisher."
            )
        return value

    def to_representation(self, instance):
        """Exclude article IDs that are no longer approved from every response."""
        data = super().to_representation(instance)
        data["articles"] = list(
            instance.articles.filter(approved=True).values_list("pk", flat=True)
        )
        return data
