from django.contrib import messages
from django.shortcuts import render, redirect, reverse
from django.utils import timezone
from decimal import Decimal
import random

from tournament.models import TournamentPlayer
from tournament_group.models import TournamentGroup
from tournament_analytics.models import TournamentTotals

def root_view(request):
	try:
		user = request.user
		context = {}
		if user.is_authenticated:
			# get all the Tournaments that this user has joined
			tournament_players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(user.id)
			tournaments = []
			for player in tournament_players:
				tournaments.append(player.tournament)
			context['tournaments'] = tournaments

			# Tournament Groups
			tournament_groups = TournamentGroup.objects.get_tournament_groups(
				user_id = request.user.id
			)
			if len(tournament_groups) > 0:
				context['tournament_groups'] = tournament_groups

			return render(request, "root/root.html", context=context)
		else:
			return redirect("/accounts/login/")
	except Exception as e:
		messages.error(request, e.args[0])
		return render(request, "root/root.html", context={})

def contact_view(request):
	return render(request, "root/contact.html")

def error_view(request, *args, **kwargs):
	message = kwargs['error_message']
	context = {}
	context['message'] = message
	return render(request=request, template_name="root/error.html", context=context)








