"""Provide authenticated news resources and the signed publication receiver."""

import secrets
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Article, ApprovedArticleLog, Newsletter, Publisher
from .roles import can_edit, can_publish, has_role
from .serializers import (
    ArticleSerializer,
    NewsletterSerializer,
    PublisherSerializer,
)
from .services import (
    queue_publication_emails,
    send_publication_emails,
    post_approved_article,
)


class NewsRolePermission(permissions.BasePermission):
    """Reject anonymous or roleless API clients before querying news resources."""

    def has_permission(self, request, view):
        """Require one of the three registered news roles."""
        return any(
            has_role(request.user, role)
            for role in ("reader", "journalist", "editor")
        )


class ArticleList(generics.ListCreateAPIView):
    """List approved articles and allow journalists to create unapproved drafts."""

    serializer_class = ArticleSerializer
    permission_classes = [NewsRolePermission]
    queryset = Article.objects.filter(approved=True).select_related(
        "author", "author__profile", "publisher"
    )

    def create(self, request, *args, **kwargs):
        """Reject non-journalists before validating a submission."""
        if not has_role(request.user, "journalist"):
            raise PermissionDenied("Only journalists can create articles.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Set the authenticated author and never accept a client approval flag."""
        serializer.save(author=self.request.user, approved=False)


class SubscribedArticles(generics.ListAPIView):
    """Return only approved content matching the authenticated reader's follows."""

    serializer_class = ArticleSerializer
    permission_classes = [NewsRolePermission]

    def get_queryset(self):
        """Scope the query to the current reader, ignoring supplied user IDs."""
        user = self.request.user
        if not has_role(user, "reader"):
            raise PermissionDenied("Only readers have subscriptions.")
        return (
            Article.objects.filter(approved=True)
            .filter(
                Q(author__in=user.profile.journalists.all())
                | Q(publisher__in=user.profile.publishers.all())
            )
            .select_related("author", "author__profile", "publisher")
            .distinct()
        )


class ArticleDetail(generics.RetrieveUpdateDestroyAPIView):
    """Read visible stories and enforce ownership/editor rights for mutations."""

    serializer_class = ArticleSerializer
    permission_classes = [NewsRolePermission]

    def get_queryset(self):
        """Expose drafts only to their author or an editor."""
        from .views import visible_articles

        return visible_articles(self.request.user)

    def update(self, request, *args, **kwargs):
        """Lock content while resetting approval for an authorized edit."""
        with transaction.atomic():
            article = self.get_object()
            if not can_edit(request.user, article):
                raise PermissionDenied(
                    "Only the author or an editor may edit."
                )
            locked = Article.objects.select_for_update().get(pk=article.pk)
            serializer = self.get_serializer(
                locked, data=request.data, partial=kwargs.get("partial", False)
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(approved=False, approved_by=None, approved_at=None)
        return Response(serializer.data)

    def perform_destroy(self, instance):
        """Reject readers and non-owning journalists before deleting content."""
        if not can_edit(self.request.user, instance):
            raise PermissionDenied("Only the author or an editor may delete.")
        instance.delete()


class ArticleApproval(APIView):
    """Publish as a publisher editor or independent owner; retry pending delivery."""

    permission_classes = [NewsRolePermission]

    def post(self, request, pk):
        """Commit approval before sending email and calling the local REST API."""
        with transaction.atomic():
            article = get_object_or_404(
                Article.objects.select_for_update(), pk=pk
            )
            if not can_publish(request.user, article):
                raise PermissionDenied(
                    "Only this publisher's editors or the independent author may publish."
                )
            if not article.approved:
                article.approved = True
                article.approved_by = (
                    request.user if article.publisher_id else None
                )
                article.approved_at = timezone.now()
                article.save(
                    update_fields=["approved", "approved_by", "approved_at"]
                )
                queue_publication_emails(article)
        failures = send_publication_emails(article)
        posted = post_approved_article(article)
        return Response(
            {
                "approved": True,
                "email_failures": failures,
                "api_logged": posted,
            }
        )


class ApprovedReceiver(APIView):
    """Accept server-to-server approval posts with a separate configured secret."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        """Verify the shared key and record only currently approved article IDs."""
        expected = settings.APPROVAL_API_KEY
        supplied = request.headers.get("X-Approval-Key", "")
        if not expected or not secrets.compare_digest(expected, supplied):
            raise PermissionDenied("Invalid approval service credentials.")
        if not isinstance(request.data, dict):
            return Response(
                {"detail": "A JSON object is required."}, status=400
            )
        pk = request.data.get("article_id")
        if isinstance(pk, bool) or not isinstance(pk, int) or pk <= 0:
            return Response(
                {"article_id": "A positive integer is required."}, status=400
            )
        article = get_object_or_404(Article, pk=pk, approved=True)
        _, created = ApprovedArticleLog.objects.get_or_create(article=article)
        return Response(
            {"article_id": article.pk, "logged": True},
            status=201 if created else 200,
        )


class NewsletterList(generics.ListCreateAPIView):
    """Let role accounts view newsletters and editorial roles curate them."""

    queryset = Newsletter.objects.select_related(
        "author", "author__profile", "publisher"
    ).prefetch_related("articles")
    serializer_class = NewsletterSerializer
    permission_classes = [NewsRolePermission]

    def create(self, request, *args, **kwargs):
        """Reject reader writes before serializer validation."""
        if not (
            has_role(request.user, "journalist")
            or has_role(request.user, "editor")
        ):
            raise PermissionDenied(
                "Only journalists and editors can create newsletters."
            )
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Assign newsletter ownership to the authenticated curator."""
        serializer.save(author=self.request.user)


class NewsletterDetail(generics.RetrieveUpdateDestroyAPIView):
    """Enforce ownership and editor control for newsletter changes."""

    queryset = Newsletter.objects.select_related(
        "author", "author__profile"
    ).prefetch_related("articles")
    serializer_class = NewsletterSerializer
    permission_classes = [NewsRolePermission]

    def perform_update(self, serializer):
        """Save only when the current user owns the newsletter or is an editor."""
        if not can_edit(self.request.user, serializer.instance):
            raise PermissionDenied("Only the author or an editor may edit.")
        serializer.save()

    def perform_destroy(self, instance):
        """Delete only when the current user owns the newsletter or is an editor."""
        if not can_edit(self.request.user, instance):
            raise PermissionDenied("Only the author or an editor may delete.")
        instance.delete()


class PublisherList(generics.ListAPIView):
    """Expose publisher identities and memberships to authenticated news roles."""

    queryset = Publisher.objects.prefetch_related("journalists", "editors")
    serializer_class = PublisherSerializer
    permission_classes = [NewsRolePermission]
