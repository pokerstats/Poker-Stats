from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404

from invite.models import Invite


def staff_required(view_func):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped


@staff_required
def delete_invite_view(request, token):
    if request.method == 'POST':
        invite = get_object_or_404(Invite, token=token)
        invite.delete()
    return redirect('invite:manage')


@staff_required
def invite_management_view(request):
    if request.method == 'POST':
        invite = Invite.objects.create_invite(created_by=request.user)
        invite_url = request.build_absolute_uri(
            f'/invite/{invite.token}/accept/'
        )
        messages.success(request, f'Invite link generated: {invite_url}')
        return redirect('invite:manage')

    invites = Invite.objects.get_all_invites()
    return render(request, 'invite/manage.html', {'invites': invites})


def accept_invite_view(request, token):
    invite = Invite.objects.get_by_token(token)
    if invite is None or not invite.is_valid:
        return render(request, 'invite/invite_invalid.html', status=410)

    request.session['invite_token'] = str(token)
    return render(request, 'invite/invite_accepted.html')
