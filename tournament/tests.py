from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from unittest import mock

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
from tournament.test_util import (
	add_players_to_tournament,
	build_tournament,
	build_structure,
	eliminate_players_and_complete_tournament,
	eliminate_all_players_except,
	eliminate_player,
	PlayerPlacementData,
	rebuy_for_test,
	split_eliminate_player
)
from tournament.util import PlayerTournamentPlacement, build_placement_string
from user.models import User
from user.test_util import (
	create_users,
	build_user
)

class TournamentPlayersTestCase(TestCase):

	def setup_tournament(self, admin, allow_rebuys):
		# Build a Structure that allows rebuys
		structure = build_structure(
			admin = admin,
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = allow_rebuys
		)

		return build_tournament(structure)


	def setUp(self):
		# Build some users for the tests
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)

	"""
	Verify the players are added correctly to the Tournament.
	"""
	def test_players_are_added_to_tournament(self):
		admin = User.objects.get_by_username("cat")

		tournament = self.setup_tournament(admin=admin, allow_rebuys=False)

		users = User.objects.all()

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			users = users,
			tournament = tournament
		)

		# Get the players
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		# Verify there are 9 players
		self.assertEqual(len(players), 9)

		# Verify there are no duplicate players
		usernames = map(lambda player: player.user.username, players)
		usernames_set = set(usernames)
		self.assertEqual(len(usernames_set), 9)

		# Verify you can't add a player twice
		for player in players:
			with self.assertRaisesMessage(ValidationError, f'{player.user.username} is already added to this tournament.'):
				TournamentPlayer.objects.create_player_for_tournament(
					user_id = player.user.id,
					tournament_id = tournament.id
				)

	"""
	Verifying the is_player_eliminated function works as expected when a player is split eliminated.
	"""
	def test_is_player_eliminated_when_split_eliminated(self):
		admin = User.objects.get_by_username("cat")

		tournament = self.setup_tournament(admin=admin, allow_rebuys=False)

		users = User.objects.all()

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			users = users,
			tournament = tournament
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("user__username")

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		admin_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = tournament.admin.id
		)

		# split eliminate player0
		split_eliminate_player(
			tournament_id = tournament.id,
			eliminator_ids = [players[1].id, players[2].id],
			eliminatee_id = players[0].id
		)

		# Confirm only player0 is eliminated
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(tournament.id)
		self.assertEqual(len(split_eliminations), 1)
		for split_elimination in split_eliminations:
			is_eliminated = TournamentPlayer.objects.is_player_eliminated(
				player_id = split_elimination.eliminatee.id,
			)
			if split_elimination.eliminatee.id == players[0].id:
				self.assertEqual(is_eliminated, True)
			else:
				self.assertEqual(is_eliminated, False)

	"""
	Verifying the is_player_eliminated function works as expected
	"""
	def test_is_eliminated(self):
		admin = User.objects.get_by_username("cat")

		tournament = self.setup_tournament(admin=admin, allow_rebuys=False)

		users = User.objects.all()

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			users = users,
			tournament = tournament
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("user__username")

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		admin_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = tournament.admin.id
		)

		# eliminate player0
		eliminate_player(
			tournament_id = tournament.id,
			eliminator_id = admin_player.id,
			eliminatee_id = players[0].id
		)

		# Confirm only player0 is eliminated
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(tournament.id)
		for elimination in eliminations:
			is_eliminated = TournamentPlayer.objects.is_player_eliminated(
				player_id=elimination.eliminatee.id,
			)
			if elimination.eliminatee.id == players[0].id:
				self.assertEqual(is_eliminated, True)
			else:
				self.assertEqual(is_eliminated, False)

	"""
	Verify you can't add or remove players from a Tournament that is completed.
	"""
	def test_cannot_add_or_remove_players_from_completed_tournament(self):
		admin = User.objects.get_by_username("cat")

		tournament = self.setup_tournament(admin=admin, allow_rebuys=False)

		users = User.objects.all()

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = tournament
		)

		Tournament.objects.start_tournament(user = admin, tournament_id = tournament.id)
		eliminate_players_and_complete_tournament(admin = admin, tournament = tournament)

		# Verify cannot add
		new_user = create_users(['horse'])[0]
		with self.assertRaisesMessage(ValidationError, "You can't add players to a Tournment that is completed."):
			TournamentPlayer.objects.create_player_for_tournament(
				user_id = new_user.id,
				tournament_id = tournament.id
			)

		# Verify cannot remove
		with self.assertRaisesMessage(ValidationError, "You can't remove players from a Tournment that is completed"):
			TournamentPlayer.objects.remove_player_from_tournament(
				removed_by_user_id = admin.id,
				removed_user_id = User.objects.get_by_username("dog").id,
				tournament_id = tournament.id
			)

	"""
	Verify you can't add or remove players from a Tournament that is started.
	"""
	def test_cannot_add_or_remove_players_from_started_tournament(self):
		admin = User.objects.get_by_username("cat")

		tournament = self.setup_tournament(admin=admin, allow_rebuys=False)

		users = User.objects.all()

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = tournament
		)

		Tournament.objects.start_tournament(user = admin, tournament_id = tournament.id)

		# Verify cannot add
		new_user = create_users(['horse'])[0]
		with self.assertRaisesMessage(ValidationError, "You can't add players to a Tournment that is started."):
			TournamentPlayer.objects.create_player_for_tournament(
				user_id = new_user.id,
				tournament_id = tournament.id
			)
		# Verify cannot remove
		with self.assertRaisesMessage(ValidationError, "You can't remove players from a Tournment that is started."):
			TournamentPlayer.objects.remove_player_from_tournament(
				removed_by_user_id = users[0].id,
				removed_user_id = users[1].id,
				tournament_id = tournament.id
			)

class TournamentRebuysTestCase(TestCase):
	
	def setup_tournament(self, allow_rebuys):
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)
		structure = build_structure(
			admin = users[0], # Cat is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = allow_rebuys
		)

		tournament = build_tournament(structure)

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = tournament
		)

		return tournament

	"""
	rebuy: player is not part of tournament.
	"""
	def test_rebuy_player_is_not_part_of_tournament(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)
		new_user = create_users(['horse'])[0]
		with self.assertRaisesMessage(ValidationError, "That player is not part of this tournament."):
			TournamentRebuy.objects.rebuy(
				tournament_id = tournament.id,
				player_id = new_user.id
			)

	"""
	rebuy: cannot rebuy if tournament is not active
	"""
	def test_rebuy_cannot_rebuy_if_tournament_not_active(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)
		cat = User.objects.get_by_username("cat")

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Activate
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Go through the players and eliminate
		for player in players:
			if player != cat_player:
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)

		# Deactivate the tournament
		tournament.started_at = None
		tournament.save()

		# Go through the players and try to rebuy
		for player in players:
			if player != cat_player:
				with self.assertRaisesMessage(ValidationError, "Cannot rebuy if Tournament is not active."):
					TournamentRebuy.objects.rebuy(
						tournament_id = tournament.id,
						player_id = player.id
					)

	"""
	rebuy: Tournament does not allow rebuys
	"""
	def test_rebuy_tournament_does_not_allow_rebuys(self):
		tournament = self.setup_tournament(
			allow_rebuys = False
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		for player in players:
			with self.assertRaisesMessage(ValidationError, "This tournament does not allow rebuys. Update the Tournament Structure."):
				TournamentRebuy.objects.rebuy(
					tournament_id = tournament.id,
					player_id = player.id
				)

	"""
	rebuy: Cannot rebuy if player has not been eliminated.
	"""
	def test_rebuy_cannot_rebuy_if_player_not_elimianted(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		cat = User.objects.get_by_username("cat")

		# Activate
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		for player in players:
			with self.assertRaisesMessage(ValidationError, f"{player.user.username} has not been eliminated. Eliminate them before adding another rebuy."):
				TournamentRebuy.objects.rebuy(
					tournament_id = tournament.id,
					player_id = player.id
				)

	"""
	rebuy: success.
	"""
	def test_rebuy_success(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		cat = User.objects.get_by_username("cat")

		# Activate
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Go through the players and eliminate, then rebuy
		for player in players:
			if player != cat_player:
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)
				rebuy = TournamentRebuy.objects.rebuy(
					tournament_id = tournament.id,
					player_id = player.id
				)
				self.assertEqual(rebuy.player.tournament, tournament)
				self.assertEqual(rebuy.player.user, player.user)
				self.assertEqual(rebuy.player, player)

	"""
	get_rebuys_for_user: success.
	"""
	def test_rebuys_for_user_success(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		cat = User.objects.get_by_username("cat")

		# Activate
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Go through the players and invoke get_rebuys_for_user. They should all be 0.
		for player in players:
			rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			self.assertEqual(len(rebuys), 0)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Eliminate players and rebuy on everyone except cat.
		for player in players:
			if player.user.username != "cat":
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)
				rebuy = TournamentRebuy.objects.rebuy(
					tournament_id = tournament.id,
					player_id = player.id
				)
				self.assertEqual(rebuy.player.tournament, tournament)
				self.assertEqual(rebuy.player, player)
				self.assertEqual(rebuy.player.user, player.user)

		# Go through the players and invoke get_rebuys_for_user. They should all be 1 except cat.
		for player in players:
			rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			if player == cat_player:
				self.assertEqual(len(rebuys), 0)
			else:
				self.assertEqual(len(rebuys), 1)


	"""
	get_rebuys_for_user: success when there is a split elimination.
	"""
	def test_rebuys_when_there_is_a_split_elimination_for_user_success(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		cat = User.objects.get_by_username("cat")

		# Activate
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Go through the players and invoke get_rebuys_for_user. They should all be 0.
		for player in players:
			rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			self.assertEqual(len(rebuys), 0)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		dog_user = User.objects.get_by_username("dog")
		dog_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = dog_user.id
		)

		# Eliminate players and rebuy on everyone except cat. Every second elimination should be a split elimination.
		for i, player in enumerate(players):
			if player.user.username != "cat" and player.user.username != "dog":
				if i % 2 == 0:
					split_eliminate_player(
						tournament_id = tournament.id,
						eliminator_ids = [cat_player.id, dog_player.id],
						eliminatee_id = player.id
					)
				else:
					eliminate_player(
						tournament_id = tournament.id,
						eliminator_id = cat_player.id,
						eliminatee_id = player.id
					)
				rebuy = TournamentRebuy.objects.rebuy(
					tournament_id = tournament.id,
					player_id = player.id
				)
				self.assertEqual(rebuy.player.tournament, tournament)
				self.assertEqual(rebuy.player, player)
				self.assertEqual(rebuy.player.user, player.user)

		# Then eliminate dog at the end
		eliminate_player(
			tournament_id = tournament.id,
			eliminator_id = cat_player.id,
			eliminatee_id = dog_player.id
		)
		rebuy = TournamentRebuy.objects.rebuy(
			tournament_id = tournament.id,
			player_id = dog_player.id
		)
		self.assertEqual(rebuy.player.tournament, tournament)
		self.assertEqual(rebuy.player, dog_player)
		self.assertEqual(rebuy.player.user, dog_player.user)

		# Go through the players and invoke get_rebuys_for_user. They should all be 1 except cat.
		for player in players:
			rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			if player == cat_player:
				self.assertEqual(len(rebuys), 0)
			else:
				self.assertEqual(len(rebuys), 1)


	"""
	get_rebuys_for_tournament: success.
	"""
	def test_rebuys_for_tournament_success(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		cat = User.objects.get_by_username("cat")

		# Activate
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Get total rebuys for tournament
		rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
			tournament_id = tournament.id,
		)
		self.assertEqual(len(rebuys), 0)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Eliminate players and rebuy on everyone except cat.
		for player in players:
			if player.user.username != "cat":
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)
				rebuy = TournamentRebuy.objects.rebuy(
					tournament_id = tournament.id,
					player_id = player.id
				)
				self.assertEqual(rebuy.player.tournament, tournament)
				self.assertEqual(rebuy.player, player)
				self.assertEqual(rebuy.player.user, player.user)

		# Get rebuys for tournament. Everyone rebought except cat, so rebuys should be 8.
		rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
			tournament_id = tournament.id,
		)
		self.assertEqual(len(rebuys), 8)

	"""
	delete_tournament_rebuys: success.
	"""
	def test_delete_tournament_rebuys(self):
		tournament = self.setup_tournament(
			allow_rebuys = True
		)

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		cat = User.objects.get_by_username("cat")

		# Activate
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Eliminate players and rebuy on everyone except cat.
		for player in players:
			if player != cat_player:
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)
				rebuy = TournamentRebuy.objects.rebuy(
					tournament_id = tournament.id,
					player_id = player.id
				)
				self.assertEqual(rebuy.player.tournament, tournament)
				self.assertEqual(rebuy.player.user, player.user)
				self.assertEqual(rebuy.player, player)

		# Get rebuys for tournament. Everyone rebought except cat, so rebuys should be 8.
		rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
			tournament_id = tournament.id,
		)
		self.assertEqual(len(rebuys), 8)

		# Delete the rebuys
		TournamentRebuy.objects.delete_tournament_rebuys(
			tournament_id = tournament.id
		)

		# Verify rebuy data is deleted
		rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
			tournament_id = tournament.id,
		)
		self.assertEqual(len(rebuys), 0)


