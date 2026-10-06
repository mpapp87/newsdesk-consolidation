"""Handle news browsing, role-restricted publishing and reader preferences."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    ArticleForm,
    CommentForm,
    PublisherForm,
    RegisterForm,
    SubscriptionForm,
)
from .models import Article, Publisher, SavedArticle
from .roles import can_edit, can_publish, has_role
from .services import (
    fetch_external_news,
    queue_publication_emails,
    send_publication_emails,
    post_approved_article,
)


def visible_articles(user):
    """Return published stories plus drafts the current account may manage."""
    articles = Article.objects.select_related("author", "publisher")
    if has_role(user, "editor"):
        return articles.filter(
            Q(approved=True) | Q(publisher__editors=user)
        ).distinct()
    if has_role(user, "journalist"):
        return articles.filter(Q(approved=True) | Q(author=user))
    return articles.filter(approved=True)


def home(request):
    """Render approved news with optional title, body and category filters."""
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    articles = Article.objects.select_related("author").filter(approved=True)
    if query:
        articles = articles.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(body__icontains=query)
        )
    if category:
        articles = articles.filter(category=category)
    return render(
        request,
        "news/home.html",
        {
            "articles": articles,
            "query": query,
            "category": category,
            "categories": Article.CATEGORY_CHOICES,
        },
    )


def article_detail(request, pk):
    """Show a visible article, returning 404 for drafts the user cannot access."""
    article = get_object_or_404(visible_articles(request.user), pk=pk)
    is_saved = (
        request.user.is_authenticated
        and SavedArticle.objects.filter(
            user=request.user, article=article
        ).exists()
    )
    return render(
        request,
        "news/article_detail.html",
        {
            "article": article,
            "form": CommentForm(),
            "is_saved": is_saved,
            "can_manage": can_edit(request.user, article),
            "can_publish": can_publish(request.user, article),
            "delivery_pending": article.approved
            and (
                article.notifications.filter(sent_at__isnull=True).exists()
                or not hasattr(article, "approval_log")
            ),
            "follows_author": has_role(request.user, "reader")
            and request.user.profile.journalists.filter(
                pk=article.author_id
            ).exists(),
            "follows_publisher": has_role(request.user, "reader")
            and request.user.profile.publishers.filter(
                pk=article.publisher_id
            ).exists(),
        },
    )


def register(request):
    """Create an account with its selected role and sign the new user in."""
    if request.user.is_authenticated:
        return redirect("news:home")
    form = RegisterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            user = form.save()
        except IntegrityError:
            # The database also protects simultaneous registration requests.
            form.add_error(
                "email", "That email or username is already registered."
            )
        else:
            login(request, user)
            messages.success(
                request,
                f"Welcome to NewsDesk, {user.profile.get_role_display()}!",
            )
            return redirect("news:home")
    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    """List an editor's review queue or a journalist's own submissions."""
    if has_role(request.user, "editor"):
        articles = (
            Article.objects.filter(publisher__editors=request.user)
            .select_related("author", "publisher")
            .distinct()
            .order_by("approved", "-updated_at")
        )
    elif has_role(request.user, "journalist"):
        articles = Article.objects.filter(author=request.user)
    else:
        return HttpResponseForbidden(
            "Only journalists and editors have a newsroom dashboard."
        )
    return render(request, "news/dashboard.html", {"articles": articles})


@login_required
def article_create(request):
    """Save publisher submissions or independent drafts for the owning journalist."""
    if not has_role(request.user, "journalist"):
        return HttpResponseForbidden("Only journalists can submit articles.")
    form = ArticleForm(
        request.POST if request.method == "POST" else None, author=request.user
    )
    if request.method == "POST" and form.is_valid():
        article = form.save(commit=False)
        article.author = request.user
        article.save()
        messages.success(
            request,
            (
                "Article submitted for publisher editor approval."
                if article.publisher_id
                else "Independent draft saved. Choose Publish when you are ready."
            ),
        )
        return redirect(article)
    return render(
        request,
        "news/article_form.html",
        {"form": form, "heading": "Submit article"},
    )


@login_required
def article_update(request, pk):
    """Edit authorized content and require a fresh publish action after changes."""
    article = get_object_or_404(Article, pk=pk)
    if not can_edit(request.user, article):
        return HttpResponseForbidden(
            "Only the journalist who wrote this article or an editor may edit it."
        )
    form = ArticleForm(
        request.POST if request.method == "POST" else None,
        instance=article,
        author=article.author,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            # Use the same row lock as approval to avoid publishing concurrent edits.
            Article.objects.select_for_update().get(pk=article.pk)
            article = form.save(commit=False)
            article.approved = False
            article.approved_by = None
            article.approved_at = None
            article.save()
        messages.success(
            request,
            (
                "Article updated and returned for publisher editor approval."
                if article.publisher_id
                else "Independent draft updated. Choose Publish when you are ready."
            ),
        )
        return redirect(article)
    return render(
        request,
        "news/article_form.html",
        {"form": form, "heading": "Edit article"},
    )


@login_required
def article_delete(request, pk):
    """Let editors or the owning journalist confirm and delete an article."""
    article = get_object_or_404(Article, pk=pk)
    if not can_edit(request.user, article):
        return HttpResponseForbidden(
            "Only the owning journalist or an editor may delete this article."
        )
    if request.method == "POST":
        article.delete()
        messages.success(request, "Article deleted.")
        return redirect("news:dashboard")
    return render(
        request, "news/article_confirm_delete.html", {"article": article}
    )


@login_required
@require_POST
def approve_article(request, pk):
    """Publish an authorized draft and deliver queued reader notifications.

    Approval and notification records commit before SMTP is attempted. A repeated
    POST retries only unsent notifications and does not duplicate tracked mail.
    """
    with transaction.atomic():
        article = get_object_or_404(Article.objects.select_for_update(), pk=pk)
        if not can_publish(request.user, article):
            return HttpResponseForbidden(
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
    failed = send_publication_emails(article)
    if not post_approved_article(article):
        messages.warning(
            request,
            "Article published. Publication logging is pending; use Retry pending delivery.",
        )
    if failed:
        messages.warning(
            request,
            "Article published, but some emails are pending. Use Retry pending delivery.",
        )
    else:
        messages.success(
            request,
            "Article published. Reader notification processing is complete.",
        )
    return redirect(article)


@login_required
@require_POST
def add_comment(request, pk):
    """Save a validated reader comment on an approved article using POST."""
    if not has_role(request.user, "reader"):
        return HttpResponseForbidden("Only readers can comment.")
    article = get_object_or_404(Article, pk=pk, approved=True)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.article, comment.author = article, request.user
        comment.save()
    else:
        messages.error(
            request, "Enter a comment between 1 and 1,000 characters."
        )
    return redirect(article)


@login_required
@require_POST
def toggle_save(request, pk):
    """Toggle the current reader's bookmark for an approved story using POST."""
    if not has_role(request.user, "reader"):
        return HttpResponseForbidden("Only readers can save articles.")
    article = get_object_or_404(Article, pk=pk, approved=True)
    saved, created = SavedArticle.objects.get_or_create(
        user=request.user, article=article
    )
    if not created:
        saved.delete()
    return redirect(article)


