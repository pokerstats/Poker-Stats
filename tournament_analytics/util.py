from collections import defaultdict
from django.contrib.humanize.templatetags.humanize import naturalday
from django.utils import timezone
from decimal import Decimal
import json
import random

from tournament.models import (
	TournamentPlayerResult,
	TournamentElimination,
	TournamentSplitElimination,
	TournamentRebuy
)
from tournament.util import get_value_or_default

def build_json_from_tournament_totals_data(list_of_tournament_totals):
	data_list = []
	for item in list_of_tournament_totals:
		data = {
			'timestamp': naturalday(item.timestamp),
			'net_earnings': f"{item.net_earnings}",
			'losses': f"{item.losses}",
			'gross_earnings': f"{item.gross_earnings}"
		}
		data_list.append(data)
	return json.dumps(data_list)

"""
Build json of TournamentPlayerResult data for each tournament.
"""
def build_tournament_player_result_data(players):
	completed_players = [p for p in players if p.tournament.completed_at is not None]
	if not completed_players:
		return json.dumps({})

	player_ids = [p.id for p in completed_players]
	player_id_set = set(player_ids)

	# Bulk fetch all needed data in 4 queries instead of 4N
	results_by_player = {
		r.player_id: r
		for r in TournamentPlayerResult.objects.filter(
			player_id__in=player_ids
		).select_related('tournament', 'player')
	}

	eliminations_by_player = defaultdict(list)
	for e in TournamentElimination.objects.filter(eliminator_id__in=player_ids):
		eliminations_by_player[e.eliminator_id].append(e)

	split_elims_by_player = defaultdict(list)
	for se in TournamentSplitElimination.objects.filter(
		eliminators__in=player_ids
	).prefetch_related('eliminators').distinct():
		for elim in se.eliminators.all():
			if elim.id in player_id_set:
				split_elims_by_player[elim.id].append(se)

	rebuys_by_player = defaultdict(list)
	for r in TournamentRebuy.objects.filter(player_id__in=player_ids):
		rebuys_by_player[r.player_id].append(r)

	completed_players_sorted = sorted(
		completed_players,
		key=lambda x: get_value_or_default(x.tournament.completed_at, timezone.now()),
		reverse=False
	)

	result_dict = {}
	for player in completed_players_sorted:
		result = results_by_player.get(player.id)
		if result:
			eliminations = eliminations_by_player[player.id]
			split_elims = split_elims_by_player[player.id]
			split_count = sum(1.0 / len(se.eliminators.all()) for se in split_elims)
			rebuys = rebuys_by_player[player.id]
			result_dict[f"{player.tournament.completed_at}"] = {
				'placement': result.placement,
				'net_earnings': f"{result.net_earnings}",
				'gross_earnings': f"{result.gross_earnings}",
				'tournament_title': result.tournament.title,
				'completed_at': naturalday(result.tournament.completed_at),
				'eliminations': f"{round(Decimal(len(eliminations) + split_count), 2)}",
				'rebuys': len(rebuys),
				'losses': f"{result.investment}",
			}
	return json.dumps(result_dict)

"""
Build json of eliminations on per-user basis. In otherwords, how many times you eliminated each player.

The json object also contains a color for each player they eliminatied. This is for chart coloring.

[
	{
		"username": "<username1>",
		"count": <elim_count>,
		"color": <rgbcolor>
	},
	{
		"username": "<username2>",
		"count": <elim_count>,
		"color": <rgbcolor>
	},
	...
]
"""
def build_player_eliminations_data(players):
	completed_players = [p for p in players if p.tournament.completed_at is not None]
	if not completed_players:
		return json.dumps([])

	player_ids = [p.id for p in completed_players]
	player_id_set = set(player_ids)

	eliminations_dict = {}

	# Bulk fetch regular eliminations
	for e in TournamentElimination.objects.filter(
		eliminator_id__in=player_ids
	).select_related('eliminatee__user'):
		username = e.eliminatee.user.username
		eliminations_dict[username] = eliminations_dict.get(username, 0) + 1

	# Bulk fetch split eliminations
	for se in TournamentSplitElimination.objects.filter(
		eliminators__in=player_ids
	).prefetch_related('eliminators').select_related('eliminatee__user').distinct():
		eliminator_count = len(se.eliminators.all())
		username = se.eliminatee.user.username
		eliminations_dict[username] = eliminations_dict.get(username, 0) + (1.0 / eliminator_count)

	eliminations = []
	for username, count in eliminations_dict.items():
		color_list = list(random.choices(range(256), k=3))
		color = f"rgb({color_list[0]}, {color_list[1]}, {color_list[2]})"
		eliminations.append({
			'username': username,
			'short_username': shorten_string(username, 15),
			'count': count,
			'color': color,
		})

	eliminations.sort(key=lambda x: x['count'], reverse=True)
	return json.dumps(eliminations)


def shorten_string(string, length):
	if len(string) > length:
		return f"{string[:length]}..."
	return string


"""
Build a dictionary of the rebuys, eliminations and split eliminations data.

"""
def build_rebuys_and_eliminations_data(players):
	completed_players = [p for p in players if p.tournament.completed_at is not None]
	if not completed_players:
		return json.dumps({})

	player_ids = [p.id for p in completed_players]
	player_id_set = set(player_ids)

	# Bulk fetch all needed data in 3 queries instead of 3N
	eliminations_by_player = defaultdict(list)
	for e in TournamentElimination.objects.filter(eliminator_id__in=player_ids):
		eliminations_by_player[e.eliminator_id].append(e)

	split_elims_by_player = defaultdict(list)
	for se in TournamentSplitElimination.objects.filter(
		eliminators__in=player_ids
	).prefetch_related('eliminators').distinct():
		for elim in se.eliminators.all():
			if elim.id in player_id_set:
				split_elims_by_player[elim.id].append(se)

	rebuys_by_player = defaultdict(list)
	for r in TournamentRebuy.objects.filter(player_id__in=player_ids):
		rebuys_by_player[r.player_id].append(r)

	completed_players_sorted = sorted(
		completed_players,
		key=lambda x: get_value_or_default(x.tournament.completed_at, timezone.now()),
		reverse=False
	)

	result_dict = {}
	for player in completed_players_sorted:
		eliminations = eliminations_by_player[player.id]
		split_elims = split_elims_by_player[player.id]
		split_count = sum(1.0 / len(se.eliminators.all()) for se in split_elims)
		rebuys = rebuys_by_player[player.id]
		result_dict[f"{player.tournament.completed_at}"] = {
			'eliminations': f"{round(Decimal(len(eliminations) + split_count), 2)}",
			'rebuys': len(rebuys),
			'tournament_title': player.tournament.title,
			'completed_at': naturalday(player.tournament.completed_at),
		}
	return json.dumps(result_dict)
