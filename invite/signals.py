from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from django.utils import timezone

from invite.models import Invite


@receiver(user_signed_up)
def consume_invite(request, user, **kwargs):
    token = None
    try:
        token = request.session.get('invite_token')
        if not token:
            return
        invite = Invite.objects.get_by_token(token)
        if invite and invite.is_valid:
            invite.used_by = user
            invite.used_at = timezone.now()
            invite.save()
    finally:
        if token:
            request.session.pop('invite_token', None)
