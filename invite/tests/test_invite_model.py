from datetime import timedelta

from django.test import TransactionTestCase
from django.utils import timezone

from invite.models import Invite
from user.test_util import build_user


class InviteIsValidTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.staff = build_user('staff')
        self.staff.is_staff = True
        self.staff.save()

    def test_is_valid_when_unused_and_not_expired(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        self.assertTrue(invite.is_valid)

    def test_is_invalid_when_used(self):
        user = build_user('user1')
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.used_by = user
        invite.used_at = timezone.now()
        invite.save()
        self.assertFalse(invite.is_valid)

    def test_is_invalid_when_expired(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.expires_at = timezone.now() - timedelta(seconds=1)
        invite.save()
        self.assertFalse(invite.is_valid)

    def test_is_invalid_when_used_and_expired(self):
        user = build_user('user2')
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.used_by = user
        invite.used_at = timezone.now()
        invite.expires_at = timezone.now() - timedelta(seconds=1)
        invite.save()
        self.assertFalse(invite.is_valid)


class InviteManagerTestCase(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.staff = build_user('staff')
        self.staff.is_staff = True
        self.staff.save()

    def test_create_invite_sets_expires_at_7_days(self):
        before = timezone.now() + timedelta(days=7) - timedelta(seconds=1)
        invite = Invite.objects.create_invite(created_by=self.staff)
        after = timezone.now() + timedelta(days=7) + timedelta(seconds=1)
        self.assertGreater(invite.expires_at, before)
        self.assertLess(invite.expires_at, after)

    def test_create_invite_sets_created_by(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        self.assertEqual(invite.created_by, self.staff)

    def test_get_by_token_returns_invite(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        result = Invite.objects.get_by_token(invite.token)
        self.assertEqual(result, invite)

    def test_get_by_token_returns_none_for_missing_token(self):
        import uuid
        result = Invite.objects.get_by_token(uuid.uuid4())
        self.assertIsNone(result)

    def test_get_all_invites_returns_all(self):
        Invite.objects.create_invite(created_by=self.staff)
        Invite.objects.create_invite(created_by=self.staff)
        Invite.objects.create_invite(created_by=self.staff)
        self.assertEqual(Invite.objects.get_all_invites().count(), 3)