class TournamentEliminationsTestCase(TestCase):

	def setUp(self):
		# Build some users for the tests
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)

		# Build a Structure with no bounties and no rebuys
		structure = build_structure(
			admin = users[0], # Cat is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = False
		)

		self.tournament = build_tournament(structure)

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = self.tournament
		)

	"""
	Test the eliminations
	"""
	def test_eliminations(self):
		tournament = self.tournament
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		# -- Create eliminations --

		# player0 eliminates player1
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[0].id,
			eliminatee_id = players[1].id
		)

		# player2 eliminates player3
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[2].id,
			eliminatee_id = players[3].id
		)

		# player4 eliminates player5
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[4].id,
			eliminatee_id = players[5].id
		)

		# player6 eliminates player7
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[6].id,
			eliminatee_id = players[7].id
		)

		# player0 eliminates player8
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[0].id,
			eliminatee_id = players[8].id
		)

		# At this point everyone is eliminated except player0

		# -- Verify eliminations --

		# Verify the eliminations by player0
		eliminations0 = TournamentElimination.objects.get_eliminations_by_eliminator(
			player_id = players[0].id
		)
		self.assertEqual(eliminations0[0].eliminatee.tournament, tournament)
		self.assertEqual(eliminations0[0].eliminator.tournament, tournament)
		self.assertEqual(eliminations0[1].eliminatee.tournament, tournament)
		self.assertEqual(eliminations0[1].eliminator.tournament, tournament)
		self.assertEqual(len(eliminations0), 2)
		# player0 eliminated player1
		self.assertEqual(eliminations0[0].eliminator, players[0])
		self.assertEqual(eliminations0[0].eliminatee, players[1])
		# player0 eliminated player8
		self.assertEqual(eliminations0[1].eliminator, players[0])
		self.assertEqual(eliminations0[1].eliminatee, players[8])

	"""
	Cannot eliminate a player who is not part of the tournament and cannot perform an elimination if the eliminator
	is not part of the tournment.
	"""
	def test_cannot_eliminate_user_who_has_not_joined_tournament(self):
		tournament = self.tournament
		tournament_id = tournament.id
		new_user = create_users(['horse'])[0]

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		with self.assertRaisesMessage(ValidationError, "Eliminatee is not part of that Tournament."):
			eliminate_player(
				tournament_id = tournament_id,
				eliminator_id = players[0].id,
				eliminatee_id = 9999999 # This will fail b/c its not a TournamentPlayer
			)

		with self.assertRaisesMessage(ValidationError, "Eliminator is not part of that Tournament."):
			eliminate_player(
				tournament_id = tournament_id,
				eliminator_id = 9999999, # This will fail b/c its not a TournamentPlayer
				eliminatee_id = players[0].id
			)

	"""
	Verify you cannot eliminate a player that is already eliminated
	"""
	def test_cannot_eliminate_player_who_is_already_eliminated(self):
		tournament = self.tournament
		tournament_id = tournament.id

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("user__username")

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		# eliminate player0
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[1].id,
			eliminatee_id = players[0].id
		)
		# Try to eliminate again. This will fail because they have already been eliminated and have no more rebuys.
		with self.assertRaisesMessage(ValidationError, f"{players[0].user.username} has already been eliminated and has no more re-buys."):
			eliminate_player(
				tournament_id = tournament_id,
				eliminator_id = players[1].id,
				eliminatee_id = players[0].id
			)

	"""
	Verify you cannot eliminate a player when the tournament is not started.
	"""
	def test_cannot_eliminate_player_when_tournament_not_active(self):
		tournament = self.tournament
		tournament_id = tournament.id

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("user__username")

		with self.assertRaisesMessage(ValidationError, "You can only eliminate players if the Tournament is Active."):
			eliminate_player(
				tournament_id = tournament_id,
				eliminator_id = players[1].id,
				eliminatee_id = players[0].id
			)

	"""
	Test cannot eliminate the final player. The Tournament should be completed.
	"""
	def test_cannot_eliminate_last_player(self):
		tournament = self.tournament
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		# -- Create eliminations --

		# Eliminate all players except player0
		eliminate_all_players_except(
			players = players,
			except_player = players[0],
			tournament = tournament
		)

		# At this point everyone is eliminated except player0
		# Try to eliminate them.
		with self.assertRaisesMessage(ValidationError, "You can't eliminate any more players. Complete the Tournament."):
			eliminate_player(
				tournament_id = tournament_id,
				eliminator_id = players[8].id,
				eliminatee_id = players[0].id
			)


