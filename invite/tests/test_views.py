from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from invite.models import Invite
from user.test_util import build_user


class AcceptInviteViewTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = build_user('staff')
        self.staff.is_staff = True
        self.staff.save()

    def test_valid_token_returns_200(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        url = reverse('invite:accept', kwargs={'token': invite.token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_valid_token_stores_in_session(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        url = reverse('invite:accept', kwargs={'token': invite.token})
        self.client.get(url)
        self.assertEqual(self.client.session.get('invite_token'), str(invite.token))

    def test_expired_token_returns_410(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.expires_at = timezone.now() - timedelta(seconds=1)
        invite.save()
        url = reverse('invite:accept', kwargs={'token': invite.token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)

    def test_used_token_returns_410(self):
        user = build_user('user1')
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.used_by = user
        invite.used_at = timezone.now()
        invite.save()
        url = reverse('invite:accept', kwargs={'token': invite.token})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)

    def test_nonexistent_token_returns_410(self):
        import uuid
        url = reverse('invite:accept', kwargs={'token': uuid.uuid4()})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 410)

    def test_expired_token_does_not_store_in_session(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        invite.expires_at = timezone.now() - timedelta(seconds=1)
        invite.save()
        url = reverse('invite:accept', kwargs={'token': invite.token})
        self.client.get(url)
        self.assertIsNone(self.client.session.get('invite_token'))


class InviteManagementViewTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = build_user('staff')
        self.staff.is_staff = True
        self.staff.save()
        self.regular_user = build_user('regular')

    def test_staff_can_access(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('invite:manage'))
        self.assertEqual(response.status_code, 200)

    def test_non_staff_gets_403(self):
        self.client.force_login(self.regular_user)
        response = self.client.get(reverse('invite:manage'))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_redirects_to_login(self):
        response = self.client.get(reverse('invite:manage'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response['Location'])

    def test_post_creates_invite(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('invite:manage'))
        self.assertEqual(Invite.objects.count(), 1)

    def test_post_sets_created_by(self):
        self.client.force_login(self.staff)
        self.client.post(reverse('invite:manage'))
        invite = Invite.objects.first()
        self.assertEqual(invite.created_by, self.staff)


class DeleteInviteViewTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.staff = build_user('staff')
        self.staff.is_staff = True
        self.staff.save()
        self.regular_user = build_user('regular')

    def test_staff_can_delete(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        self.client.force_login(self.staff)
        self.client.post(reverse('invite:delete', kwargs={'token': invite.token}))
        self.assertEqual(Invite.objects.count(), 0)

    def test_non_staff_gets_403(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        self.client.force_login(self.regular_user)
        response = self.client.post(reverse('invite:delete', kwargs={'token': invite.token}))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Invite.objects.count(), 1)

    def test_delete_redirects_to_manage(self):
        invite = Invite.objects.create_invite(created_by=self.staff)
        self.client.force_login(self.staff)
        response = self.client.post(reverse('invite:delete', kwargs={'token': invite.token}))
        self.assertRedirects(response, reverse('invite:manage'))
