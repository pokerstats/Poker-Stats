from django.contrib import admin

from invite.models import Invite


@admin.register(Invite)
class InviteAdmin(admin.ModelAdmin):
    list_display = ('token', 'created_by', 'created_at', 'expires_at', 'used_by', 'used_at')
    readonly_fields = ('token', 'created_at', 'used_at')
