from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from tournament.models import (
	TournamentPlayerResult,
	TournamentStructure,
	TournamentElimination,
	Tournament,
	TournamentPlayer,
	TournamentState,
	TournamentRebuy,
	TournamentSplitElimination
)
from tournament.util import (
	PlayerTournamentPlacement,
	DID_NOT_PLACE_VALUE
)
from tournament.test_util import (
	build_tournament,
	build_structure,
	add_players_to_tournament
)

from tournament_analytics.models import (
	TournamentTotals
)

from user.models import User
from user.test_util import (
	create_users,
	build_user
)


class TournamentTotalsTestCase(TestCase):

	def setUp(self):
		# Build some users for the tests
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)

		structure = build_structure(
			admin = users[0], # Cat is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = True
		)

		self.tournament = build_tournament(structure)

	def verify_result(self, user, num_tournaments, expected_eliminations_count, expected_rebuys_count):
		# Get the results. We can use this to verify TournamentTotals.
		results = []
		tournament_players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(
			user_id = user.id
		)
		for player in tournament_players:
			result = TournamentPlayerResult.objects.get_results_by_player(
				player = player
			)
			results.append(result[0])
		expected_gross_earnings = Decimal(0)
		expected_net_earnings = Decimal(0)
		expected_losses = Decimal(0)
		most_recent_tournament = results[0].player.tournament
		for result in results:
			expected_gross_earnings += result.gross_earnings
			expected_net_earnings += result.net_earnings
			expected_losses += result.investment

			if result.player.tournament.completed_at > most_recent_tournament.completed_at:
				most_recent_tournament = result.player.tournament
		
		# TournamentTotals
		tournament_totals = TournamentTotals.objects.get_or_build_tournament_totals_by_user_id(player.user.id)
		tournament_totals = sorted(tournament_totals, key=lambda x: x.timestamp, reverse=False)
		self.assertEqual(len(tournament_totals), num_tournaments)

		# only verify the most recent tournament
		total = tournament_totals[len(tournament_totals) - 1]
		self.assertEqual(total.tournaments_played, num_tournaments)
		self.assertEqual(total.gross_earnings, expected_gross_earnings)
		self.assertEqual(total.net_earnings, expected_net_earnings)
		self.assertEqual(total.losses, expected_losses)
		self.assertEqual(total.eliminations, expected_eliminations_count)
		self.assertEqual(total.rebuys, expected_rebuys_count)

		# Timestamp should be same as most recent tournament
		self.assertEqual(total.timestamp, most_recent_tournament.completed_at)

	"""
	Pass in a dict to build the placements list.
	format:
	{
		<playerid>: 0,
		<playerid>: 1,
		<playerid>: 2,
		...
	}
	"""
	def build_tournament_placements_data(self, placement_dict):
		placements = []
		for player_id in placement_dict:
			placements.append(
				PlayerTournamentPlacement(
					player_id = player_id,
					placement = placement_dict[player_id]
				)
			)
		return placements

	"""
	Test the TournamentTotals generated when each player has participated in a single tournament.
	"""
	def test_build_tournament_totals_for_single_tournament(self):
		# Tournament
		tournament = self.tournament

		users = User.objects.all()
		cat = User.objects.get_by_username("cat")

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = tournament
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		cat = User.objects.get_by_username("cat")
		dog = User.objects.get_by_username("dog")
		bird = User.objects.get_by_username("bird")
		monkey = User.objects.get_by_username("monkey")
		donkey = User.objects.get_by_username("donkey")
		elephant = User.objects.get_by_username("elephant")
		gator = User.objects.get_by_username("gator")
		insect = User.objects.get_by_username("insect")
		racoon = User.objects.get_by_username("racoon")

		cat_player = players.filter(user=cat)[0]
		dog_player = players.filter(user=dog)[0]
		bird_player = players.filter(user=bird)[0]
		monkey_player = players.filter(user=monkey)[0]
		donkey_player = players.filter(user=donkey)[0]
		elephant_player = players.filter(user=elephant)[0]
		gator_player = players.filter(user=gator)[0]
		insect_player = players.filter(user=insect)[0]
		racoon_player = players.filter(user=racoon)[0]

		"""
		Build data so we can backfill a tournament.

		Based on this we can generate the results using Tournament.complete_tournament_for_backfill.
		"""
		elim_dict = {
			cat_player.id: [dog_player, monkey_player],
			dog_player.id: [cat_player, gator_player],
			bird_player.id: [],
			monkey_player.id: [racoon_player, gator_player, insect_player, bird_player, donkey_player],
			donkey_player.id: [],
			elephant_player.id: [dog_player],
			gator_player.id: [],
			insect_player.id: [racoon_player, gator_player, monkey_player],
			racoon_player.id: [elephant_player],
		}
		split_eliminations = [
			{
				'eliminators': [cat_player, elephant_player],
				'eliminatee': dog_player
			},
			{
				'eliminators': [donkey_player, insect_player, racoon_player],
				'eliminatee': monkey_player
			},
		]

		placement_dict = {
			cat_player.id: 0,
			dog_player.id: 1,
			gator_player.id: 2,
			bird_player.id: DID_NOT_PLACE_VALUE,
			monkey_player.id: DID_NOT_PLACE_VALUE,
			donkey_player.id: DID_NOT_PLACE_VALUE,
			elephant_player.id: DID_NOT_PLACE_VALUE,
			insect_player.id: DID_NOT_PLACE_VALUE,
			racoon_player.id: DID_NOT_PLACE_VALUE,
		}
		player_tournament_placements = self.build_tournament_placements_data(placement_dict)

		# Backfill the tournament with the above data.
		Tournament.objects.complete_tournament_for_backfill(
			user = cat,
			tournament_id = tournament.id,
			player_tournament_placements = player_tournament_placements,
			elim_dict = elim_dict,
			split_eliminations = split_eliminations
		)

		for player in players:
			if player == cat_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(2.50), 2),
					expected_rebuys_count = 1
				)
			elif player == dog_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(2), 2),
					expected_rebuys_count = 2
				)
			elif player == bird_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(0), 2),
					expected_rebuys_count = 0
				)
			elif player == donkey_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(0.33), 2),
					expected_rebuys_count = 0
				)
			elif player == monkey_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(5), 2),
					expected_rebuys_count = 2
				)
			elif player == elephant_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(1.5), 2),
					expected_rebuys_count = 0
				)
			elif player == insect_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(3.33), 2),
					expected_rebuys_count = 0
				)
			elif player == racoon_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(1.33), 2),
					expected_rebuys_count = 1
				)
			elif player == gator_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 1,
					expected_eliminations_count = round(Decimal(0), 2),
					expected_rebuys_count = 2
				)

	"""
	Test the TournamentTotals generated when each player has participated in 2 tournaments.
	"""
	def test_build_tournament_totals_for_two_tournaments(self):
		# First Tournament
		tournament = self.tournament

		users = User.objects.all()
		cat = User.objects.get_by_username("cat")

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = tournament
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		dog = User.objects.get_by_username("dog")
		bird = User.objects.get_by_username("bird")
		monkey = User.objects.get_by_username("monkey")
		donkey = User.objects.get_by_username("donkey")
		elephant = User.objects.get_by_username("elephant")
		gator = User.objects.get_by_username("gator")
		insect = User.objects.get_by_username("insect")
		racoon = User.objects.get_by_username("racoon")

		cat_player = players.filter(user=cat)[0]
		dog_player = players.filter(user=dog)[0]
		bird_player = players.filter(user=bird)[0]
		monkey_player = players.filter(user=monkey)[0]
		donkey_player = players.filter(user=donkey)[0]
		elephant_player = players.filter(user=elephant)[0]
		gator_player = players.filter(user=gator)[0]
		insect_player = players.filter(user=insect)[0]
		racoon_player = players.filter(user=racoon)[0]

		"""
		Build data so we can backfill a tournament.

		Based on this we can generate the results using Tournament.complete_tournament_for_backfill.
		"""
		elim_dict = {
			cat_player.id: [dog_player, monkey_player],
			dog_player.id: [cat_player, gator_player],
			bird_player.id: [],
			monkey_player.id: [racoon_player, gator_player, insect_player, bird_player, donkey_player],
			donkey_player.id: [],
			elephant_player.id: [dog_player],
			gator_player.id: [],
			insect_player.id: [racoon_player, gator_player, monkey_player],
			racoon_player.id: [elephant_player],
		}
		split_eliminations = [
			{
				'eliminators': [cat_player, elephant_player],
				'eliminatee': dog_player
			},
			{
				'eliminators': [donkey_player, insect_player, racoon_player],
				'eliminatee': monkey_player
			},
		]

		placement_dict = {
			cat_player.id: 0,
			dog_player.id: 1,
			gator_player.id: 2,
			bird_player.id: DID_NOT_PLACE_VALUE,
			monkey_player.id: DID_NOT_PLACE_VALUE,
			donkey_player.id: DID_NOT_PLACE_VALUE,
			elephant_player.id: DID_NOT_PLACE_VALUE,
			insect_player.id: DID_NOT_PLACE_VALUE,
			racoon_player.id: DID_NOT_PLACE_VALUE,
		}
		player_tournament_placements = self.build_tournament_placements_data(placement_dict)

		# Backfill the tournament with the above data.
		Tournament.objects.complete_tournament_for_backfill(
			user = cat,
			tournament_id = tournament.id,
			player_tournament_placements = player_tournament_placements,
			elim_dict = elim_dict,
			split_eliminations = split_eliminations
		)

		# Second tournament
		structure = build_structure(
			admin = users[0], # Cat is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = True
		)

		tournament2 = build_tournament(structure)

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = tournament2
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament2.id
		)

		dog = User.objects.get_by_username("dog")
		bird = User.objects.get_by_username("bird")
		monkey = User.objects.get_by_username("monkey")
		donkey = User.objects.get_by_username("donkey")
		elephant = User.objects.get_by_username("elephant")
		gator = User.objects.get_by_username("gator")
		insect = User.objects.get_by_username("insect")
		racoon = User.objects.get_by_username("racoon")

		cat_player = players.filter(user=cat)[0]
		dog_player = players.filter(user=dog)[0]
		bird_player = players.filter(user=bird)[0]
		monkey_player = players.filter(user=monkey)[0]
		donkey_player = players.filter(user=donkey)[0]
		elephant_player = players.filter(user=elephant)[0]
		gator_player = players.filter(user=gator)[0]
		insect_player = players.filter(user=insect)[0]
		racoon_player = players.filter(user=racoon)[0]

		"""
		Build data so we can backfill a tournament.

		Based on this we can generate the results using Tournament.complete_tournament_for_backfill.
		"""
		elim_dict2 = {
			cat_player.id: [],
			dog_player.id: [racoon_player, insect_player, gator_player],
			bird_player.id: [],
			monkey_player.id: [elephant_player, dog_player, gator_player, gator_player, insect_player],
			donkey_player.id: [cat_player],
			elephant_player.id: [gator_player, dog_player, bird_player],
			gator_player.id: [racoon_player],
			insect_player.id: [racoon_player, bird_player, monkey_player],
			racoon_player.id: [donkey_player],
		}
		split_eliminations2 = [
			{
				'eliminators': [cat_player, dog_player, bird_player],
				'eliminatee': racoon_player
			},
			{
				'eliminators': [elephant_player, insect_player],
				'eliminatee': gator_player
			},
		]

		placement_dict2 = {
			racoon_player.id: 0,
			elephant_player.id: 1,
			bird_player.id: 2,
			cat_player.id: DID_NOT_PLACE_VALUE,
			dog_player.id: DID_NOT_PLACE_VALUE,
			donkey_player.id: DID_NOT_PLACE_VALUE,
			monkey_player.id: DID_NOT_PLACE_VALUE,
			insect_player.id: DID_NOT_PLACE_VALUE,
			gator_player.id: DID_NOT_PLACE_VALUE,
		}
		player_tournament_placements2 = self.build_tournament_placements_data(placement_dict2)

		# Backfill the tournament with the above data.
		Tournament.objects.complete_tournament_for_backfill(
			user = cat,
			tournament_id = tournament2.id,
			player_tournament_placements = player_tournament_placements2,
			elim_dict = elim_dict2,
			split_eliminations = split_eliminations2
		)

		for player in players:
			if player == cat_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(2.83), 2),
					expected_rebuys_count = 1
				)
			elif player == dog_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(5.33), 2),
					expected_rebuys_count = 3
				)
			elif player == bird_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(0.33), 2),
					expected_rebuys_count = 1
				)
			elif player == donkey_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(1.33), 2),
					expected_rebuys_count = 0
				)
			elif player == monkey_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(10), 2),
					expected_rebuys_count = 2
				)
			elif player == elephant_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(5), 2),
					expected_rebuys_count = 0
				)
			elif player == insect_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(6.83), 2),
					expected_rebuys_count = 1
				)
			elif player == racoon_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(2.33), 2),
					expected_rebuys_count = 5
				)
			elif player == gator_player:
				self.verify_result(
					user = player.user,
					num_tournaments = 2,
					expected_eliminations_count = round(Decimal(1), 2),
					expected_rebuys_count = 6
				)
























