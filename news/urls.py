"""Route news and registration requests to application views."""

from django.urls import path
from . import views, api
from rest_framework.authtoken.views import obtain_auth_token

app_name = "news"

urlpatterns = [
    path("api/token/", obtain_auth_token, name="api_token"),
    path("api/articles/", api.ArticleList.as_view(), name="api_articles"),
    path(
        "api/articles/subscribed/",
        api.SubscribedArticles.as_view(),
        name="api_subscribed",
    ),
    path(
        "api/articles/<int:pk>/", api.ArticleDetail.as_view(), name="api_article_detail"
    ),
    path(
        "api/articles/<int:pk>/approve/",
        api.ArticleApproval.as_view(),
        name="api_article_approve",
    ),
    path("api/approved/", api.ApprovedReceiver.as_view(), name="api_approved"),
    path("api/newsletters/", api.NewsletterList.as_view(), name="api_newsletters"),
    path(
        "api/newsletters/<int:pk>/",
        api.NewsletterDetail.as_view(),
        name="api_newsletter_detail",
    ),
    path("api/publishers/", api.PublisherList.as_view(), name="api_publishers"),
    path("newsletters/", views.newsletters, name="newsletters"),
    path("newsletters/new/", views.newsletter_create, name="newsletter_create"),
    path("newsletters/<int:pk>/", views.newsletter_detail, name="newsletter_detail"),
    path(
        "newsletters/<int:pk>/edit/", views.newsletter_update, name="newsletter_update"
    ),
    path(
        "newsletters/<int:pk>/delete/",
        views.newsletter_delete,
        name="newsletter_delete",
    ),
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("subscriptions/", views.subscriptions, name="subscriptions"),
    path("article/<int:pk>/approve/", views.approve_article, name="approve_article"),
    path("register/", views.register, name="register"),
    path("article/new/", views.article_create, name="article_create"),
    path("article/<int:pk>/", views.article_detail, name="article_detail"),
    path("article/<int:pk>/edit/", views.article_update, name="article_update"),
    path("article/<int:pk>/delete/", views.article_delete, name="article_delete"),
    path("article/<int:pk>/comment/", views.add_comment, name="add_comment"),
    path("article/<int:pk>/save/", views.toggle_save, name="toggle_save"),
    path("saved/", views.saved_articles, name="saved_articles"),
    path("external/", views.external_news, name="external_news"),
]
