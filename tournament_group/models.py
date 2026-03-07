from enum import Enum
from itertools import chain
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from datetime import datetime
import pytz

from tournament.models import (
	Tournament,
	TournamentPlayer,
	TournamentPlayerResult,
	TournamentState,
	TournamentElimination,
	TournamentSplitElimination,
	TournamentRebuy
)
from tournament_group.util import (
	TournamentGroupNetEarnings,
	TournamentGroupPotContributions,
	TournamentGroupEliminationsAndRebuys,
	TournamentGroupTournamentsPlayed
)
from user.models import User

class TournamentGroupManager(models.Manager):

	def create_tournament_group(self, admin, title):
		group = self.model(
			admin = admin,
			title = title
		)
		group.save(using=self._db)
		return group

	def add_tournaments_to_group(self, admin, group, tournaments):
		if group.admin != admin:
			raise ValidationError("You're not the admin of that TournamentGroup.")

		tournament_set = set(tournaments)
		if len(tournament_set) != len(tournaments):
			raise ValidationError("There is a duplicate in the list of tournaments you're trying to add to this TournamentGroup.")

		current_tournaments = group.get_tournaments()
		for tournament in tournaments:
			if tournament in current_tournaments:
				raise ValidationError(f"{tournament.title} is already in this TournamentGroup.")

		for tournament in tournaments:
			if tournament.get_state() != TournamentState.COMPLETED:
				raise ValidationError(f"Only completed tournaments can be added to a Tournament Group.")

		# Only add tournaments that fall within the allowed date range.
		if group.start_at != None:
			for tournament in tournaments:
				if tournament.completed_at < group.start_at:
					raise ValidationError(f"The completion date for '{tournament.title}' does not fall within the allowed date range.")
		if group.end_at != None:
			for tournament in tournaments:
				if tournament.completed_at > group.end_at:
					raise ValidationError(f"The completion date for '{tournament.title}' does not fall within the allowed date range.")

		updated_group = group
		updated_group.tournaments.add(*tournaments)
		updated_group.save()
		return updated_group

	def remove_tournament_from_group(self, admin, group, tournament):
		if group.admin != admin:
			raise ValidationError("You're not the admin of that TournamentGroup.")

		current_tournaments = group.get_tournaments()
		if not tournament in current_tournaments:
			raise ValidationError(f"{tournament.title} is not in this TournamentGroup.")

		updated_group = group
		updated_group.tournaments.remove(*[tournament])
		updated_group.save()
		return updated_group


	def update_tournament_group_title(self, admin, group, title):
		if group.admin != admin:
			raise ValidationError(f"You're not the admin of that TournamentGroup.")

		if title == None:
			raise ValidationError("Tournament Group title cannot be empty.")

		updated_group = group
		updated_group.title = title
		updated_group.save()
		return updated_group

	def get_by_id(self, id):
		try:
			tournament_group = self.get(id = id)
			return tournament_group
		except TournamentGroup.DoesNotExist:
			return None

	"""
	Get TournamentGroup's that this user is part of (i.e. played in at least one tournament in the group).
	"""
	def get_tournament_groups(self, user_id):
		user = User.objects.get_by_id(user_id)
		from django.db.models import Q
		return super().get_queryset().filter(
			Q(admin=user) | Q(tournaments__tournamentplayer__user=user)
		).distinct()

	"""
	Build a list of TournamentGroupNetEarnings for each user in the group.
	Note: This is a heavy operation and should be done async.
	"""
	def build_group_net_earnings_data(self, group):
		net_earnings_data = []
		tournaments = group.get_tournaments()
		for user in group.get_users():
			net_earnings = 0
			for tournament in tournaments:
				if tournament.get_state() == TournamentState.COMPLETED:
					result = TournamentPlayerResult.objects.get_results_for_user_by_tournament(
						user_id = user.id,
						tournament_id = tournament.id
					)
					if len(result) == 0:
						continue
					else:
						net_earnings += result[0].net_earnings
			net_earnings_data.append(
				TournamentGroupNetEarnings(
					username = f"{user.username}",
					net_earnings = net_earnings
				)
			)
		return sorted(
			net_earnings_data,
			key = lambda x: x.net_earnings,
			reverse = True
		)

	"""
	Build a list of TournamentGroupPotContributions for each user in the group.
	Note: This is a heavy operation and should be done async.
	"""
	def build_group_pot_contributions_data(self, group):
		pot_contributions = []
		tournaments = group.get_tournaments()
		for user in group.get_users():
			contribution = 0
			for tournament in tournaments:
				if tournament.get_state() == TournamentState.COMPLETED:
					result = TournamentPlayerResult.objects.get_results_for_user_by_tournament(
						user_id = user.id,
						tournament_id = tournament.id
					)
					if len(result) == 0:
						continue
					else:
						contribution += result[0].investment
			pot_contributions.append(
				TournamentGroupPotContributions(
					username = f"{user.username}",
					contribution = contribution
				)
			)
		return sorted(
			pot_contributions,
			key = lambda x: x.contribution,
			reverse = True
		)

	"""
	Build a list of TournamentGroupEliminationsAndRebuys for each user in the group.
	Note: This is a heavy operation and should be done async.
	"""
	def build_group_eliminations_and_rebuys_data(self, group):
		eliminations_and_rebuys_data = []
		tournaments = group.get_tournaments()
		for user in group.get_users():
			eliminations_count = 0.00
			rebuys_count = 0
			for tournament in tournaments:
				if tournament.get_state() == TournamentState.COMPLETED:
					players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(user.id).filter(tournament = tournament)
					if len(players) > 1:
						raise ValidationError(f"According to our records {user.username} was added to {tournament.title} more than once.")
					elif len(players) == 0:
						continue
					player = players[0]
					eliminations = TournamentElimination.objects.get_eliminations_by_eliminator(
						player_id = player.id
					)
					eliminations_count += len(eliminations)
					split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
						player_id = player.id
					)
					for split_elimination in split_eliminations:
						eliminator_count = len(split_elimination.eliminators.all())
						eliminations_count += round((1.00 / eliminator_count), 2)
					rebuys = TournamentRebuy.objects.get_rebuys_for_player(
						player = player
					)
					rebuys_count += len(rebuys)
			eliminations_and_rebuys_data.append(
				TournamentGroupEliminationsAndRebuys(
					username = f"{user.username}",
					eliminations = eliminations_count,
					rebuys = rebuys_count
				)
			)
		return sorted(
			eliminations_and_rebuys_data,
			key = lambda x: x.eliminations,
			reverse = True
		)

	"""
	Build a list of TournamentGroupTournamentsPlayed for each user in the group.
	Note: This is a heavy operation and should be done async.
	"""
	def build_group_tournaments_played_data(self, group):
		tournaments_played_data = []
		tournaments = group.get_tournaments()
		for user in group.get_users():
			count = 0
			for tournament in tournaments:
				if tournament.get_state() == TournamentState.COMPLETED:
					players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(user.id).filter(tournament = tournament)
					if len(players) > 1:
						raise ValidationError(f"According to our records {user.username} was added to {tournament.title} more than once.")
					elif len(players) == 0:
						continue
					count += 1
			tournaments_played_data.append(
				TournamentGroupTournamentsPlayed(
					username = f"{user.username}",
					count = count,
				)
			)
		return sorted(
			tournaments_played_data,
			key = lambda x: x.count,
			reverse = True
		)

	"""
	Format of 'end_at_date': 2023/03/16
	"""
	def update_end_at_date(self, user, group, end_at_date):
		if user != group.admin:
			raise ValidationError("You're not the Tournament Group admin!")

		# Make it timezone aware and force time to 11:59.
		timezone = pytz.timezone('US/Pacific')
		date_with_time_added = f"{end_at_date} 23:59"
		datetime_object = timezone.localize(datetime.strptime(date_with_time_added, "%Y/%m/%d %H:%M"))

		if group.start_at != None:
			if datetime_object < group.start_at:
				raise ValidationError("The 'end date' cannot be before the 'start date'.")

		updated_group = TournamentGroup.objects.get_by_id(group.id)
		updated_group.end_at = datetime_object
		updated_group.save()
		return updated_group

	"""
	Format of 'start_at_date': 2023/03/16
	"""
	def update_start_at_date(self, user, group, start_at_date):
		if user != group.admin:
			raise ValidationError("You're not the Tournament Group admin!")

		# Make it timezone aware and force time to 12:00am.
		timezone = pytz.timezone('US/Pacific')
		date_with_time_added = f"{start_at_date} 00:00"
		datetime_object = timezone.localize(datetime.strptime(date_with_time_added, "%Y/%m/%d %H:%M"))

		if group.end_at != None:
			if datetime_object > group.end_at:
				raise ValidationError("The 'start date' cannot be after the 'end date'.")

		updated_group = TournamentGroup.objects.get_by_id(group.id)
		updated_group.start_at = datetime_object
		updated_group.save()
		return updated_group

