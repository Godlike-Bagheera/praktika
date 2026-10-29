from django.urls import path

from . import views

urlpatterns = [
    # Auth
    path("auth/register", views.RegisterView.as_view(), name="register"),
    path("auth/login", views.LoginView.as_view(), name="login"),
    path("auth/logout", views.LogoutView.as_view(), name="logout"),
    path("auth/refresh", views.RefreshView.as_view(), name="token-refresh"),
    path("auth/me", views.MeView.as_view(), name="me"),

    # Categories
    path("categories", views.CategoryListCreateView.as_view(),
         name="category-list"),
    path("categories/<int:pk>", views.CategoryDetailView.as_view(),
         name="category-detail"),

    # Topics
    path("topics", views.TopicListCreateView.as_view(), name="topic-list"),
    path("topics/<int:pk>", views.TopicDetailView.as_view(),
         name="topic-detail"),
    path("topics/<int:pk>/posts", views.TopicPostsListView.as_view(),
         name="topic-posts"),

    # Posts
    path("posts/<int:pk>", views.PostDetailView.as_view(),
         name="post-detail"),
    # Без слэша: фронт обращается к /api/posts/export (nginx проксирует как есть)
    path("posts/export", views.PostsExportView.as_view(),
         name="posts-export"),
    path("posts/<int:post_id>/report/", views.ReportCreateView.as_view(),
         name="post-report"),
    path("posts/<int:post_id>/my-reports/", views.UserReportStatusView.as_view(),
         name="post-report-status"),

    # Reports (модерация, admin only)
    path("reports/pending-count/", views.PendingReportsCountView.as_view(),
         name="reports-pending-count"),
    path("reports/<int:pk>/action/", views.ReportActionView.as_view(),
         name="report-action"),
    path("reports/", views.ReportListView.as_view(), name="reports-list"),
    # Notifications
    path("notifications", views.NotificationListView.as_view(),
         name="notification-list"),
    path("notifications/count", views.NotificationUnreadCountView.as_view(),
         name="notification-count"),
    path("notifications/read", views.NotificationMarkReadView.as_view(),
         name="notification-read"),

    # Stats (admin only)
    path("stats", views.ForumStatsView.as_view(), name="forum-stats"),
]