@login_required
def saved_articles(request):
    """Display the reader's bookmarks, excluding articles returned to draft."""
    if not has_role(request.user, "reader"):
        return HttpResponseForbidden("Only readers have saved articles.")
    saved = SavedArticle.objects.filter(
        user=request.user, article__approved=True
    ).select_related("article", "article__author")
    return render(request, "news/saved_articles.html", {"saved": saved})


@login_required
def subscriptions(request):
    """Update a reader's subscriptions without accepting role changes."""
    if not has_role(request.user, "reader"):
        return HttpResponseForbidden("Only readers can subscribe.")
    form = SubscriptionForm(
        request.POST if request.method == "POST" else None,
        instance=request.user.profile,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Subscriptions updated. You will receive emails when new articles are approved.",
        )
        return redirect("news:subscriptions")
    return render(request, "news/subscriptions.html", {"form": form})


def external_news(request):
    """Render external stories while allowing the service to handle outages."""
    query = request.GET.get("q", "technology").strip() or "technology"
    return render(
        request,
        "news/external_news.html",
        {"stories": fetch_external_news(query=query), "query": query},
    )


@login_required
def newsletters(request):
    """List newsletters for registered news roles."""
    from .models import Newsletter

    if not any(
        has_role(request.user, r) for r in ("reader", "journalist", "editor")
    ):
        return HttpResponseForbidden("A news role is required.")
    return render(
        request,
        "news/newsletters.html",
        {"newsletters": Newsletter.objects.select_related("author")},
    )