"""
Used to denote the state of the TournamentGroup with respect to start_at and end_at fields.
1. NONE: start_at == None and end_at == None
2. STARTED: start_at != None and end_at == None
3. ENDED: start_at != None and end_at  != None
"""
class TournamentGroupState(Enum):
	NONE = 0
	STARTED = 1
	ENDED = 2

class TournamentGroup(models.Model):
	admin					= models.ForeignKey(User, on_delete=models.CASCADE)
	title					= models.CharField(blank=False, null=False, max_length=255, unique=False)
	tournaments				= models.ManyToManyField(Tournament, related_name="tournaments_in_group")

	"""
	start_at and end_at are dates marking the start and end date of the group. This can be used to
	implement "seasons". Example: A 2023 season would start January 1 2023 and end Decemeber 31 2023.
	"""
	start_at				= models.DateTimeField(null=True, blank=True)
	end_at					= models.DateTimeField(null=True, blank=True)

	objects = TournamentGroupManager()

	def __str__(self):
		return f"""\n
		Title: {self.title}\n
		Admin: {self.admin.username}\n
		"""

	def get_tournaments(self):
		return self.tournaments.all().order_by("-started_at")

	def get_users(self):
		player_user_ids = TournamentPlayer.objects.filter(
			tournament__in=self.tournaments.all()
		).values_list('user_id', flat=True).distinct()
		return User.objects.filter(id__in=player_user_ids)

	def get_state(self):
		if self.start_at == None and self.end_at == None:
			return TournamentGroupState.NONE
		elif self.start_at != None and self.end_at == None:
			return TournamentGroupState.STARTED
		else:
			return TournamentGroupState.ENDED

	"""
	Return how many days have elapsed since the TournamentGroup started.
	"""
	def get_progress(self):
		if self.get_state() != TournamentGroupState.NONE:
			return (timezone.now() - self.start_at).days
		else:
			return None

	"""
	Return how many days until since the TournamentGroup ends.
	"""
	def get_days_remaining(self):
		if self.get_state() != TournamentGroupState.NONE:
			return (self.end_at - timezone.now()).days
		else:
			return None

	"""
	Return how many days the TournamentGroup is active for.
	"""
	def get_group_duration(self):
		if self.get_state() != TournamentGroupState.NONE:
			return (self.end_at - self.start_at).days
		else:
			return None
