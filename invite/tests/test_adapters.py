from datetime import timedelta

from django.test import TestCase, RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone

from invite.adapters import InviteAccountAdapter, InviteSocialAccountAdapter
from invite.models import Invite
from user.test_util import build_user


def make_request_with_session(session_data=None):
    factory = RequestFactory()
    request = factory.get('/')
    request.session = SessionStore()
    if session_data:
        for key, value in session_data.items():
            request.session[key] = value
    return request


class InviteAccountAdapterTestCase(TestCase):

    def setUp(self):
        self.adapter = InviteAccountAdapter()
        self.staff = build_user('staff')
        self.staff.is_staff = True
        self.staff.save()

    def test_open_for_signup_with_valid_token(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        request = make_request_with_session({'invite_token': str(invite.token)})
        self.assertTrue(self.adapter.is_open_for_signup(request))

    def test_closed_with_no_token_in_session(self):
        request = make_request_with_session()
        self.assertFalse(self.adapter.is_open_for_signup(request))

    def test_closed_with_expired_token(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.expires_at = timezone.now() - timedelta(seconds=1)
        invite.save()
        request = make_request_with_session({'invite_token': str(invite.token)})
        self.assertFalse(self.adapter.is_open_for_signup(request))

    def test_closed_with_used_token(self):
        user = build_user('user1')
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.used_by = user
        invite.used_at = timezone.now()
        invite.save()
        request = make_request_with_session({'invite_token': str(invite.token)})
        self.assertFalse(self.adapter.is_open_for_signup(request))

    def test_closed_with_nonexistent_token(self):
        import uuid
        request = make_request_with_session({'invite_token': str(uuid.uuid4())})
        self.assertFalse(self.adapter.is_open_for_signup(request))


class InviteSocialAccountAdapterTestCase(TestCase):

    def setUp(self):
        self.adapter = InviteSocialAccountAdapter()
        self.staff = build_user('staff')
        self.staff.is_staff = True
        self.staff.save()

    def test_open_for_signup_with_valid_token(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        request = make_request_with_session({'invite_token': str(invite.token)})
        self.assertTrue(self.adapter.is_open_for_signup(request, sociallogin=None))

    def test_closed_with_no_token_in_session(self):
        request = make_request_with_session()
        self.assertFalse(self.adapter.is_open_for_signup(request, sociallogin=None))

    def test_closed_with_expired_token(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.expires_at = timezone.now() - timedelta(seconds=1)
        invite.save()
        request = make_request_with_session({'invite_token': str(invite.token)})
        self.assertFalse(self.adapter.is_open_for_signup(request, sociallogin=None))

    def test_closed_with_used_token(self):
        user = build_user('user1')
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.used_by = user
        invite.used_at = timezone.now()
        invite.save()
        request = make_request_with_session({'invite_token': str(invite.token)})
        self.assertFalse(self.adapter.is_open_for_signup(request, sociallogin=None))
