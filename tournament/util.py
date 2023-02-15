from dataclasses import dataclass

DID_NOT_PLACE_VALUE = 999999999

"""
player_id: TournamentPlayer id.
placement: Where they placed in the tournament. 1 is considered 1st place.
"""
@dataclass
class PlayerTournamentPlacement:
	player_id: int
	placement: int

"""
A utility data holder class for modeling information used in complex views like tournament_admin_view.
player_id: TournamentPlayer pk
"""
@dataclass
class PlayerTournamentData:
	player_id: int
	username: str
	rebuys: int
	bounties: int
	is_eliminated: bool

"""
A player and all the players they eliminated.
"""
@dataclass
class PlayerEliminationsData:
	# id of the user who did the eliminating.
	player_id: int

	# username of the user who did the eliminating.
	player_username: int

	# username's of the players that were eliminated.
	eliminated_player_usernames: list[str]

	# Amount earned from bounties
	bounty_earnings: float

def build_placement_string(placement):
	if placement == 0:
		return "1st"
	elif placement == 1:
		return "2nd"
	elif placement == 2:
		return "3rd"
	elif placement == DID_NOT_PLACE_VALUE:
		return "--"
	else:
		return f"{placement + 1}th"

"""
Used in a template to apply styling based on placement.

input: [Decimal(60), Decimal(30), Decimal(20)]
output: "1, 2, 3"
"""
def payout_positions(percentages):
	placements = ""
	for i in range(0, len(percentages)):
		placements += f"{i}"
		if i != len(percentages):
			placements += ","
	return placements

"""
Builds a PlayerEliminationsData.
eliminator: The TournamentPlayer who did the eliminating.
eliminations: List of TournamentElimination's for the eliminator.

Return None if they did not eliminate anyone.
"""
def build_player_eliminations_data_from_eliminations(eliminator, eliminations):
	eliminated_usernames = []
	for elimination in eliminations:
		eliminated_usernames.append(elimination.eliminatee.user.username)
	if len(eliminated_usernames) > 0:
		bounty_amount = eliminator.tournament.tournament_structure.bounty_amount
		bounty_earnings = 0
		if bounty_amount != None:
			bounty_earnings = float(bounty_amount) * float(len(eliminated_usernames))
		data = PlayerEliminationsData(
			player_id = eliminator.id,
			player_username = eliminator.user.username,
			eliminated_player_usernames = eliminated_usernames,
			bounty_earnings = bounty_earnings
		)
		return data
	return None












