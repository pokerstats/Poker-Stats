from dataclasses import dataclass, field

from tournament.models import Tournament, TournamentPlayer, TournamentElimination, TournamentStructure
from user.models import User


"""
A utility data holder class that makes testing TournamentPlayerResults easier.
"""
@dataclass
class PlayerPlacementData:
	user_id: int
	placement: int
	placement_earnings: str
	gross_earnings: str
	investment: str
	net_earnings: str
	bounty_earnings: str
	rebuys: int
	eliminations: list[int] = field(default_factory=list)

"""
Convenience function for adding players to a tournament in tests.
Do not add the admin since they are automatically added.
"""
def add_players_to_tournament(users, tournament):
	players = []
	for user in users:
		if user != tournament.admin:
			player = TournamentPlayer.objects.create_player_for_tournament(
				user_id = user.id,
				tournament_id = tournament.id
			)
			players.append(player)
	return players

"""
Convenience function for completing a tournament in tests.
"""
def eliminate_players_and_complete_tournament(admin, tournament):
	# eliminate all the players except 1. Must do this before completing.
	players = TournamentPlayer.objects.get_tournament_players(
		tournament_id = tournament.id
	)
	for i in range(1, len(players), 1):
		TournamentElimination.objects.create_elimination(
			tournament_id = tournament.id,
			eliminator_id = players[0].user.id,
			eliminatee_id = players[i].user.id
		)
	# Complete the tournament
	Tournament.objects.complete_tournament(user = admin, tournament_id = tournament.id)

"""
Convenience function for building a tournament in tests.
"""
def build_tournament(structure):
	admin = User.objects.get_by_username("cat")

	# Build a Tournament with the only structure available.
	tournament = Tournament.objects.create_tournament(
		title = "Tournament name",
		user = admin,
		tournament_structure = structure
	)
	return tournament

"""
Convenience function for building a tournament structure in tests.
"""
def build_structure(admin, buyin_amount, bounty_amount, payout_percentages, allow_rebuys):
	structure = TournamentStructure.objects.create_tournament_struture(
		title = "Structure name",
		user = admin,
		buyin_amount = buyin_amount,
		bounty_amount = bounty_amount,
		payout_percentages = payout_percentages,
		allow_rebuys = allow_rebuys
	)
	return structure

"""
Convenience function for eliminating players in tests
"""
def eliminate_player(tournament_id, eliminator_id, eliminatee_id):
	elimination = TournamentElimination.objects.create_elimination(
					tournament_id = tournament_id,
					eliminator_id = eliminator_id,
					eliminatee_id = eliminatee_id
				)
	return elimination

def eliminate_all_players_except(players, except_user, tournament):
	# Eliminate all the players except 1 (except_user)
	eliminations = []
	for player in players:
		if player.user.username != except_user.username:
			elimination = eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = except_user.id,
				eliminatee_id = player.user.id
			)
			eliminations.append(elimination)
	return eliminations





