class TournamentTestCase(TestCase):
	
	"""
	bounty_amount: If None, this is not a bounty tournament.
	"""
	def build_structure(self, user, buyin_amount, bounty_amount, payout_percentages, allow_rebuys):
		structure = build_structure(
			admin = user,
			buyin_amount = buyin_amount,
			bounty_amount = bounty_amount,
			payout_percentages = payout_percentages,
			allow_rebuys = allow_rebuys
		)
		return structure
	
	def build_tournament(self, admin, title, structure):
		tournament = Tournament.objects.create_tournament(
			title = title,
			user = admin,
			tournament_structure = structure
		)
		return tournament

	"""
	Verify any error occurs, the follow must happen:
		1. eliminations deleted
		2. rebuys deleted
		3. Tournament.started_at = None
		4. Tournament.completed_at = None
	"""
	def verify_tournament_reset(self, tournament_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		self.assertEqual(tournament.completed_at, None)
		self.assertEqual(tournament.started_at, None)
		rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(tournament.id)
		self.assertEqual(len(rebuys), 0)
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(tournament.id)
		self.assertEqual(len(eliminations), 0)

	"""
	bounty_amount can be None if not a bounty tournament.
	"""
	def verify_result(self, result, is_backfill, placement_string, placement_earnings, rebuy_count, eliminations_count, buyin_amount, bounty_amount):
		if bounty_amount == None:
			bounty_amount = 0
		expected_investment = round(buyin_amount + (buyin_amount * rebuy_count), 2)
		expected_bounty_earnings = round(bounty_amount * Decimal(eliminations_count), 2)
		expected_placement_earnings = placement_earnings
		expected_gross_earnings = round(expected_placement_earnings + expected_bounty_earnings, 2)
		rebuys = TournamentRebuy.objects.get_rebuys_for_player(
			player = result.player
		)
		eliminations = TournamentElimination.objects.get_eliminations_by_eliminator(
			player_id = result.player.id
		)
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
			player_id = result.player.id
		)
		split_eliminations_count = 0.00
		for split_elimination in split_eliminations:
			eliminators = split_elimination.eliminators.all()
			split_eliminations_count += round(1.00 / len(eliminators), 2)
		self.assertEqual(result.investment, expected_investment)
		self.assertEqual(build_placement_string(result.placement), placement_string)
		self.assertEqual(result.placement_earnings, expected_placement_earnings)
		self.assertEqual(len(rebuys), rebuy_count)
		self.assertEqual(result.bounty_earnings, expected_bounty_earnings)
		self.assertEqual(result.gross_earnings, expected_gross_earnings)
		self.assertEqual(round(len(eliminations) + split_eliminations_count, 2), eliminations_count)
		self.assertEqual(result.net_earnings, round(expected_gross_earnings - Decimal(expected_investment), 2))
		self.assertEqual(result.is_backfill, is_backfill)

	def setUp(self):
		# Build some users for the tests
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)

	"""
	Verify cannot use a TournamentStructure that you didn't create.
	"""
	def test_cannot_use_structure_you_dont_own(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Try to create a tournment where the admin is dog using the structure made by cat
		dog = User.objects.get_by_username("dog")
		with self.assertRaisesMessage(ValidationError, "You cannot use a Tournament Structure that you don't own."):
			self.build_tournament(
				admin = dog,
				title = "Doge Tournament",
				structure = structure
			)

	"""
	Verify creating a tournment
	"""
	def test_create_tournament(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		tournaments = Tournament.objects.get_by_user(user = cat)
		self.assertEqual(len(tournaments), 1)
		self.assertEqual(tournaments[0].admin, cat)
		self.assertEqual(tournaments[0].title, "Cat Tournament")
		self.assertEqual(tournaments[0].tournament_structure.buyin_amount, 100)
		self.assertEqual(tournaments[0].tournament_structure.bounty_amount, 10)
		self.assertEqual(tournaments[0].tournament_structure.payout_percentages, [100])
		self.assertEqual(tournaments[0].tournament_structure.allow_rebuys, False)

		# Verify the admin is added as a TournamentPlayer
		players = TournamentPlayer.objects.get_tournament_players(tournaments[0].id)
		self.assertEqual(len(players), 1)
		self.assertEqual(players[0].user, cat)

		# Create a second Tournament with a different structure
		structure2 = self.build_structure(
			user = cat,
			buyin_amount = 199,
			bounty_amount = None,
			payout_percentages = [60, 20, 15, 5],
			allow_rebuys = True
		)
		self.build_tournament(
			title = "Cat Tournament 2",
			admin = cat,
			structure = structure2
		)

		touraments2 = Tournament.objects.get_by_user(user = cat)


		self.assertEqual(len(touraments2), 2)
		# Verify Cat Tournament 2
		self.assertEqual(touraments2[0].admin, cat)
		self.assertEqual(touraments2[0].title, "Cat Tournament 2")
		self.assertEqual(touraments2[0].tournament_structure.buyin_amount, 199)
		self.assertEqual(touraments2[0].tournament_structure.bounty_amount, None)
		self.assertEqual(touraments2[0].tournament_structure.payout_percentages, [60, 20, 15, 5])
		self.assertEqual(touraments2[0].tournament_structure.allow_rebuys, True)

		# Verify Cat Tournament 1 is the same as previous assertions
		self.assertEqual(touraments2[1].admin, cat)
		self.assertEqual(touraments2[1].title, "Cat Tournament")
		self.assertEqual(touraments2[1].tournament_structure.buyin_amount, 100)
		self.assertEqual(touraments2[1].tournament_structure.bounty_amount, 10)
		self.assertEqual(touraments2[1].tournament_structure.payout_percentages, [100])
		self.assertEqual(touraments2[1].tournament_structure.allow_rebuys, False)

		# Verify the admin is added as a TournamentPlayer
		players2 = TournamentPlayer.objects.get_tournament_players(touraments2[1].id)
		self.assertEqual(len(players2), 1)
		self.assertEqual(players2[0].user, cat)


	"""
	Verify get_joined_tournaments
	"""
	def test_get_joined_tournaments(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament owned by 'cat'
		cat_tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Build a structure made by dog
		dog = User.objects.get_by_username("dog")
		structure = self.build_structure(
			user = dog,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament owned by 'dog'
		dog_tournament = self.build_tournament(
			title = "Dog Tournament",
			admin = dog,
			structure = structure
		)

		# add dog to cat's tournament
		TournamentPlayer.objects.create_player_for_tournament(
			user_id = dog.id,
			tournament_id = cat_tournament.id
		)

		# Verify dog's joined tournaments list is NOT empty
		dogs_joined_tournaments = Tournament.objects.get_joined_tournaments(
			user_id = dog.id
		)
		self.assertEqual(len(dogs_joined_tournaments), 1)

		# Verify cat's joined tournaments list is empty since they are the admin of the only tournament they're part of.
		cats_joined_tournaments = Tournament.objects.get_joined_tournaments(
			user_id = cat.id
		)
		self.assertEqual(len(cats_joined_tournaments), 0)

	"""
	Verify is_completable without rebuys enabled.
	"""
	def test_is_completable_without_rebuys(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# is_completable will raise at this point b/c no one is eliminated
		with self.assertRaisesMessage(ValidationError, "Every player must be eliminated before completing a Tournament"):
			is_completable = Tournament.objects.is_completable(
				tournament_id = tournament.id
			)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Eliminate every player except cat and dog.
		for player in players:
			if player != cat_player and player.user.username != "dog": 
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)

		# is_completable will raise at this point b/c 2 players remain
		with self.assertRaisesMessage(ValidationError, "Every player must be eliminated before completing a Tournament"):
			is_completable = Tournament.objects.is_completable(
				tournament_id = tournament.id
			)

		# Eliminate the last player ("dog")
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		for player in players:
			if player.user.username == "dog":
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)

		# is_completable will succeed now
		is_completable = Tournament.objects.is_completable(
				tournament_id = tournament.id
			)
		self.assertEqual(is_completable, True)


	"""
	Verify cannot complete a Tournament if not the admin.
	Using @mock to verify 'email_tournament_results' is called when a Tournament is successfully completed.
	"""
	@mock.patch.object(Tournament.objects, "email_tournament_results")
	def test_cannot_complete_tournament_if_not_admin(self, mock):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Eliminate all the players except 1 (cat)
		eliminate_all_players_except(
			players = players,
			except_player = cat_player,
			tournament = tournament
		)

		# Loop through players and try to complete the Tournament. Only the admin will succeed
		for player in players:
			if player.user.username == "cat":
				tournament = Tournament.objects.complete_tournament(
					user = player.user,
					tournament_id = tournament.id
				)
				self.assertTrue(tournament.completed_at != None)

				# Verify the 'email_tournament_results' function is called when a Tournament is successfully completed.
				mock.assert_called()
			else:
				with self.assertRaisesMessage(ValidationError, "You cannot update a Tournament if you're not the admin."):
					Tournament.objects.complete_tournament(
						user = player.user,
						tournament_id = tournament.id
					)

	"""
	Verify can't complete a Tournament that has not been started.
	"""
	def test_cannot_complete_tournament_if_not_started(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)
		with self.assertRaisesMessage(ValidationError, "You can't complete a Tournament that has not been started."):
			eliminate_players_and_complete_tournament(admin = cat, tournament = tournament)


	"""
	Verify can't complete a Tournament that is already completed
	"""
	def test_cannot_complete_tournament_if_already_completed(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)
		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)
		# Attempt to complete again
		with self.assertRaisesMessage(ValidationError, "This tournament is already completed."):
			Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

	"""
	Verify undo completion cannot be executed if not admin
	"""
	def test_cannot_undo_completion_if_not_admin(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		# Attempt to undo completion if not admin
		for user in User.objects.all():
			if user.username != "cat":
				with self.assertRaisesMessage(ValidationError, "You cannot update a Tournament if you're not the admin."):
					Tournament.objects.undo_complete_tournament(
						user = user,
						tournament_id = tournament.id
				)

	"""
	Verify undo completion if Tournament is not complete.
	"""
	def test_cannot_undo_completion_if_not_admin(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Attempt to undo completion when it has never been completed
		with self.assertRaisesMessage(ValidationError, "The tournament is not completed. Nothing to undo."):
			Tournament.objects.undo_complete_tournament(
					user = cat,
					tournament_id = tournament.id
				)	


	"""
	Verify undo completion deletes eliminations, split eliminations and rebuys
	"""
	def test_undo_completion_deletes_eliminations_split_eliminations_rebuys_and_results(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Eliminate all the players except 1 (cat)
		eliminate_all_players_except(
			players = players,
			except_player = cat_player,
			tournament = tournament
		)

		# Rebuy on all players (except admin)
		for player in players:
			if player != cat_player:
				rebuy_for_test(
					tournament_id = tournament.id,
					player_id = player.id
				)

		dog = User.objects.get_by_username("dog")
		dog_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = dog.id
		)

		bird = User.objects.get_by_username("bird")
		bird_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = bird.id
		)		

		# Eliminate dog with a split elimination between cat and bird.
		split_eliminate_player(
			tournament_id = tournament.id,
			eliminator_ids = [cat_player.id, bird_player.id],
			eliminatee_id = dog_player.id
		)

		# Eliminate everyone else (Except admin)
		for player in players:
			if player.user.username != "cat" and player.user.username != "dog":
				eliminate_player(
					tournament_id = tournament.id,
					eliminator_id = cat_player.id,
					eliminatee_id = player.id
				)
		
		# Verify every player has 2 eliminations (Except cat and dog). Dog will have 1 elimination and 1 split elimination.
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		elim_dict = {}
		for elimination in eliminations:
			if elimination.eliminatee.id in elim_dict.keys():
				elim_dict[elimination.eliminatee.id] = elim_dict[elimination.eliminatee.id] + 1
			else:
				elim_dict[elimination.eliminatee.id] = 1
		self.assertFalse(cat_player.id in elim_dict)
		for key in elim_dict.keys():
			if key != dog_player.id:
				self.assertEqual(elim_dict[key], 2)
			elif key == dog_player.id:
				# a single TournamentElimination for dog.
				self.assertEqual(elim_dict[key], 1)

		# Then verify dog has a TournamentSplitElimination
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(tournament.id)
		self.assertEqual(len(split_eliminations), 1)
		self.assertEqual(split_eliminations[0].eliminatee, dog_player)

		# Verify every player has 1 rebuy (except cat)
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		for player in players:
			num_rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			if player != cat_player:
				self.assertEqual(len(num_rebuys), 1)
			else:
				self.assertEqual(len(num_rebuys), 0)

		# verify there are no tournament results
		tournament_results = TournamentPlayerResult.objects.get_results_for_tournament(tournament.id)
		self.assertTrue(len(tournament_results) == 0)

		# Complete tournament
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		# verify the tournament results were generated.
		tournament_results = TournamentPlayerResult.objects.get_results_for_tournament(tournament.id)
		self.assertTrue(len(tournament_results) != 0)

		# Undo completion
		Tournament.objects.undo_complete_tournament(
			user = cat,
			tournament_id = tournament.id
		)

		# verify there are no tournament results
		tournament_results = TournamentPlayerResult.objects.get_results_for_tournament(tournament.id)
		self.assertTrue(len(tournament_results) == 0)

		# Verify the eliminations are deleted
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		self.assertEqual(len(eliminations), 0)

		# Verify the split_eliminations are deleted
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		self.assertEqual(len(split_eliminations), 0)

		# Verify rebuys are deleted
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		for player in players:
			num_rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			self.assertEqual(len(num_rebuys), 0)

		# Verify completed_at is None
		tournament = Tournament.objects.get_by_id(tournament.id)
		self.assertEqual(tournament.completed_at, None)

	"""
	Verify cannot start a Tournament unless you're the admin.
	"""
	def test_cannot_start_tournament_if_not_admin(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Cannot start if not admin
		for user in User.objects.all():
			if user.username != "cat":
				with self.assertRaisesMessage(ValidationError, "You cannot update a Tournament if you're not the admin."):
					Tournament.objects.start_tournament(
							user = user,
							tournament_id = tournament.id
						)

	"""
	Verify cannot start a Tournament that's been completed
	"""
	def test_cannot_start_tournament_if_completed(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		# Cannot start if completed
		with self.assertRaisesMessage(ValidationError, "You can't start a Tournament that has already been completed."):
			Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)


	"""
	Verify start_tournament
	"""
	def test_start_tournament(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Verify the state is ACTIVE
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)
		tournament = Tournament.objects.get_by_id(tournament.id)
		self.assertEqual(tournament.get_state(), TournamentState.ACTIVE)

	"""
	Verify cannot calculate tournament value until tournament is complete
	"""
	def test_cannot_calculate_tournament_value_until_complete(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		with self.assertRaisesMessage(ValidationError, "Tournament value cannot be calculated until a Tournament is complete."):
			Tournament.objects.calculate_tournament_value(tournament_id = tournament.id, num_rebuys=0)


	"""
	Verify tournament value calculation
	"""
	def test_tournament_value(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		buyin_amount = 115.20
		structure = self.build_structure(
			user = cat,
			buyin_amount = buyin_amount,
			bounty_amount = 11.7,
			payout_percentages = [100],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)
		# Eliminate all the players except 1 (cat)
		eliminate_all_players_except(
			players = players,
			except_player = cat_player,
			tournament = tournament
		)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		# Verify the value
		value = Tournament.objects.calculate_tournament_value(tournament_id = tournament.id, num_rebuys=0)
		expected_value = round(Decimal(1036.80), 2)
		self.assertEqual(value, expected_value)

		# undo_complete to add some rebuys. This will reset all eliminations so we need to add again.
		Tournament.objects.undo_complete_tournament(user = cat, tournament_id = tournament.id)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Eliminate all the players except 1 (cat)
		eliminate_all_players_except(
			players = players,
			except_player= cat_player,
			tournament = tournament
		)

		# Rebuy on all players (except admin)
		for player in players:
			if player.user.username != "cat":
				rebuy_for_test(
					tournament_id = tournament.id,
					player_id = player.id
				)
		# Eliminate everyone again (Except admin)
		eliminate_all_players_except(
			players = players,
			except_player = cat_player,
			tournament = tournament
		)

		# Complete again
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		# Verify the value
		value = Tournament.objects.calculate_tournament_value(tournament_id = tournament.id, num_rebuys = 8)
		expected_value = round(Decimal(1958.40), 2)
		self.assertEqual(value, expected_value)

	"""
	Verify completing a tournament for backfill is successful.
	Bounties: Enabled
	Rebuys: Enabled
	"""
	def test_complete_tournament_for_backfill_bounty_enabled_rebuy_enabled(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		buyin_amount = 115.20
		structure = self.build_structure(
			user = cat,
			buyin_amount = buyin_amount,
			bounty_amount = 11.7,
			payout_percentages = [50, 30, 20],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)
		p_names = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		p_all = TournamentPlayer.objects.get_tournament_players(tournament_id=tournament.id)
		p_by_name = {pl.user.username: pl for pl in p_all}
		p = {i+1: p_by_name[name] for i, name in enumerate(p_names)}

		# --- Placements ----
		player_tournament_placements = [
			# First
			PlayerTournamentPlacement(
				player_id = p[1].id,
				placement = 0,
			),

			# Second
			PlayerTournamentPlacement(
				player_id = p[9].id,
				placement = 1,
			),

			# Third
			PlayerTournamentPlacement(
				player_id = p[6].id,
				placement = 2,
			),
		]

		# --- Eliminations ---
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("id")
		elim_dict = {
			# cat eliminates player3, player4, player5
			p[1].id: [players[2], players[3], players[4]],

			# player2 eliminates player9 (twice), player1, player4, player6
			p[2].id: [players[8], players[0], players[3], players[8], players[5]],

			# player5 eliminates player7, player6, player2
			p[5].id: [players[6], players[5], players[1]],

			# player7 eliminates player8
			p[7].id: [players[7]],

			# player8 eliminates player1
			p[8].id: [players[0]],

			# player9 eliminates player7
			p[9].id: [players[6]],
		}

		# --- Split Eliminations ----
		split_eliminations = []
		split_elim1 = {
			'eliminatee': players[1],
			'eliminators': [players[2], players[3]]
		}
		split_elim2 = {
			'eliminatee': players[4],
			'eliminators': [players[7], players[1], players[8]]
		}
		split_eliminations.append(split_elim1)
		split_eliminations.append(split_elim2)

		# Execute the backfill
		Tournament.objects.complete_tournament_for_backfill(
			user = tournament.admin,
			tournament_id = tournament.id,
			player_tournament_placements = player_tournament_placements,
			elim_dict = elim_dict,
			split_eliminations = split_eliminations
		)

		results = TournamentPlayerResult.objects.get_results_for_tournament(
			tournament_id = tournament.id
		)

		# 1958.40
		# bounties 198.9
		# minus bounties 1759.50
		buyin_amount = Decimal(115.20)
		bounty_amount = Decimal(11.70)
		for result in results:
			self.assertEqual(result.is_backfill, True)
			if result.player.user.username == "racoon":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "2nd",
					placement_earnings = Decimal("527.85"),
					rebuy_count = 1,
					eliminations_count = 1.33,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "insect":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 1.33,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "gator":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 1,
					eliminations_count = 1,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "elephant":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "3rd",
					placement_earnings = Decimal("351.9"),
					rebuy_count = 1,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "donkey":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 1,
					eliminations_count = 3,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "bird":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 1,
					eliminations_count = 0.5,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "monkey":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 0.5,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "dog":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 1,
					eliminations_count = 5.83,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "cat":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "1st",
					placement_earnings = Decimal("879.75"),
					rebuy_count = 2,
					eliminations_count = 3,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)

	"""
	Verify completing a tournament for backfill is successful.
	Bounties: Disabled
	Rebuys: Enabled
	"""
	def test_complete_tournament_for_backfill_success_bounty_disabled_rebuy_enabled(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		buyin_amount = 115.20
		structure = self.build_structure(
			user = cat,
			buyin_amount = buyin_amount,
			bounty_amount = None,
			payout_percentages = [50, 30, 20],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)
		p_names = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		p_all = TournamentPlayer.objects.get_tournament_players(tournament_id=tournament.id)
		p_by_name = {pl.user.username: pl for pl in p_all}
		p = {i+1: p_by_name[name] for i, name in enumerate(p_names)}

		# --- Placements ----
		player_tournament_placements = [
			# First
			PlayerTournamentPlacement(
				player_id = p[1].id,
				placement = 0,
			),

			# Second
			PlayerTournamentPlacement(
				player_id = p[9].id,
				placement = 1,
			),

			# Third
			PlayerTournamentPlacement(
				player_id = p[6].id,
				placement = 2,
			),
		]

		# --- Eliminations ---
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("id")
		elim_dict = {
			# cat eliminates player3, player4, player5
			p[1].id: [players[2], players[3], players[4]],

			# player2 eliminates player9 (twice), player1, player4, player6
			p[2].id: [players[8], players[0], players[3], players[8], players[5]],

			# player5 eliminates player7, player6, player2
			p[5].id: [players[6], players[5], players[1]],

			# player7 eliminates player8
			p[7].id: [players[7]],

			# player8 eliminates player1
			p[8].id: [players[0]],

			# player9 eliminates player7
			p[9].id: [players[6]],
		}

		# Execute the backfill
		Tournament.objects.complete_tournament_for_backfill(
			user = tournament.admin,
			tournament_id = tournament.id,
			player_tournament_placements = player_tournament_placements,
			elim_dict = elim_dict,
			split_eliminations = [],
		)

		results = TournamentPlayerResult.objects.get_results_for_tournament(
			tournament_id = tournament.id
		)

		buyin_amount = Decimal(115.20)
		bounty_amount = None
		# 1728
		for result in results:
			self.assertEqual(result.is_backfill, True)
			if result.player.user.username == "racoon":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "2nd",
					placement_earnings = Decimal("518.40"),
					rebuy_count = 1,
					eliminations_count = 1,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "insect":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 1,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "gator":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 1,
					eliminations_count = 1,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "elephant":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "3rd",
					placement_earnings = Decimal("345.60"),
					rebuy_count = 1,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "donkey":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 3,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "bird":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 1,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "monkey":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "dog":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 5,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "cat":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "1st",
					placement_earnings = Decimal("864"),
					rebuy_count = 2,
					eliminations_count = 3,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)

	"""
	Verify completing a tournament for backfill is successful.
	Bounties: Disabled
	Rebuys: Disabled
	"""
	def test_complete_tournament_for_backfill_success_bounty_disabled_rebuy_disabled(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		buyin_amount = 115.20
		structure = self.build_structure(
			user = cat,
			buyin_amount = buyin_amount,
			bounty_amount = None,
			payout_percentages = [50, 30, 20],
			allow_rebuys = False
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)
		p_names = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		p_all = TournamentPlayer.objects.get_tournament_players(tournament_id=tournament.id)
		p_by_name = {pl.user.username: pl for pl in p_all}
		p = {i+1: p_by_name[name] for i, name in enumerate(p_names)}

		# --- Placements ----
		player_tournament_placements = [
			# First
			PlayerTournamentPlacement(
				player_id = p[1].id,
				placement = 0,
			),

			# Second
			PlayerTournamentPlacement(
				player_id = p[9].id,
				placement = 1,
			),

			# Third
			PlayerTournamentPlacement(
				player_id = p[6].id,
				placement = 2,
			),
		]

		# --- Eliminations ---
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("id")
		elim_dict = {
			p[1].id: [players[2], players[4]],
			p[2].id: [players[8], players[3],  players[5]],
			p[5].id: [],
			p[7].id: [players[7], players[1]],
			p[8].id: [],
			p[9].id: [players[6]],
		}

		# Execute the backfill
		Tournament.objects.complete_tournament_for_backfill(
			user = tournament.admin,
			tournament_id = tournament.id,
			player_tournament_placements = player_tournament_placements,
			elim_dict = elim_dict,
			split_eliminations = [],
		)

		results = TournamentPlayerResult.objects.get_results_for_tournament(
			tournament_id = tournament.id
		)

		buyin_amount = Decimal(115.20)
		bounty_amount = None
		# 1036.80
		for result in results:
			self.assertEqual(result.is_backfill, True)
			if result.player.user.username == "racoon":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "2nd",
					placement_earnings = Decimal("311.04"),
					rebuy_count = 0,
					eliminations_count = 1,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "insect":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "gator":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 2,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "elephant":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "3rd",
					placement_earnings = Decimal("207.36"),
					rebuy_count = 0,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "donkey":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "bird":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "monkey":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 0,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "dog":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "--",
					placement_earnings = Decimal("0.00"),
					rebuy_count = 0,
					eliminations_count = 3,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)
			elif result.player.user.username == "cat":
				self.verify_result(
					result = result,
					is_backfill = True,
					placement_string = "1st",
					placement_earnings = Decimal("518.40"),
					rebuy_count = 0,
					eliminations_count = 2,
					buyin_amount = buyin_amount,
					bounty_amount = bounty_amount
				)

	"""
	Verify if placements aren't added correctly this fails.
	"""
	def test_complete_tournament_error_placements_not_added(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		buyin_amount = 115.20
		structure = self.build_structure(
			user = cat,
			buyin_amount = buyin_amount,
			bounty_amount = 11.7,
			payout_percentages = [50, 30, 20],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)
		p_names = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		p_all = TournamentPlayer.objects.get_tournament_players(tournament_id=tournament.id)
		p_by_name = {pl.user.username: pl for pl in p_all}
		p = {i+1: p_by_name[name] for i, name in enumerate(p_names)}

		# --- Placements ----
		player_tournament_placements = [
			# First
			PlayerTournamentPlacement(
				player_id = p[1].id,
				placement = 0,
			),

			# Second
			PlayerTournamentPlacement(
				player_id = p[9].id,
				placement = 1,
			),

			# Missing third placement!
		]

		# --- Eliminations ---
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("id")
		elim_dict = {
			# cat eliminates player3, player4, player5
			p[1].id: [players[2], players[3], players[4]],

			# player2 eliminates player9 (twice), player1, player4, player6
			p[2].id: [players[8], players[0], players[3], players[8], players[5]],

			# player5 eliminates player7, player6, player2
			p[5].id: [players[6], players[5], players[1]],

			# player7 eliminates player8
			p[7].id: [players[7]],

			# player8 eliminates player1
			p[8].id: [players[0]],

			# player9 eliminates player7
			p[9].id: [players[6]],
		}

		with self.assertRaisesMessage(ValidationError, "The tournament structure requires you select 3 players who placed in the tournament."):
			Tournament.objects.complete_tournament_for_backfill(
				user = tournament.admin,
				tournament_id = tournament.id,
				player_tournament_placements = player_tournament_placements,
				elim_dict = elim_dict,
				split_eliminations = [],
			)
		self.verify_tournament_reset(tournament.id)

	"""
	Verify if the same player is specified for multiple placements, we fail.
	"""
	def test_complete_tournament_error_same_player_multiple_placements(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		buyin_amount = 115.20
		structure = self.build_structure(
			user = cat,
			buyin_amount = buyin_amount,
			bounty_amount = 11.7,
			payout_percentages = [50, 30, 20],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)
		p_names = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		p_all = TournamentPlayer.objects.get_tournament_players(tournament_id=tournament.id)
		p_by_name = {pl.user.username: pl for pl in p_all}
		p = {i+1: p_by_name[name] for i, name in enumerate(p_names)}

		# --- Placements ----
		player_tournament_placements = [
			# First
			PlayerTournamentPlacement(
				player_id = p[1].id,
				placement = 0,
			),

			# Second
			PlayerTournamentPlacement(
				player_id = p[9].id,
				placement = 1,
			),

			# Third (SAME PLAYER AS second)
			PlayerTournamentPlacement(
				player_id = p[9].id,
				placement = 2,
			),
		]

		# --- Eliminations ---
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("id")
		elim_dict = {
			# cat eliminates player3, player4, player5
			p[1].id: [players[2], players[3], players[4]],

			# player2 eliminates player9 (twice), player1, player4, player6
			p[2].id: [players[8], players[0], players[3], players[8], players[5]],

			# player5 eliminates player7, player6, player2
			p[5].id: [players[6], players[5], players[1]],

			# player7 eliminates player8
			p[7].id: [players[7]],

			# player8 eliminates player1
			p[8].id: [players[0]],

			# player9 eliminates player7
			p[9].id: [players[6]],
		}

		with self.assertRaisesMessage(ValidationError, "You can't specify the same player for multiple placements."):
			Tournament.objects.complete_tournament_for_backfill(
				user = tournament.admin,
				tournament_id = tournament.id,
				player_tournament_placements = player_tournament_placements,
				elim_dict = elim_dict,
				split_eliminations = [],
			)
		self.verify_tournament_reset(tournament.id)

	"""
	Verify if a player did not win, they were eliminated at least once.
	"""
	def test_complete_tournament_error_if_player_did_not_win_must_be_eliminated(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		buyin_amount = 115.20
		structure = self.build_structure(
			user = cat,
			buyin_amount = buyin_amount,
			bounty_amount = 11.7,
			payout_percentages = [50, 30, 20],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)
		p_names = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		p_all = TournamentPlayer.objects.get_tournament_players(tournament_id=tournament.id)
		p_by_name = {pl.user.username: pl for pl in p_all}
		p = {i+1: p_by_name[name] for i, name in enumerate(p_names)}

		# --- Placements ----
		player_tournament_placements = [
			# First
			PlayerTournamentPlacement(
				player_id = p[1].id,
				placement = 0,
			),

			# Second
			PlayerTournamentPlacement(
				player_id = p[9].id,
				placement = 1,
			),

			# Third
			PlayerTournamentPlacement(
				player_id = p[3].id,
				placement = 2,
			),
		]

		# --- Eliminations ---
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("id")
		elim_dict = {
			# cat eliminates player3, player4, player5
			p[1].id: [players[2], players[3], players[4]],

			# player2 eliminates player9 (twice), player1, player4, player6
			p[2].id: [players[8], players[0], players[3], players[8], players[5]],

			# player5 eliminates player7, player6, player2
			p[5].id: [players[6], players[5], players[1]],

			p[7].id: [],

			# player8 eliminates player1
			p[8].id: [players[0]],

			# player9 eliminates player7
			p[9].id: [players[6]],
		}

		# Note: players[7] was never eliminated and they did not win. So error will throw.
		with self.assertRaisesMessage(ValidationError, f"{players[7].user.username} did not win, they must have been eliminated at least once."):
			Tournament.objects.complete_tournament_for_backfill(
				user = tournament.admin,
				tournament_id = tournament.id,
				player_tournament_placements = player_tournament_placements,
				elim_dict = elim_dict,
				split_eliminations = [],
			)
		self.verify_tournament_reset(tournament.id)

	"""
	Verify undo activating a tournament deletes eliminations and rebuys.
	"""
	def test_undo_activation_deletes_eliminations_rebuys(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")
		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = 10,
			payout_percentages = [100],
			allow_rebuys = True
		)

		# Create tournament
		tournament = self.build_tournament(
			title = "Cat Tournament",
			admin = cat,
			structure = structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		cat_player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament.id,
			user_id = cat.id
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Eliminate all the players except 1 (cat)
		eliminate_all_players_except(
			players = players,
			except_player = cat_player,
			tournament = tournament
		)

		# Rebuy on all players (except admin)
		for player in players:
			if player != cat_player:
				rebuy_for_test(
					tournament_id = tournament.id,
					player_id = player.id
				)

		# Eliminate everyone again (Except admin)
		eliminate_all_players_except(
			players = players,
			except_player = cat_player,
			tournament = tournament
		)

		# Verify every player has 2 eliminations (Except cat)
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		elim_dict = {}
		for elimination in eliminations:
			if elimination.eliminatee.id in elim_dict.keys():
				elim_dict[elimination.eliminatee.id] = elim_dict[elimination.eliminatee.id] + 1
			else:
				elim_dict[elimination.eliminatee.id] = 1
		self.assertFalse(cat_player.id in elim_dict)
		for key in elim_dict.keys():
			self.assertEqual(elim_dict[key], 2)

		# Verify every player has 1 rebuy (except cat)
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		for player in players:
			num_rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			if player != cat_player:
				self.assertEqual(len(num_rebuys), 1)
			else:
				self.assertEqual(len(num_rebuys), 0)

		# verify there are no tournament results
		tournament_results = TournamentPlayerResult.objects.get_results_for_tournament(tournament.id)
		self.assertTrue(len(tournament_results) == 0)

		# De-activate the tournament
		Tournament.objects.undo_start_tournament(user = cat, tournament_id = tournament.id)

		# verify there are no tournament results
		tournament_results = TournamentPlayerResult.objects.get_results_for_tournament(tournament.id)
		self.assertTrue(len(tournament_results) == 0)

		# Verify the eliminations are deleted
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		self.assertEqual(len(eliminations), 0)

		# Verify rebuys are deleted
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		for player in players:
			num_rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			self.assertEqual(len(num_rebuys), 0)

		# Verify started_at is None
		tournament = Tournament.objects.get_by_id(tournament.id)
		self.assertEqual(tournament.started_at, None)


class TournamentSplitEliminationsTestCase(TestCase):

	def setUp(self):
		# Build some users for the tests
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)

		# Build a Structure with no bounties and no rebuys
		structure = build_structure(
			admin = users[0], # Cat is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = False
		)

		self.tournament = build_tournament(structure)

		# Add the users to the Tournament as TournamentPlayer's
		add_players_to_tournament(
			# Remove the admin since they are already a player automatically
			users = [value for value in users if value.username != "cat"],
			tournament = self.tournament
		)


	"""
	Test the split eliminations
	"""
	def test_split_eliminations(self):
		tournament = self.tournament
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		# -- Create eliminations --
		# player0 and player4 eliminate player1
		split_eliminate_player(
			tournament_id = tournament_id,
			eliminator_ids = [players[0].id, players[4].id],
			eliminatee_id = players[1].id
		)

		# player2, player6 and player8 eliminate player3
		split_eliminate_player(
			tournament_id = tournament_id,
			eliminator_ids = [players[2].id, players[6].id, players[8].id],
			eliminatee_id = players[3].id
		)

		# player4 eliminates player5
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[4].id,
			eliminatee_id = players[5].id
		)

		# player6 eliminates player7
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[6].id,
			eliminatee_id = players[7].id
		)

		# player0 eliminates player8
		eliminate_player(
			tournament_id = tournament_id,
			eliminator_id = players[0].id,
			eliminatee_id = players[8].id
		)

		# At this point everyone is eliminated except player0

		# -- Verify eliminations --

		# Verify the split eliminations by player0 and player4
		split_eliminations0 = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
			player_id = players[0].id
		)
		self.assertEqual(split_eliminations0[0].eliminatee.tournament, tournament)
		self.assertEqual(len(split_eliminations0), 1)

		# verify player0 and player4 split eliminated player1
		split_eliminators0 = split_eliminations0[0].eliminators.all()
		for eliminator in split_eliminators0:
			self.assertEqual(eliminator.tournament, tournament)
		self.assertEqual(len(split_eliminators0), 2)
		self.assertTrue(players[0] in split_eliminators0)
		self.assertTrue(players[4] in split_eliminators0)
		self.assertEqual(split_eliminations0[0].eliminatee, players[1])

		# Verify the split eliminations by player2, player6 and player8
		split_eliminations1 = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
					player_id = players[2].id
		)
		# verify player2, player6 and player8 split eliminated player3
		split_eliminators1 = split_eliminations1[0].eliminators.all()
		for eliminator in split_eliminators1:
			self.assertEqual(eliminator.tournament, tournament)
		self.assertEqual(len(split_eliminators1), 3)
		self.assertTrue(players[2] in split_eliminators1)
		self.assertTrue(players[6] in split_eliminators1)
		self.assertTrue(players[8] in split_eliminators1)
		self.assertEqual(split_eliminations1[0].eliminatee, players[3])


	"""
	Test you cannot do a split elimination when specifying only one eliminator.
	"""
	def test_split_eliminations(self):
		tournament = self.tournament
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		with self.assertRaisesMessage(ValidationError, "You must choose more than one eliminator for a split elimination."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[0].id],
				eliminatee_id = players[1].id
			)

	"""
	Cannot eliminate a player who is not part of the tournament and cannot perform an elimination if the eliminator
	is not part of the tournment.
	"""
	def test_cannot_split_eliminate_user_who_has_not_joined_tournament(self):
		tournament = self.tournament
		tournament_id = tournament.id
		new_user = create_users(['horse'])[0]

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		with self.assertRaisesMessage(ValidationError, "Eliminatee is not part of that Tournament."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[0].id, players[1].id],
				eliminatee_id = 9999999 # This will fail b/c its not a TournamentPlayer
			)

		with self.assertRaisesMessage(ValidationError, "Eliminator is not part of that Tournament."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [9999999, players[2].id], # This will fail b/c its not a TournamentPlayer
				eliminatee_id = players[0].id
			)

	"""
	Verify you cannot split eliminate a player that is already eliminated
	"""
	def test_cannot_split_eliminate_player_who_is_already_eliminated(self):
		tournament = self.tournament
		tournament_id = tournament.id

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("user__username")

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		# split eliminate player0
		split_eliminate_player(
			tournament_id = tournament_id,
			eliminator_ids = [players[1].id, players[2].id],
			eliminatee_id = players[0].id
		)
		# Try to eliminate again. This will fail because they have already been eliminated and have no more rebuys.
		with self.assertRaisesMessage(ValidationError, f"{players[0].user.username} has already been eliminated and has no more re-buys."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[1].id, players[3].id],
				eliminatee_id = players[0].id
			)

	"""
	Verify you cannot specifiy the same user as an eliminator more than once during a split elimination.
	"""
	def test_cannot_specify_same_eliminator_multiple_times_for_split_elimination(self):
		tournament = self.tournament
		tournament_id = tournament.id

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("user__username")

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		with self.assertRaisesMessage(ValidationError, f"You specified {players[1].user.username} more than once as an eliminator."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[1].id, players[1].id],
				eliminatee_id = players[0].id
			)

	"""
	Verify you cannot split eliminate a player when the tournament is not started.
	"""
	def test_cannot_split_eliminate_player_when_tournament_not_active(self):
		tournament = self.tournament
		tournament_id = tournament.id

		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).order_by("user__username")

		with self.assertRaisesMessage(ValidationError, "You can only eliminate players if the Tournament is Active."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[1].id, players[2].id],
				eliminatee_id = players[0].id
			)

	"""
	Test cannot split eliminate the final player. The Tournament should be completed.
	"""
	def test_cannot_split_eliminate_last_player(self):
		tournament = self.tournament
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		# -- Create eliminations --

		# Eliminate all players except player0
		eliminate_all_players_except(
			players = players,
			except_player = players[0],
			tournament = tournament
		)

		# At this point everyone is eliminated except player0
		# Try to eliminate them.
		with self.assertRaisesMessage(ValidationError, "You can't eliminate any more players. Complete the Tournament."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[8].id, players[7].id],
				eliminatee_id = players[0].id
			)

	"""
	Test cannot split eliminate themself.
	"""
	def test_cannot_split_eliminate_last_player(self):
		tournament = self.tournament
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		with self.assertRaisesMessage(ValidationError, f"{players[0].user.username} can't eliminate themselves!"):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[0].id, players[7].id],
				eliminatee_id = players[0].id
			)

	"""
	Test must choose at least 2 players to do a split elimination.
	"""
	def test_must_choose_at_least_2_players_to_perform_split_elimination(self):
		tournament = self.tournament
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)

		# Start
		Tournament.objects.start_tournament(user = tournament.admin, tournament_id = tournament.id)

		with self.assertRaisesMessage(ValidationError, "You must choose more than one eliminator for a split elimination."):
			split_eliminate_player(
				tournament_id = tournament_id,
				eliminator_ids = [players[7].id],
				eliminatee_id = players[0].id
			)


