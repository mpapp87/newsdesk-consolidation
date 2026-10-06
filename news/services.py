"""Fetch external headlines and deliver approved news to subscribed readers."""

import requests

HACKER_NEWS_API = "https://hn.algolia.com/api/v1/search"


def fetch_external_news(query="technology", limit=10):
    """Return a normalized list of current stories from the Hacker News API."""
    try:
        response = requests.get(
            HACKER_NEWS_API,
            params={"query": query, "tags": "story", "hitsPerPage": limit},
            timeout=5,
        )
        response.raise_for_status()
        stories = []
        for hit in response.json().get("hits", []):
            title = hit.get("title")
            if not title:
                continue
            stories.append(
                {
                    "title": title,
                    "url": hit.get("url")
                    or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    "author": hit.get("author", "Unknown"),
                    "created_at": hit.get("created_at", ""),
                }
            )
        return stories
    except (requests.RequestException, ValueError):
        return []


def queue_publication_emails(article):
    """Snapshot subscribed reader addresses once for an approved article.

    Call inside the approval transaction. Following both the publisher and the
    journalist still produces only one notification for each reader.
    """
    from django.db.models import Q
    from .models import Profile, PublicationEmail

    sources = Q(journalists=article.author)
    if article.publisher_id:
        sources |= Q(publishers=article.publisher)
    readers = (
        Profile.objects.filter(sources, role="reader", user__is_active=True)
        .exclude(user__email="")
        .select_related("user")
        .distinct()
    )
    for profile in readers:
        PublicationEmail.objects.get_or_create(
            article=article,
            reader=profile.user,
            defaults={"recipient": profile.user.email},
        )


def send_publication_emails(article):
    """Deliver unsent notifications privately and return the failure count.

    Lock each notification while sending to serialize simultaneous retry requests.
    SMTP errors leave it unsent for an editor's later retry. A process crash after
    SMTP accepts a message but before the database commit can still duplicate mail.
    """
    import logging
    from smtplib import SMTPException
    from django.conf import settings
    from django.core.mail import send_mail
    from django.db import transaction
    from django.utils import timezone
    from .models import PublicationEmail

    failed = 0
    for notification_id in article.notifications.filter(
        sent_at__isnull=True
    ).values_list("pk", flat=True):
        with transaction.atomic():
            # Also lock the article: a concurrent edit must not email an unapproved draft.
            current = type(article).objects.select_for_update().get(pk=article.pk)
            if not current.approved:
                break
            item = PublicationEmail.objects.select_for_update().get(pk=notification_id)
            if item.sent_at:
                continue
            profile = getattr(item.reader, "profile", None)
            subscribed = (
                profile
                and profile.role == "reader"
                and (
                    profile.journalists.filter(pk=current.author_id).exists()
                    or (
                        current.publisher_id
                        and profile.publishers.filter(pk=current.publisher_id).exists()
                    )
                )
            )
            if not item.reader.is_active or not subscribed:
                item.delete()
                continue
            url = settings.SITE_URL.rstrip("/") + current.get_absolute_url()
            try:
                delivered = send_mail(
                    f"NewsDesk: {current.title}",
                    f"{current.title}\n\n{current.summary}\n\n"
                    f"{current.body}\n\nRead online: {url}",
                    settings.DEFAULT_FROM_EMAIL,
                    [item.recipient],
                    fail_silently=False,
                )
                if delivered != 1:
                    raise OSError("Email backend did not accept the message.")
            except (SMTPException, OSError):
                logging.getLogger(__name__).warning(
                    "Publication email %s could not be delivered.", item.pk
                )
                failed += 1
            else:
                item.sent_at = timezone.now()
                item.save(update_fields=["sent_at"])
    return failed


def post_approved_article(article):
    """POST an approved article ID to the configured local API and report success.

    No network request occurs without an operator-provided key. The receiver is
    idempotent; failed delivery can be retried through either approval view.
    """
    from django.conf import settings

    if not article.approved or not settings.APPROVAL_API_KEY:
        return False
    try:
        response = requests.post(
            settings.APPROVAL_API_URL,
            json={"article_id": article.pk},
            headers={"X-Approval-Key": settings.APPROVAL_API_KEY},
            timeout=5,
            allow_redirects=False,
        )
        response.raise_for_status()
        data = response.json()
        return (
            response.status_code in (200, 201)
            and isinstance(data, dict)
            and data.get("logged") is True
            and data.get("article_id") == article.pk
        )
    except (requests.RequestException, ValueError):
        return False