@login_required
def newsletter_detail(request, pk):
    """Show a newsletter while excluding linked articles returned to draft."""
    from .models import Newsletter

    if not any(
        has_role(request.user, r) for r in ("reader", "journalist", "editor")
    ):
        return HttpResponseForbidden("A news role is required.")
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return render(
        request,
        "news/newsletter_detail.html",
        {
            "newsletter": newsletter,
            "articles": newsletter.articles.filter(approved=True),
            "can_manage": can_edit(request.user, newsletter),
        },
    )


@login_required
def newsletter_create(request):
    """Let journalists and editors curate a collection of approved articles."""
    from .forms import NewsletterForm

    if not (
        has_role(request.user, "journalist")
        or has_role(request.user, "editor")
    ):
        return HttpResponseForbidden(
            "Only journalists and editors can curate newsletters."
        )
    form = NewsletterForm(
        request.POST if request.method == "POST" else None, author=request.user
    )
    if request.method == "POST" and form.is_valid():
        newsletter = form.save(commit=False)
        newsletter.author = request.user
        newsletter.save()
        form.save_m2m()
        return redirect(newsletter)
    return render(
        request,
        "news/article_form.html",
        {"form": form, "heading": "Create newsletter"},
    )


@login_required
def newsletter_update(request, pk):
    """Allow an owning journalist or editor to revise newsletter content."""
    from .forms import NewsletterForm
    from .models import Newsletter

    newsletter = get_object_or_404(Newsletter, pk=pk)
    if not can_edit(request.user, newsletter):
        return HttpResponseForbidden("Only the author or an editor may edit.")
    form = NewsletterForm(
        request.POST if request.method == "POST" else None,
        instance=newsletter,
        author=newsletter.author,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(newsletter)
    return render(
        request,
        "news/article_form.html",
        {"form": form, "heading": "Edit newsletter"},
    )


@login_required
def newsletter_delete(request, pk):
    """Confirm and delete a newsletter only for its owner or an editor."""
    from .models import Newsletter

    newsletter = get_object_or_404(Newsletter, pk=pk)
    if not can_edit(request.user, newsletter):
        return HttpResponseForbidden(
            "Only the author or an editor may delete."
        )
    if request.method == "POST":
        newsletter.delete()
        return redirect("news:newsletters")
    return render(
        request,
        "news/newsletter_confirm_delete.html",
        {"newsletter": newsletter},
    )


@login_required
def publisher_manage(request, pk=None):
    """Create publishers or update an organization owned by the current editor."""
    if not has_role(request.user, "editor"):
        return HttpResponseForbidden("Only editors can manage publishers.")
    publisher = (
        get_object_or_404(Publisher, pk=pk, editors=request.user)
        if pk
        else None
    )
    form = PublisherForm(
        request.POST if request.method == "POST" else None, instance=publisher
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            publisher = form.save()
            publisher.editors.add(request.user)
        messages.success(
            request, "Publisher saved. Journalist membership is updated."
        )
        return redirect("news:publisher_manage", pk=publisher.pk)
    return render(
        request,
        "news/publishers.html",
        {
            "form": form,
            "publisher": publisher,
            "publishers": Publisher.objects.filter(editors=request.user),
        },
    )


@login_required
@require_POST
def subscribe_article(request, pk):
    """Add or remove only the current article's author or publisher subscription."""
    if not has_role(request.user, "reader"):
        return HttpResponseForbidden("Only readers can subscribe.")
    article = get_object_or_404(Article, pk=pk, approved=True)
    source = request.POST.get("source")
    action = request.POST.get("action")
    if source == "journalist":
        relation, target = request.user.profile.journalists, article.author
    elif source == "publisher" and article.publisher_id:
        relation, target = request.user.profile.publishers, article.publisher
    else:
        return HttpResponseForbidden(
            "Choose an author or publisher on this article."
        )
    if action == "subscribe":
        relation.add(target)
        messages.success(
            request, "Subscribed to future articles from this source."
        )
    elif action == "unsubscribe":
        relation.remove(target)
        messages.success(request, "Subscription removed.")
    else:
        return HttpResponseForbidden("Choose subscribe or unsubscribe.")
    return redirect(article)
