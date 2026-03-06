from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from root.views import (
    contact_view,
    error_view,
    root_view,
)

from user.views import CustomPasswordChangeView

urlpatterns = [
    path('', root_view, name="home"),
    path('accounts/password/change/', CustomPasswordChangeView.as_view(), name="account_change_password"),
    path('accounts/', include("allauth.urls")),
    path('admin/', admin.site.urls),
    path('contact/', contact_view, name="contact"),
    path('error/<str:error_message>/', error_view, name="error"),
    path('tournament/', include("tournament.urls"), name="tournament"),
    path('user/', include("user.urls"), name="user"),
    path('tournament_analytics/', include("tournament_analytics.urls"), name="tournament_analytics"),
    path('tournament_group/', include("tournament_group.urls"), name="tournament_group"),
    path('invite/', include("invite.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
