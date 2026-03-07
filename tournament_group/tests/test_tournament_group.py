from django.core.exceptions import ValidationError
from django.test import TestCase

from tournament.models import (
	Tournament
)
from tournament.test_util import (
	build_tournament,
	build_structure,
	add_players_to_tournament,
	eliminate_players_and_complete_tournament
)

from tournament_group.models import TournamentGroup

from user.models import User
from user.test_util import (
	create_users,
	build_user
)

class TournamentGroupTestCase(TestCase):

	def setUp(self):
		# Build some users for the tests
		users = create_users(
			identifiers = ["cat", "dog", "monkey", "bird", "donkey", "elephant", "gator", "insect", "racoon"]
		)

	def create_tournament_group(self, title, admin):
		group = TournamentGroup.objects.create_tournament_group(
			admin = admin,
			title = title
		)
		return group

	"""
	Test the logic in test_add_tournaments_to_group.
	"""
	def test_add_tournaments_to_group(self):
		cat = User.objects.get_by_username("cat")
		title = "Cat's tournament group"
		cats_group = self.create_tournament_group(
			admin = cat,
			title = title
		)
		# Add cats tournament to the group
		structure = build_structure(
			admin = cat, # Cat is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = True
		)

		dog = User.objects.get_by_username("dog")
		tournament = build_tournament(structure, admin_user=cat)

		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)
		tournament = Tournament.objects.complete_tournament(
						user = cat,
						tournament_id = tournament.id
					)

		# Verify you cannot add tournaments to a group if you are not admin
		with self.assertRaisesMessage(ValidationError, "You're not the admin of that TournamentGroup."):
			TournamentGroup.objects.add_tournaments_to_group(
				admin = dog,
				group = cats_group,
				tournaments = [tournament]
			)

		# Verify you cannot add the same tournament more than once.
		with self.assertRaisesMessage(ValidationError, "There is a duplicate in the list of tournaments you're trying to add to this TournamentGroup."):
			TournamentGroup.objects.add_tournaments_to_group(
				admin = cat,
				group = cats_group,
				tournaments = [tournament, tournament]
			)

		# Add a tournament to the group
		TournamentGroup.objects.add_tournaments_to_group(
			admin = cat,
			group = cats_group,
			tournaments = [tournament]
		)
		groups = TournamentGroup.objects.get_tournament_groups(user_id=cat.id)
		self.assertEqual(len(groups), 1)
		self.assertEqual(groups[0].admin, cat)
		self.assertEqual(len(groups[0].get_tournaments()), 1)
		self.assertEqual(groups[0].get_tournaments()[0].admin, cat)

		# Verify you cannot add the same tournament again.
		with self.assertRaisesMessage(ValidationError, f"{tournament.title} is already in this TournamentGroup."):
			TournamentGroup.objects.add_tournaments_to_group(
				admin = cat,
				group = cats_group,
				tournaments = [tournament]
			)

	"""
	Test the logic in remove_tournament_from_group.
	"""
	def test_remove_tournament_from_group(self):
		cat = User.objects.get_by_username("cat")
		title = "Cat's tournament group"
		cats_group = self.create_tournament_group(
			admin = cat,
			title = title
		)
		# Add cats tournament to the group
		structure = build_structure(
			admin = cat, # Cat is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = True
		)

		dog = User.objects.get_by_username("dog")
		tournament = build_tournament(structure, admin_user=cat)

		Tournament.objects.start_tournament(user = cat, tournament_id = tournament.id)
		tournament = Tournament.objects.complete_tournament(
						user = cat,
						tournament_id = tournament.id
					)

		# Add a tournament to the group
		TournamentGroup.objects.add_tournaments_to_group(
			admin = cat,
			group = cats_group,
			tournaments = [tournament]
		)
		groups = TournamentGroup.objects.get_tournament_groups(user_id=cat.id)
		self.assertEqual(len(groups), 1)
		self.assertEqual(groups[0].admin, cat)
		self.assertEqual(len(groups[0].get_tournaments()), 1)
		self.assertEqual(groups[0].get_tournaments()[0].admin, cat)

		# Verify you cannot remove a tournament if you are not the admin
		with self.assertRaisesMessage(ValidationError, "You're not the admin of that TournamentGroup."):
			TournamentGroup.objects.remove_tournament_from_group(
				admin = dog,
				group = cats_group,
				tournament = tournament
			)

		# Verify you cannot remove a tournament that is not in the group
		structure = build_structure(
			admin = dog, # Dog is admin
			buyin_amount = 115,
			bounty_amount = 15,
			payout_percentages = (60, 30, 10),
			allow_rebuys = True
		)
		dog_tournament = build_tournament(structure = structure, admin_user = dog)

		Tournament.objects.start_tournament(user = dog, tournament_id = dog_tournament.id)
		dog_tournament = Tournament.objects.complete_tournament(
						user = dog,
						tournament_id = dog_tournament.id
					)

		with self.assertRaisesMessage(ValidationError, f"{dog_tournament.title} is not in this TournamentGroup."):
			TournamentGroup.objects.remove_tournament_from_group(
				admin = cat,
				group = cats_group,
				tournament = dog_tournament
			)

		# Remove the Tournament from the group
		TournamentGroup.objects.remove_tournament_from_group(
			admin = cat,
			group = cats_group,
			tournament = tournament
		)
		group = TournamentGroup.objects.get_by_id(cats_group.id)
		self.assertEqual(len(group.get_tournaments()), 0)

	"""
	get_users() should return all distinct users who are players in any tournament in the group.
	"""
	def test_get_users_derives_from_tournament_players(self):
		cat = User.objects.get_by_username("cat")
		dog = User.objects.get_by_username("dog")
		bird = User.objects.get_by_username("bird")

		group = self.create_tournament_group(admin=cat, title="Test Group")

		# Empty group — no users
		self.assertEqual(len(group.get_users()), 0)

		# Build a tournament with cat as admin (auto-added as player) and dog as additional player
		structure = build_structure(
			admin=cat,
			buyin_amount=100,
			bounty_amount=10,
			payout_percentages=(60, 30, 10),
			allow_rebuys=False
		)
		tournament = build_tournament(structure, admin_user=cat)
		add_players_to_tournament([dog], tournament)
		Tournament.objects.start_tournament(user=cat, tournament_id=tournament.id)
		eliminate_players_and_complete_tournament(admin=cat, tournament=tournament)
		tournament = Tournament.objects.get_by_id(tournament.id)

		TournamentGroup.objects.add_tournaments_to_group(
			admin=cat,
			group=group,
			tournaments=[tournament]
		)

		users = group.get_users()
		self.assertEqual(len(users), 2)
		self.assertIn(cat, users)
		self.assertIn(dog, users)
		self.assertNotIn(bird, users)

	"""
	A user who plays in multiple tournaments in the group should appear only once.
	"""
	def test_get_users_returns_distinct_users(self):
		cat = User.objects.get_by_username("cat")
		dog = User.objects.get_by_username("dog")

		group = self.create_tournament_group(admin=cat, title="Test Group")

		structure = build_structure(
			admin=cat,
			buyin_amount=100,
			bounty_amount=10,
			payout_percentages=(60, 30, 10),
			allow_rebuys=False
		)

		# Two tournaments both with cat and dog as players
		t1 = build_tournament(structure, admin_user=cat)
		add_players_to_tournament([dog], t1)
		Tournament.objects.start_tournament(user=cat, tournament_id=t1.id)
		eliminate_players_and_complete_tournament(admin=cat, tournament=t1)
		t1 = Tournament.objects.get_by_id(t1.id)

		t2 = build_tournament(structure, admin_user=cat)
		add_players_to_tournament([dog], t2)
		Tournament.objects.start_tournament(user=cat, tournament_id=t2.id)
		eliminate_players_and_complete_tournament(admin=cat, tournament=t2)
		t2 = Tournament.objects.get_by_id(t2.id)

		TournamentGroup.objects.add_tournaments_to_group(
			admin=cat, group=group, tournaments=[t1, t2]
		)

		users = group.get_users()
		self.assertEqual(len(users), 2)

	"""
	get_tournament_groups should return groups where the user played in at least one tournament.
	"""
	def test_get_tournament_groups_returns_groups_user_played_in(self):
		cat = User.objects.get_by_username("cat")
		dog = User.objects.get_by_username("dog")
		bird = User.objects.get_by_username("bird")

		cats_group = self.create_tournament_group(admin=cat, title="Cat's Group")
		dogs_group = self.create_tournament_group(admin=dog, title="Dog's Group")

		# Cat plays in a tournament added to cat's group
		structure = build_structure(
			admin=cat,
			buyin_amount=100,
			bounty_amount=10,
			payout_percentages=(60, 30, 10),
			allow_rebuys=False
		)
		cat_tournament = build_tournament(structure, admin_user=cat)
		Tournament.objects.start_tournament(user=cat, tournament_id=cat_tournament.id)
		cat_tournament = Tournament.objects.complete_tournament(user=cat, tournament_id=cat_tournament.id)
		TournamentGroup.objects.add_tournaments_to_group(
			admin=cat, group=cats_group, tournaments=[cat_tournament]
		)

		# Dog plays in a tournament added to dog's group
		structure2 = build_structure(
			admin=dog,
			buyin_amount=100,
			bounty_amount=10,
			payout_percentages=(60, 30, 10),
			allow_rebuys=False
		)
		dog_tournament = build_tournament(structure2, admin_user=dog)
		Tournament.objects.start_tournament(user=dog, tournament_id=dog_tournament.id)
		dog_tournament = Tournament.objects.complete_tournament(user=dog, tournament_id=dog_tournament.id)
		TournamentGroup.objects.add_tournaments_to_group(
			admin=dog, group=dogs_group, tournaments=[dog_tournament]
		)

		# cat should see only cat's group
		cat_groups = TournamentGroup.objects.get_tournament_groups(user_id=cat.id)
		self.assertEqual(len(cat_groups), 1)
		self.assertEqual(cat_groups[0], cats_group)

		# dog should see only dog's group
		dog_groups = TournamentGroup.objects.get_tournament_groups(user_id=dog.id)
		self.assertEqual(len(dog_groups), 1)
		self.assertEqual(dog_groups[0], dogs_group)

		# bird has no tournaments anywhere — sees nothing
		bird_groups = TournamentGroup.objects.get_tournament_groups(user_id=bird.id)
		self.assertEqual(len(bird_groups), 0)