class TournamentPlayerResultTestCase(TestCase):
	
	"""
	bounty_amount: If None, this is not a bounty tournament.
	"""
	def build_structure(self, user, buyin_amount, bounty_amount, payout_percentages, allow_rebuys):
		structure = build_structure(
			admin = user,
			buyin_amount = buyin_amount,
			bounty_amount = bounty_amount,
			payout_percentages = payout_percentages,
			allow_rebuys = allow_rebuys
		)
		return structure
	
	def build_tournament(self, admin, title, structure):
		tournament = Tournament.objects.create_tournament(
			title = title,
			user = admin,
			tournament_structure = structure
		)
		return tournament

	def build_player_lookup(self, tournament_id):
		p_names = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		p_by_name = {pl.user.username: pl for pl in TournamentPlayer.objects.get_tournament_players(tournament_id)}
		return {i+1: p_by_name[name] for i, name in enumerate(p_names)}

	def build_placement_percentages(num_placements):
		if num_placements > 9:
			raise ValidationError("Can't build payout_percentages for tournament with more than 9 players.")
		percentages = []
		for x in range(1, num_placements):
			if x == 1:
				percentages.append(100)
			elif x == 2:
				percentages.append(60,40)
			elif x == 3:
				percentages.append(50,30,20)
		return percentages

	"""
	Builds a dictionary of PlayerPlacementData.
	Their placement is the key and PlayerPlacementData is the value.
	This makes it much easier to verify the placements and earnings.
	"""
	def build_placement_dict(self, is_backfill, tournament, eliminatee_order, eliminator_order, split_eliminatee_order=[], split_eliminator_order=[], debug=False):
		players = TournamentPlayer.objects.get_tournament_players(tournament.id)
		placement_dict = {}

		for player in players:
			# This will return a queryset but it should only be length of 1.
			result = TournamentPlayerResult.objects.get_results_for_user_by_tournament(
				user_id = player.user.id,
				tournament_id = tournament.id
			)[0]

			self.assertEqual(result.is_backfill, is_backfill)

			eliminations = TournamentElimination.objects.get_eliminations_by_eliminator(
				player_id = player.id
			)
			split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
				player_id = player.id
			)
			rebuys = TournamentRebuy.objects.get_rebuys_for_player(
				player = player
			)
			placement_data = PlayerPlacementData(
				user_id = result.player.user.id,
				username = result.player.user.username,
				placement = result.placement,
				placement_earnings = f"{result.placement_earnings}",
				investment = f"{result.investment}",
				eliminations = eliminations,
				split_eliminations = split_eliminations,
				bounty_earnings = f"{result.bounty_earnings}",
				rebuys = rebuys,
				gross_earnings = f"{result.gross_earnings}",
				net_earnings = f"{result.net_earnings}"
			)
			placement_dict[result.placement] = placement_data

		# For debugging
		if debug:
			for place in placement_dict.keys():
				print(f"{placement_dict[place].user_id} " +
					f"placed {placement_dict[place].placement} " +
					f"and earned {placement_dict[place].placement_earnings}.")

		return placement_dict

	def setUp(self):
		# Build some users for the tests
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)

	"""
	Verify cannot generate results before tournament is completed.
	"""
	def test_cannot_generate_results_before_tournament_complete(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = None,
			payout_percentages = [100],
			allow_rebuys = False
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		with self.assertRaisesMessage(ValidationError, "You cannot build Tournament results until the Tournament is complete."):
			results = TournamentPlayerResult.objects.build_results_for_tournament(tournament.id)

	"""
	Verify cannot calculate placement until tournament completed.
	"""
	def test_cannot_calculate_placement_until_tournament_completed(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = None,
			payout_percentages = [100],
			allow_rebuys = False
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		with self.assertRaisesMessage(ValidationError, "Cannot determine placement until tourment is completed."):
			results = TournamentPlayerResult.objects.determine_placement(user_id=cat.id, tournament_id=tournament.id)


	"""
	Verify placement is calculated correctly.
	No rebuys.
	"""
	def test_placement_calculation_no_rebuys_scenario1(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = None,
			payout_percentages = [100],
			allow_rebuys = False
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		p = self.build_player_lookup(tournament.id)

		# Eliminate in a specific order so we can verify. 6 is the winner here.
		# So expected placement order is: [6, 4, 8, 9, 1, 2, 3, 5, 7]
		eliminatee_order = [p[7].id, p[5].id, p[3].id, p[2].id, p[1].id, p[9].id, p[8].id, p[4].id]
		eliminator_order = [p[5].id, p[3].id, p[2].id, p[1].id, p[9].id, p[8].id, p[4].id, p[6].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order
		)

		self.assertEqual(len(placement_dict), 9) # There were only 9 players
		self.assertEqual(placement_dict[0].username, "elephant")
		self.assertEqual(placement_dict[1].username, "bird")
		self.assertEqual(placement_dict[2].username, "insect")
		self.assertEqual(placement_dict[3].username, "racoon")
		self.assertEqual(placement_dict[4].username, "cat")
		self.assertEqual(placement_dict[5].username, "dog")
		self.assertEqual(placement_dict[6].username, "monkey")
		self.assertEqual(placement_dict[7].username, "donkey")
		self.assertEqual(placement_dict[8].username, "gator")

	"""
	Verify placement is calculated correctly.
	No rebuys.
	"""
	def test_placement_calculation_no_rebuys_scenario2(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = None,
			payout_percentages = [100],
			allow_rebuys = False
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		p = self.build_player_lookup(tournament.id)

		# Eliminate in a specific order so we can verify. 9 is the winner here.
		# So expected placement order is: [9, 6, 8, 4, 5, 3, 2, 1, 7]
		eliminatee_order = [p[7].id, p[1].id, p[2].id, p[3].id, p[5].id, p[4].id, p[8].id, p[6].id]
		eliminator_order = [p[5].id, p[9].id, p[9].id, p[9].id, p[9].id, p[9].id, p[4].id, p[9].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order
		)

		self.assertEqual(len(placement_dict), 9) # There were only 9 players
		self.assertEqual(placement_dict[0].username, "racoon")
		self.assertEqual(placement_dict[1].username, "elephant")
		self.assertEqual(placement_dict[2].username, "insect")
		self.assertEqual(placement_dict[3].username, "bird")
		self.assertEqual(placement_dict[4].username, "donkey")
		self.assertEqual(placement_dict[5].username, "monkey")
		self.assertEqual(placement_dict[6].username, "dog")
		self.assertEqual(placement_dict[7].username, "cat")
		self.assertEqual(placement_dict[8].username, "gator")

	"""
	Verify placement is calculated correctly.
	With rebuys.
	"""
	def test_placement_calculation_with_rebuys_scenario1(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 100,
			bounty_amount = None,
			payout_percentages = [100],
			allow_rebuys = True
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		p = self.build_player_lookup(tournament.id)

		# Manunally add some rebuys
		# So 1 has two rebuys. 5, 7 and 8 have one rebuy each.
		rebuys = [p[1].id, p[5].id, p[7].id, p[8].id, p[1].id]
		for player_id in rebuys:
			rebuy_for_test(
				tournament_id = tournament.id,
				player_id = player_id
			)

		# Eliminate in a specific order so we can verify. 9 is the winner here.
		# So expected placement order is: [9, 7, 8, 1, 5, 6, 4, 3, 2]
		eliminatee_order = [p[1].id, p[1].id, p[5].id, p[2].id, p[3].id, p[4].id, p[6].id, p[5].id, p[7].id, p[8].id, p[1].id, p[8].id, p[7].id]
		eliminator_order = [p[2].id, p[5].id, p[9].id, p[7].id, p[8].id, p[1].id, p[1].id, p[9].id, p[8].id, p[1].id, p[9].id, p[7].id, p[9].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order,
			debug = False
		)

		self.assertEqual(len(placement_dict), 9) # There were only 9 players
		self.assertEqual(placement_dict[0].username, "racoon")
		self.assertEqual(placement_dict[1].username, "gator")
		self.assertEqual(placement_dict[2].username, "insect")
		self.assertEqual(placement_dict[3].username, "cat")
		self.assertEqual(placement_dict[4].username, "donkey")
		self.assertEqual(placement_dict[5].username, "elephant")
		self.assertEqual(placement_dict[6].username, "bird")
		self.assertEqual(placement_dict[7].username, "monkey")
		self.assertEqual(placement_dict[8].username, "dog")

	"""
	Verify placement earnings is calculated correctly.
	No rebuys, no bounties. (60, 30, 20) payout percentages.
	"""
	def test_placement_earnings_no_rebuys_no_bounties_60_30_20(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 115.12,
			bounty_amount = None,
			payout_percentages = [60, 30, 10],
			allow_rebuys = False
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		p = self.build_player_lookup(tournament.id)

		# Eliminate in a specific order so we can verify. 9 is the winner here.
		# So expected placement order is: [9, 6, 8, 4, 5, 3, 2, 1, 7]
		eliminatee_order = [p[7].id, p[1].id, p[2].id, p[3].id, p[5].id, p[4].id, p[8].id, p[6].id]
		eliminator_order = [p[5].id, p[9].id, p[9].id, p[9].id, p[9].id, p[9].id, p[4].id, p[9].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order
		)

		self.assertEqual(placement_dict[0].placement_earnings, f"{round(Decimal(621.65), 2)}")
		self.assertEqual(placement_dict[1].placement_earnings, f"{round(Decimal(310.82), 2)}")
		self.assertEqual(placement_dict[2].placement_earnings, f"{round(Decimal(103.61), 2)}")
		self.assertEqual(placement_dict[3].placement_earnings, "0.00")
		self.assertEqual(placement_dict[4].placement_earnings, "0.00")
		self.assertEqual(placement_dict[5].placement_earnings, "0.00")
		self.assertEqual(placement_dict[6].placement_earnings, "0.00")
		self.assertEqual(placement_dict[7].placement_earnings, "0.00")
		self.assertEqual(placement_dict[8].placement_earnings, "0.00")

	"""
	Verify placement earnings is calculated correctly.
	Rebuys enabled, no bounties. (50, 30, 15, 5) payout percentages.
	"""
	def test_placement_earnings_no_bounties_50_30_15_5(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 115.12,
			bounty_amount = None,
			payout_percentages = [50, 30, 15, 5],
			allow_rebuys = True
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		p = self.build_player_lookup(tournament.id)

		# Manunally add some rebuys
		# So 1 has two rebuys. 5, 7 and 8 have one rebuy each.
		rebuys = [p[1].id, p[5].id, p[7].id, p[8].id, p[1].id]
		for player_id in rebuys:
			rebuy_for_test(
				tournament_id = tournament.id,
				player_id = player_id
			)

		# Eliminate in a specific order so we can verify. 9 is the winner here.
		# So expected placement order is: [9, 7, 8, 1, 5, 6, 4, 3, 2]
		eliminatee_order = [p[1].id, p[1].id, p[5].id, p[2].id, p[3].id, p[4].id, p[6].id, p[5].id, p[7].id, p[8].id, p[1].id, p[8].id, p[7].id]
		eliminator_order = [p[2].id, p[5].id, p[9].id, p[7].id, p[8].id, p[1].id, p[1].id, p[9].id, p[8].id, p[1].id, p[9].id, p[7].id, p[9].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order,
			debug = False
		)

		self.assertEqual(placement_dict[0].placement_earnings, f"{round(Decimal(805.84), 2)}")
		self.assertEqual(placement_dict[1].placement_earnings, f"{round(Decimal(483.50), 2)}")
		self.assertEqual(placement_dict[2].placement_earnings, f"{round(Decimal(241.75), 2)}")
		self.assertEqual(placement_dict[3].placement_earnings, f"{round(Decimal(80.58), 2)}")
		self.assertEqual(placement_dict[4].placement_earnings, "0.00")
		self.assertEqual(placement_dict[5].placement_earnings, "0.00")
		self.assertEqual(placement_dict[6].placement_earnings, "0.00")
		self.assertEqual(placement_dict[7].placement_earnings, "0.00")
		self.assertEqual(placement_dict[8].placement_earnings, "0.00")


	"""
	Verify placement earnings is calculated correctly.
	Rebuys enabled, bounties enabled. (50, 30, 15, 5) payout percentages.
	"""
	def test_placement_earnings_rebuys_and_bounty_enabled_50_30_15_5(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 115.12,
			bounty_amount = 25.69,
			payout_percentages = [50, 30, 15, 5],
			allow_rebuys = True
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		p = self.build_player_lookup(tournament.id)

		# Manunally add some rebuys
		# So 1 has two rebuys. 5, 7 and 8 have one rebuy each.
		rebuys = [p[1].id, p[5].id, p[7].id, p[8].id, p[1].id]
		for player_id in rebuys:
			rebuy_for_test(
				tournament_id = tournament.id,
				player_id = player_id
			)

		# Eliminate in a specific order so we can verify. 9 is the winner here.
		# So expected placement order is: [9, 7, 8, 1, 5, 6, 4, 3, 2]
		eliminatee_order = [p[1].id, p[1].id, p[5].id, p[2].id, p[3].id, p[4].id, p[6].id, p[5].id, p[7].id, p[8].id, p[1].id, p[8].id, p[7].id]
		eliminator_order = [p[2].id, p[5].id, p[9].id, p[7].id, p[8].id, p[1].id, p[1].id, p[9].id, p[8].id, p[1].id, p[9].id, p[7].id, p[9].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order,
			debug = False
		)

		self.assertEqual(placement_dict[0].placement_earnings, f"{round(Decimal(626.01), 2)}")
		self.assertEqual(placement_dict[1].placement_earnings, f"{round(Decimal(375.61), 2)}")
		self.assertEqual(placement_dict[2].placement_earnings, f"{round(Decimal(187.80), 2)}")
		self.assertEqual(placement_dict[3].placement_earnings, f"{round(Decimal(62.60), 2)}")
		self.assertEqual(placement_dict[4].placement_earnings, "0.00")
		self.assertEqual(placement_dict[5].placement_earnings, "0.00")
		self.assertEqual(placement_dict[6].placement_earnings, "0.00")
		self.assertEqual(placement_dict[7].placement_earnings, "0.00")
		self.assertEqual(placement_dict[8].placement_earnings, "0.00")


	"""
	Verify placement earnings is calculated correctly.
	Rebuys disabled, bounties enabled. (50, 30, 15, 5) payout percentages.
	"""
	def test_placement_earnings_rebuys_disabled_and_bounty_enabled_50_30_15_5(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 115.12,
			bounty_amount = 25.69,
			payout_percentages = [50, 30, 15, 5],
			allow_rebuys = False
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		p = self.build_player_lookup(tournament.id)

		# Add some split eliminations
		"""
		1. 7 was split eliminated by 2, 5 and 9.
		"""
		split_eliminatee_order = [p[7].id]
		split_eliminator_order = [
			[p[2].id, p[5].id, p[9].id]
		]
		for index,eliminatee_id in enumerate(split_eliminatee_order):
			split_eliminate_player(
				tournament_id = tournament.id,
				eliminator_ids = split_eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Eliminate in a specific order so we can verify. 9 is the winner here.
		eliminatee_order = [p[1].id, p[2].id, p[3].id, p[5].id, p[4].id, p[8].id, p[6].id]
		eliminator_order = [p[9].id, p[9].id, p[9].id, p[9].id, p[9].id, p[4].id, p[9].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order
		)

		# Verify results
		investment_decimal = Decimal("115.12")
		for place in placement_dict.keys():
			self.assertEqual(placement_dict[place].investment, "115.12")
			self.assertEqual(
				[rebuy.player.id for rebuy in placement_dict[place].rebuys],
				[]
			)
			if placement_dict[place].username == "racoon":
				gross_earnings = placement_dict[place].gross_earnings
				bounty_earnings = Decimal(placement_dict[place].bounty_earnings)
				placement_earnings = Decimal(placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				self.assertEqual(gross_earnings, f"{round(placement_earnings + bounty_earnings, 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, f"{round(Decimal(402.44), 2)}")
				self.assertEqual(place, 0)
				self.assertEqual(placement_dict[place].bounty_earnings, f"{round(Decimal(162.62), 2)}")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["cat", "dog", "monkey", "donkey", "bird", "elephant"]
				)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["gator"]
				)
			elif placement_dict[place].username == "insect":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				self.assertEqual(placement_dict[place].gross_earnings, placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].placement_earnings, f"{round(Decimal(120.73), 2)}")
				self.assertEqual(place, 2)
				self.assertEqual(gross_earnings, f"{round(Decimal(120.73), 2)}")
				self.assertEqual(placement_dict[place].bounty_earnings, "0.00")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					[]
				)
			elif placement_dict[place].username == "gator":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				self.assertEqual(placement_dict[place].gross_earnings, "0.00")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 8)
				self.assertEqual(placement_dict[place].bounty_earnings, "0.00")
				self.assertEqual(gross_earnings, "0.00")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					[]
				)
			elif placement_dict[place].username == "elephant":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				self.assertEqual(placement_dict[place].gross_earnings, placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].placement_earnings, f"{round(Decimal(241.46), 2)}")
				self.assertEqual(place, 1)
				self.assertEqual(placement_dict[place].bounty_earnings, "0.00")
				self.assertEqual(gross_earnings, f"{round(Decimal(241.46), 2)}")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					[]
				)
			elif placement_dict[place].username == "donkey":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				bounty_earnings = Decimal(placement_dict[place].bounty_earnings)
				placement_earnings = Decimal(placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 4)
				self.assertEqual(placement_dict[place].bounty_earnings, f"{round(Decimal(8.48), 2)}")
				self.assertEqual(gross_earnings, f"{round(Decimal(8.48), 2)}")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					[]
				)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["gator"]
				)
			elif placement_dict[place].username == "bird":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				bounty_earnings = Decimal(placement_dict[place].bounty_earnings)
				placement_earnings = Decimal(placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].gross_earnings, f"{round(placement_earnings + bounty_earnings, 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, f"{round(Decimal(40.24), 2)}")
				self.assertEqual(place, 3)
				self.assertEqual(gross_earnings, f"{round(Decimal(65.93), 2)}")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["insect"]
				)
			elif placement_dict[place].username == "monkey":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				self.assertEqual(placement_dict[place].gross_earnings, "0.00")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 5)
				self.assertEqual(placement_dict[place].bounty_earnings, "0.00")
				self.assertEqual(gross_earnings, "0.00")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					[]
				)
			elif placement_dict[place].username == "dog":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 6)
				self.assertEqual(placement_dict[place].bounty_earnings, "8.48")
				self.assertEqual(gross_earnings, "8.48")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					[]
				)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["gator"]
				)
			elif placement_dict[place].username == "cat":
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - investment_decimal, 2)}")
				self.assertEqual(placement_dict[place].gross_earnings, "0.00")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 7)
				self.assertEqual(placement_dict[place].bounty_earnings, "0.00")
				self.assertEqual(gross_earnings, "0.00")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					[]
				)

	"""
	Verify placement earnings is calculated correctly.
	Rebuys enabled, bounties enabled. (50, 30, 15, 5) payout percentages.
	"""
	def test_placement_earnings_rebuys_enabled_and_bounty_enabled_50_30_15_5(self):
		# Build a structure made by cat
		cat = User.objects.get_by_username("cat")

		structure = self.build_structure(
			user = cat,
			buyin_amount = 115.12,
			bounty_amount = 25.69,
			payout_percentages = [50, 30, 15, 5],
			allow_rebuys = True
		)

		tournament = self.build_tournament(
			admin = cat,
			title = "Results tournament",
			structure= structure
		)

		# Add players
		players = add_players_to_tournament(
			users = User.objects.all(),
			tournament = tournament
		)

		p = self.build_player_lookup(tournament.id)

		# Start
		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)

		# Manunally add some rebuys
		# So 1 has two rebuys. 5, 7 and 8 have one rebuy each.
		rebuys = [p[1].id, p[5].id, p[5].id, p[7].id, p[7].id, p[8].id, p[1].id]
		for player_id in rebuys:
			rebuy_for_test(
				tournament_id = tournament.id,
				player_id = player_id
			)

		tournament_rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
			tournament_id = tournament.id
		)

		# Add some split eliminations
		"""
		1. 7 was split eliminated by 2, 5 and 9.
		2. 5 was split eliminated by 6 and 4
		"""
		split_eliminatee_order = [p[7].id, p[5].id]
		split_eliminator_order = [
			[p[2].id, p[5].id, p[9].id],
			[p[6].id, p[4].id]
		]
		for index,eliminatee_id in enumerate(split_eliminatee_order):
			split_eliminate_player(
				tournament_id = tournament.id,
				eliminator_ids = split_eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Eliminate in a specific order so we can verify. 9 is the winner here.
		# 2 elim 1, 5 elim 1, 9 elim 5, 7 elim 2, etc...
		eliminatee_order = [p[1].id, p[1].id, p[5].id, p[2].id, p[3].id, p[4].id, p[6].id, p[5].id, p[7].id, p[8].id, p[1].id, p[8].id, p[7].id]
		eliminator_order = [p[2].id, p[5].id, p[9].id, p[7].id, p[8].id, p[1].id, p[1].id, p[9].id, p[8].id, p[1].id, p[9].id, p[7].id, p[9].id]
		for index,eliminatee_id in enumerate(eliminatee_order):
			eliminate_player(
				tournament_id = tournament.id,
				eliminator_id = eliminator_order[index],
				eliminatee_id = eliminatee_id
			)

		# Complete
		Tournament.objects.complete_tournament(user = cat, tournament_id = tournament.id)

		placement_dict = self.build_placement_dict(
			is_backfill = False,
			tournament = tournament,
			eliminatee_order = eliminatee_order,
			eliminator_order = eliminator_order,
			split_eliminatee_order = split_eliminatee_order,
			split_eliminator_order = split_eliminator_order,
			debug = False
		)

		# 1841.92
		# minus bounty: 1430.88
		# bounty: 411.04
		# Verify results
		for place in placement_dict.keys():
			if placement_dict[place].username == "racoon":
				expected_investment = "115.12"
				gross_earnings = placement_dict[place].gross_earnings
				bounty_earnings = Decimal(placement_dict[place].bounty_earnings)
				placement_earnings = Decimal(placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				self.assertEqual(gross_earnings, f"{round(placement_earnings + bounty_earnings, 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, "715.44")
				self.assertEqual(place, 0)
				self.assertEqual(placement_dict[place].bounty_earnings, "111.24")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["donkey", "donkey", "cat", "gator"]
				)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["gator"]
				)
				self.assertEqual(placement_dict[place].investment, "115.12")
				self.assertEqual(len(placement_dict[place].rebuys), 0)
			elif placement_dict[place].username == "insect":
				expected_investment = "230.24"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, "214.63")
				self.assertEqual(place, 2)
				self.assertEqual(gross_earnings, "266.01")
				self.assertEqual(placement_dict[place].bounty_earnings, "51.38")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["monkey", "gator"]
				)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 1)
				self.assertEqual(placement_dict[place].rebuys[0].player.user.username, "insect")
			elif placement_dict[place].username == "gator":
				expected_investment = "345.36"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				self.assertEqual(gross_earnings, "480.64")
				self.assertEqual(placement_dict[place].placement_earnings, "429.26")
				self.assertEqual(place, 1)
				self.assertEqual(placement_dict[place].bounty_earnings, "51.38")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["dog", "insect"]
				)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 2)
				self.assertEqual(placement_dict[place].rebuys[0].player.user.username, "gator")
			elif placement_dict[place].username == "elephant":
				expected_investment = "115.12"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 5)
				self.assertEqual(placement_dict[place].bounty_earnings, "12.84")
				self.assertEqual(gross_earnings, "12.84")
				self.assertEqual(len(placement_dict[place].eliminations), 0)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 0)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["donkey"]
				)
			elif placement_dict[place].username == "donkey":
				expected_investment = "345.36"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				bounty_earnings = Decimal(placement_dict[place].bounty_earnings)
				placement_earnings = Decimal(placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 4)
				self.assertEqual(placement_dict[place].bounty_earnings, "34.17")
				self.assertEqual(gross_earnings, "34.17")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["cat"]
				)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["gator"]
				)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 2)
				self.assertEqual(placement_dict[place].rebuys[0].player.user.username, "donkey")
			elif placement_dict[place].username == "bird":
				expected_investment = "115.12"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				bounty_earnings = Decimal(placement_dict[place].bounty_earnings)
				placement_earnings = Decimal(placement_dict[place].placement_earnings)
				self.assertEqual(placement_dict[place].gross_earnings, f"{round(placement_earnings + bounty_earnings, 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 6)
				self.assertEqual(placement_dict[place].bounty_earnings, "12.84")
				self.assertEqual(gross_earnings, "12.84")
				self.assertEqual(len(placement_dict[place].eliminations), 0)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 0)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["donkey"]
				)
			elif placement_dict[place].username == "monkey":
				expected_investment = "115.12"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				self.assertEqual(placement_dict[place].gross_earnings, "0.00")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 7)
				self.assertEqual(placement_dict[place].bounty_earnings, "0.00")
				self.assertEqual(gross_earnings, "0.00")
				self.assertEqual(len(placement_dict[place].eliminations), 0)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 0)
			elif placement_dict[place].username == "dog":
				expected_investment = "115.12"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				self.assertEqual(placement_dict[place].placement_earnings, "0.00")
				self.assertEqual(place, 8)
				self.assertEqual(placement_dict[place].bounty_earnings, "34.17")
				self.assertEqual(gross_earnings, "34.17")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["cat"]
				)
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].split_eliminations],
					["gator"]
				)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 0)
			elif placement_dict[place].username == "cat":
				expected_investment = "345.36"
				gross_earnings = placement_dict[place].gross_earnings
				self.assertEqual(placement_dict[place].net_earnings, f"{round(Decimal(gross_earnings) - Decimal(expected_investment), 2)}")
				self.assertEqual(gross_earnings, "148.61")
				self.assertEqual(placement_dict[place].placement_earnings, "71.54")
				self.assertEqual(place, 3)
				self.assertEqual(placement_dict[place].bounty_earnings, "77.07")
				self.assertEqual(
					[elimination.eliminatee.user.username for elimination in placement_dict[place].eliminations],
					["bird", "elephant", "insect"]
				)
				self.assertEqual(placement_dict[place].investment, expected_investment)
				self.assertEqual(len(placement_dict[place].rebuys), 2)
				self.assertEqual(placement_dict[place].rebuys[0].player.user.username, "cat")





		

		

		


















