from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from invite.models import Invite


class InviteAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        token = request.session.get('invite_token')
        if not token:
            return False
        invite = Invite.objects.get_by_token(token)
        return invite is not None and invite.is_valid


class InviteSocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(self, request, sociallogin):
        token = request.session.get('invite_token')
        if not token:
            return False
        invite = Invite.objects.get_by_token(token)
        return invite is not None and invite.is_valid
