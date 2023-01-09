from django.contrib import admin
from django.urls import path

from root.views import root_view
from account.views import register_view

urlpatterns = [
    path('', root_view, name="home"),
    path('admin/', admin.site.urls),
    path("register", register_view, name="register")
]
