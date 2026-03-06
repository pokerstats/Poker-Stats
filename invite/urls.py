from django.urls import path

from invite.views import accept_invite_view, delete_invite_view, invite_management_view

app_name = 'invite'

urlpatterns = [
    path('', invite_management_view, name='manage'),
    path('<uuid:token>/accept/', accept_invite_view, name='accept'),
    path('<uuid:token>/delete/', delete_invite_view, name='delete'),
]
