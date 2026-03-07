from django.core.exceptions import ValidationError
from django.core import serializers
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse


import json
from tournament.models import TournamentPlayer
from tournament_analytics.models import TournamentTotals
from tournament_group.models import TournamentGroup
from tournament_analytics.util import (
	build_all_chart_data,
	build_json_from_tournament_totals_data,
	build_tournament_player_result_data,
	build_player_eliminations_data,
	build_rebuys_and_eliminations_data
)

@login_required
def stats_view(request, *args, **kwargs):
	context = {}
	tournament_groups = TournamentGroup.objects.get_tournament_groups(user_id=request.user.id)
	if len(tournament_groups) > 0:
		context['tournament_groups'] = tournament_groups
	context['analytics_data'] = build_all_chart_data(request.user.id)
	return render(request=request, template_name='tournament_analytics/stats.html', context=context)

@login_required
def fetch_all_analytics_data(request, *args, **kwargs):
	try:
		user_id = kwargs['user_id']
		data = build_all_chart_data(user_id)
	except Exception as e:
		return JsonResponse({'error': 'Unable to retrieve analytics data.', 'message': f'{e.args[0]}'}, status=200)
	return JsonResponse(data, status=200)

"""
Request for retrieving the TournamentTotals data for a user.
"""
@login_required
def fetch_tournament_totals_data(request, *args, **kwargs):
	context = {}
	try:
		user_id = kwargs['user_id']

		# Get TournamentTotals data
		tournament_totals = TournamentTotals.objects.get_or_build_tournament_totals_by_user_id(user_id = user_id)
		tournament_totals = sorted(tournament_totals, key=lambda x: x.timestamp, reverse=False)

		serialized_tournament_totals = build_json_from_tournament_totals_data(tournament_totals)
		context['tournament_totals'] = serialized_tournament_totals
	except Exception as e:
		error = {
			'error': "Unable to retrieve tournament totals data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)

"""
Request for retrieving the TournamentPlayerResult data for a user.
"""
@login_required
def fetch_tournament_player_results_data(request, *args, **kwargs):
	context = {}
	try:
		user_id = kwargs['user_id']

		tournament_players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(user_id)
		tournament_player_results_json = build_tournament_player_result_data(tournament_players)
		if tournament_player_results_json:
			context['tournament_player_results'] = tournament_player_results_json
		else:
			raise ValidationError("Error retrieving Tournament results data.")
	except Exception as e:
		error = {
			'error': "Unable to retrieve tournament results data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)
	
"""
Request for retrieving the eliminations data for each user they've eliminated.
"""
@login_required
def fetch_tournament_player_eliminations_data(request, *args, **kwargs):
	context = {}
	try:
		user_id = kwargs['user_id']

		tournament_players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(user_id)
		eliminations_json = build_player_eliminations_data(tournament_players)
		if eliminations_json:
			context['eliminations'] = eliminations_json
		else:
			raise ValidationError("Error retieving eliminations data.")
	except Exception as e:
		error = {
			'error': "Unable to retrieve tournament eliminations data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)

"""
Request for retrieving total eliminations and rebuys for a player..
"""
@login_required
def fetch_tournament_eliminations_and_rebuys_data(request, *args, **kwargs):
	context = {}
	try:
		user_id = kwargs['user_id']

		tournament_players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(user_id)
		rebuys_and_eliminations_json = build_rebuys_and_eliminations_data(tournament_players)
		if rebuys_and_eliminations_json:
			context['rebuys_and_eliminations'] = rebuys_and_eliminations_json
		else:
			raise ValidationError("Error retieving rebuys and eliminations data.")
	except Exception as e:
		error = {
			'error': "Unable to retrieve rebuys and eliminations data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)














