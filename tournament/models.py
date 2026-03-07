import json
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from enum import Enum
from io import StringIO
from itertools import chain

from user.models import User

PERCENTAGE_VALIDATOR = [MinValueValidator(0), MaxValueValidator(100)]

from tournament.util import build_placement_string, PlayerTournamentPlacement, DID_NOT_PLACE_VALUE


"""
Checks if
(1) the payout_percentages sum to 100
(2) every value in payout_percentages is between 0 and 100.
"""
def validate_percentages(payout_percentages):
	total = 0
	for pct in payout_percentages:
		if pct > 100 or pct < 0:
			raise ValidationError("Each payout percentage must be between 0 and 100.")
		total += pct
	if total != 100:
		raise ValidationError("Payout Percentages must sum to 100")
	
class TournamentStructureManager(models.Manager):

	# USED FOR TESTING ONLY... create new fn using the USER instead of user_email.
	# from tournament.models import TournamentStructure
	# TournamentStructure.objects.create_tournament_struture_test("mitchs tournmanet structure", "mitch@tabian.ca", 60, 10, (70,20,10), True)
	def create_tournament_struture_test(self, title, user_email, buyin_amount, bounty_amount, payout_percentages, allow_rebuys):
		user = User.objects.get_by_email(user_email)
		validate_percentages(payout_percentages)
		tournament_structure = self.model(
			title=title,
			user=user,
			buyin_amount=buyin_amount,
			bounty_amount=bounty_amount,
			payout_percentages=payout_percentages,
			allow_rebuys=allow_rebuys
		)
		tournament_structure.save(using=self._db)
		return tournament_structure

	def create_tournament_struture(self, title, user, buyin_amount, bounty_amount, payout_percentages, allow_rebuys):
		validate_percentages(payout_percentages)
		tournament_structure = self.model(
			title=title,
			user=user,
			buyin_amount=buyin_amount,
			bounty_amount=bounty_amount,
			payout_percentages=payout_percentages,
			allow_rebuys=allow_rebuys
		)
		tournament_structure.save(using=self._db)
		return tournament_structure

	# ONLY USE FOR TESTING
	def get_structures_by_user_email(self, user_email):
		user = User.objects.get_by_email(user_email)
		structures = super().get_queryset().filter(user=user)
		return structures

	def get_structures_by_user(self, user):
		structures = super().get_queryset().filter(user=user)
		return structures

	def get_by_id(self, id):
		try:
			structure = self.get(pk=id)
		except TournamentStructure.DoesNotExist:
			structure = None
		return structure

"""
Note: buyin_amount already takes into account the bounty_amount. 
Ex: If buyin_amount=60 and bounty_amount=10, the total amount a user must pay to play is 60.
"""
class TournamentStructure(models.Model):
	title 					= models.CharField(max_length=254, blank=False, null=False)

	# The user that created this tournament structure.
	user 					= models.ForeignKey(User, on_delete=models.CASCADE)

	# Cost to buy into this tournament.
	buyin_amount			= models.DecimalField(max_digits=9, decimal_places=2, blank=False, null=False)

	# Optional. Not all tournaments must have bounties. If this is null, it is not a bounty tournament.
	bounty_amount			= models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)
	
	"""
	Ex: (70, 20, 10)
	"""
	payout_percentages		= ArrayField(
								models.DecimalField(
									max_digits=3,
									decimal_places=0,
									default=0,
									validators=PERCENTAGE_VALIDATOR
								),
								validators=[validate_percentages]
							)
	allow_rebuys 			= models.BooleanField(default=False)


	objects = TournamentStructureManager()

	def __str__(self):
		return self.title

	def is_bounty_tournament(self):
		if self.bounty_amount != None:
			return True
		else:
			return False

	"""
	Builds a JSON representations of a TournamentStructure.
	"""
	def buildJson(self):
		data = {}
		data['pk'] = self.pk
		data['title'] = self.title
		data['buyin_amount'] = f"{self.buyin_amount}"
		if self.bounty_amount != None:
			data['bounty_amount'] = f"{self.bounty_amount}"
		payout_percentages = []
		for pct in self.payout_percentages:
			payout_percentages.append(f"{pct}")
		data['payout_percentages'] = payout_percentages
		return json.dumps(data)

class TournamentManager(models.Manager):

	def create_tournament(self, title, user, tournament_structure):
		if tournament_structure.user != user:
			raise ValidationError("You cannot use a Tournament Structure that you don't own.")
		tournament = self.model(
			title=title,
			admin=user,
			tournament_structure=tournament_structure
		)
		tournament.save(using=self._db)

		# The admin automatically becomes a player in the tournament
		player = TournamentPlayer.objects.create_player_for_tournament(
			user_id = user.id,
			tournament_id = tournament.id	
		)

		return tournament

	# from tournament.models import Tournament
	# Tournament.objects.email_tournament_results(1)
	"""
	Email the results of a tournament to all the players.
	This is mainly for data backup reasons. Like if for some reason an admin accidentally "undo-completion" and 
	their data is lost. At least they'll have this text backup.
	"""
	def email_tournament_results(self, tournament_id):
		try:
			tournament = self.get(pk=tournament_id)
			subject = f"{settings.ACCOUNT_EMAIL_SUBJECT_PREFIX} results for tournament."
			message = f"Here are the results for the Tournament you played on {tournament.completed_at}."
			payout_string = '('
			for i, pct in enumerate(tournament.tournament_structure.payout_percentages):
				if i != 0:
					payout_string += ', '
				payout_string += f'{build_placement_string(i)}: {pct}%'
			payout_string += ')'
			is_bounty_tournament = f'{tournament.tournament_structure.buyin_amount != None}'
			allow_rebuys = f'{tournament.tournament_structure.allow_rebuys}'
			buyin_amount = f'${tournament.tournament_structure.buyin_amount}'
			bounty_amount = tournament.tournament_structure.bounty_amount
			if bounty_amount == None:
				bounty_amount = "N/A"
			else:
				bounty_amount = f"${bounty_amount}"
			
			players = TournamentPlayer.objects.get_tournament_players(
				tournament_id = tournament.id
			)
			players_string = ''
			total_players = 0
			player_rebuys_string = '\n'
			total_rebuys = 0
			for i, player in enumerate(players):
				total_players += 1
				if i != 0:
					players_string += ', '
				players_string += f'{player.user.username}'
				rebuys = TournamentRebuy.objects.get_rebuys_for_player(
					player = player
				)
				if len(rebuys) > 0:
					total_rebuys += len(rebuys)
					player_rebuys_string += f'\t\t\t\t{player.user.username}: ({len(rebuys)})\n'

			if not tournament.tournament_structure.allow_rebuys:
				player_rebuys_string = "N/A"

			eliminations = TournamentElimination.objects.get_eliminations_by_tournament(
				tournament_id = tournament.id,
			)
			split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(
				tournament_id = tournament.id,
			)
			combined_eliminations = list(chain(eliminations, split_eliminations))
			combined_eliminations.sort(key=lambda elimination: elimination.eliminated_at)
			player_eliminations_string = '\n'
			total_eliminations = 0
			for elimination in combined_eliminations:
				total_eliminations += 1
				if type(elimination) is TournamentElimination:
					player_eliminations_string += f'\t\t\t\t{elimination.eliminator.user.username}: eliminated {elimination.eliminatee.user.username} at {elimination.eliminated_at}\n'
				if type(elimination) is TournamentSplitElimination:
					player_split_elimination_string = [f"{player.user.username}, " for player in elimination.eliminators.all()]
					player_eliminations_string += f'\t\t\t\t{player_split_elimination_string}: eliminated {elimination.eliminatee.user.username} at {elimination.eliminated_at}\n'
			
			results = TournamentPlayerResult.objects.get_results_for_tournament(
				tournament_id = tournament.id
			).order_by("placement")
			placement_string = '\n'
			for result in results:
				placement_string += f'\t\t\t\t{build_placement_string(result.placement)}: {result.player.user.username}\n'
				
			total_pot_value = f'${round(Decimal((len(players) + total_rebuys) * tournament.tournament_structure.buyin_amount), 2)}'

			f = StringIO()
			f.write(f'''\n
				Tournament Title: {tournament.title}\n
				Completed on: {tournament.completed_at}\n
				Bounty Tournament? {is_bounty_tournament}\n
				Allow rebuys? {allow_rebuys}\n
				Payout percentages: {payout_string}\n
				Buyin amount: {buyin_amount}\n
				Bounty amount: {bounty_amount}\n
				Players: {players_string}\n
				Num players: {total_players}\n
				Placements: {placement_string}
				Num rebuys: {total_rebuys}\n
				Player rebuys: {player_rebuys_string}
				Player Eliminations: {player_eliminations_string}
				Total Tournament value: {total_pot_value}
				\n''')
			f.seek(0)
			msg = MIMEBase('application', "octet-stream")
			msg.set_payload(f.read())
			encoders.encode_base64(msg)
			msg.add_header(
				'Content-Disposition',
				'attachment',
				filename='tournament_summary.txt'
			)
			players = TournamentPlayer.objects.get_tournament_players(
				tournament_id = tournament.id
			)
			emails = [player.user.email for player in players]
			mail = EmailMessage(subject, message, settings.EMAIL_HOST_USER, emails)
			mail.attach(msg)
			mail.send()
		except Exception as e:
			# Fail silently.
			# TODO add bugsnag call here.
			pass

	def complete_tournament(self, user, tournament_id):
		tournament = self.get(pk=tournament_id)
		try:
			if tournament.admin != user:
				raise ValidationError("You cannot update a Tournament if you're not the admin.")
			if tournament.started_at is None:
				raise ValidationError("You can't complete a Tournament that has not been started.")
			if tournament.completed_at is not None:
				raise ValidationError("This tournament is already completed.")

			# Verify every player except 1 has been eliminated. This will raise if false.
			self.is_completable(tournament_id)

			tournament.completed_at = timezone.now()
			tournament.save(using=self._db)

			# Calculate the TournamentPlayerResultData for each player. These are saved to db.
			results = TournamentPlayerResult.objects.build_results_for_tournament(tournament_id)

			# Email the results to all the players
			self.email_tournament_results(tournament.id)

			return tournament
		except Exception as e:
			# If anything goes wrong we need to reset the Tournament back into the active state.
			tournament.completed_at = None
			tournament.save(using=self._db)
			# Also delete any results that were generated.
			results = TournamentPlayerResult.objects.get_results_for_tournament(
				tournament_id = tournament.id
			)
			for result in results:
				result.delete()
			raise e

	"""
	Complete a Tournament that was create via a the backfill process (see tournament.views.tournament_backfill_view).

	player_tournament_placements: list of PlayerTournamentPlacement.

	elim_dict: dictionary containg the eliminations data.
	Format: key = id of the eliminator player. values = list of players they eliminated.
		{
			'player_id0': [player1, player5, ...],
			'player_id1': [player2, player3, ...],
			...
		}

	split_eliminations: data for split eliminations.
	Format:
	[{
      "eliminators": [
	    "<player5>"
	    "<player23>"
      ],
      "eliminatee":"<player8>"
     },
     {
       "eliminators": [
	     "<player6>"
	     "<player23>"
         "<player67>"
       ],
        "eliminatee":"<player9>"
      }, ...
      ]
	"""
	def complete_tournament_for_backfill(self, user, tournament_id, player_tournament_placements, elim_dict, split_eliminations):
		tournament = self.get(pk=tournament_id)
		if tournament.admin != user:
			raise ValidationError("You cannot update a Tournament if you're not the admin.")
		if tournament.started_at is not None:
			raise ValidationError("You can't backfill an active Tournment.")
		if tournament.completed_at is not None:
			raise ValidationError("You can't backfill a completed Tournment.")

		# Split elimination validation
		for split_elim_data in split_eliminations:
			eliminatee = split_elim_data['eliminatee']
			eliminators = split_elim_data['eliminators']
			if len(eliminators) <= 1:
				raise ValidationError("Split Elimination Error: You must specify more than one eliminator for a split elimination.")
			if eliminatee in eliminators:
				raise ValidationError(f"Split Elimination Error: {eliminatee.user.username} cannot eliminate themself.")
			if eliminatee.tournament != tournament:
				raise ValidationError(f"Split Elimination Error: {eliminatee.user.username} is not part of this tournament.")
			for eliminator in eliminators:
				if eliminator.tournament != tournament:
					raise ValidationError(f"Split Elimination Error: {eliminator.user.username} is not part of this tournament.")
			if len(set(eliminators)) != len(eliminators):
				raise ValidationError("Split Elimination Error: Cannot list the same eliminator more than once.")

		# Verify the number of placements equals the number of payout percentages
		num_placement_positions = len(tournament.tournament_structure.payout_percentages)
		placement_count = 0
		for placed_player in player_tournament_placements:
			if placed_player.placement != DID_NOT_PLACE_VALUE:
				placement_count += 1
		if num_placement_positions != placement_count:
			raise ValidationError(f"The tournament structure requires you select {num_placement_positions} players who placed in the tournament.")

		# Verify the same player isn't specified for multiple placements.
		placed_player_ids = [value.player_id for value in player_tournament_placements]
		if len(placed_player_ids) != len(set(placed_player_ids)):
			raise ValidationError("You can't specify the same player for multiple placements.")

		# Find winner
		winning_player = None
		for player_tournament_placement in player_tournament_placements:
			if player_tournament_placement.placement == 0:
				winning_player = TournamentPlayer.objects.get_by_id(player_tournament_placement.player_id)

		"""
		Add the rebuys. First we need to determine who needs rebuys from the elim_dict and split_eliminations.
			'rebuys' is a dict of player id's as the key and a an integer representing the number 
			of rebuys they need.
		Format:
		{
			'<player_id>': <num_rebuys>
		}
		"""
		rebuys_dict = {}
		# Rebuys from eliminations
		for player_id in elim_dict:
			for eliminated_player in elim_dict[player_id]:
				if eliminated_player.id not in rebuys_dict:
					# First time they were eliminated. Add an entry to the dict with a value of 0
					# since the initial buyin does not count as a rebuy.
					if eliminated_player.id == winning_player.id:
						# Start the winning players rebuy counter at 1 since a rebuy won't be added
						# because they get populated based on eliminations.
						rebuys_dict[eliminated_player.id] = 1
					else:
						rebuys_dict[eliminated_player.id] = 0
				else:
					# They already exist in the rebuys_dict. Increment the value.
					num_rebuys = rebuys_dict[eliminated_player.id]
					num_rebuys += 1
					rebuys_dict[eliminated_player.id] = num_rebuys
		# Rebuys from split eliminations
		for elim_data in split_eliminations:
			eliminatee = elim_data['eliminatee']
			if eliminatee.id not in rebuys_dict:
				# First time they were eliminated. Add an entry to the dict with a value of 0
				# since the initial buyin does not count as a rebuy.
				if eliminatee.id == winning_player.id:
					# Start the winning players rebuy counter at 1 since a rebuy won't be added
					# because they get populated based on eliminations.
					rebuys_dict[eliminatee.id] = 1
				else:
					rebuys_dict[eliminatee.id] = 0
			else:
				# They already exist in the rebuys_dict. Increment the value.
				num_rebuys = rebuys_dict[eliminatee.id]
				num_rebuys += 1
				rebuys_dict[eliminatee.id] = num_rebuys


		# DEBUG
		# for player_id in rebuys_dict:
		# 	player = TournamentPlayer.objects.get_by_id(player_id)
		# 	print(f"{player.user.username}, rebuys: {rebuys_dict[player_id]}")

		# Verify if a player did not win, they must have been eliminated at least once.
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		).exclude(id=winning_player.id)
		for player in players:
			num_times_player_was_eliminated = 0
			for player_id in  elim_dict.keys():
				for eliminated_player in elim_dict[player_id]:
					if player == eliminated_player:
						num_times_player_was_eliminated += 1
			for elim_data in split_eliminations:
				eliminatee = elim_data['eliminatee']
				if player == eliminatee:
					num_times_player_was_eliminated += 1
			if num_times_player_was_eliminated == 0:
				raise ValidationError(f"{player.user.username} did not win, they must have been eliminated at least once.")

		try:
			# Activate the tournament
			tournament.started_at = timezone.now()
			tournament.save(using=self._db)

			# Build the rebuys
			if tournament.tournament_structure.allow_rebuys == True:
				for player_id in rebuys_dict:
					for i in range(0, rebuys_dict[player_id]):
						rebuy = TournamentRebuy.objects.backfill_rebuy(
							tournament_id = tournament.id,
							player_id = player_id
						)

			# Add the eliminations
			eliminations = self.build_eliminations_for_backfilled_tournament(
				tournament_id = tournament.id,
				elim_dict = elim_dict
			)

			# Add split eliminations
			split_eliminations = self.build_split_eliminations_for_backfilled_tournament(
				tournament_id = tournament.id,
				split_eliminations = split_eliminations
			)

			# Complete the Tournament
			tournament.completed_at = timezone.now()
			tournament.save(using=self._db)

			# Calculate the TournamentPlayerResult data for each player. These are saved to db.
			results = TournamentPlayerResult.objects.build_results_for_backfilled_tournament(
				player_tournament_placements = player_tournament_placements,
				tournament_id = tournament_id
			)
		except Exception as e:
			"""
			If something goes wrong building the results, we need:
			1. undo activation
			2. undo completion
			3. delete rebuys
			4. delete eliminations
			5. delete split eliminations
			"""
			Tournament.objects.delete_all_rebuys_and_eliminations(
				admin = tournament.admin,
				tournament_id = tournament.id
			)
			# Delete any Tournament results.
			TournamentPlayerResult.objects.delete_results_for_tournament(tournament.id)
			tournament.started_at = None
			tournament.completed_at = None
			tournament.save(using=self._db)
			raise e

		return tournament

	"""
	elim_dict: dictionary containg the eliminations data.
	Format: key = id of the eliminator player. values = list of players they eliminated.
		{
			'player_id0': [player1, player5, ...],
			'player_id1': [player2, player3, ...],
			...
		}
	"""
	def build_eliminations_for_backfilled_tournament(self, tournament_id, elim_dict):
		eliminations = []
		for player_id in elim_dict:
			eliminated_players = elim_dict[player_id]
			for player in eliminated_players:
				elimination = TournamentElimination.objects.create_backfill_elimination(
					tournament_id = tournament_id,
					eliminator_id = player_id,
					eliminatee_id = player.id
				)
				eliminations.append(elimination)
		return eliminations

	"""
	split_eliminations: data for split eliminations.
	Format:
	[{
      "eliminators": [
	    "<player5>"
	    "<player23>"
      ],
      "eliminatee":"<player8>"
     },
     {
       "eliminators": [
	     "<player6>"
	     "<player23>"
         "<player67>"
       ],
        "eliminatee":"<player9>"
      }, ...
      ]
	"""
	def build_split_eliminations_for_backfilled_tournament(self, tournament_id, split_eliminations):
		eliminations = []
		for elim_data in split_eliminations:
			eliminators = elim_data['eliminators']
			eliminatee = elim_data['eliminatee']
			elimination = TournamentSplitElimination.objects.create_backfill_split_elimination(
				tournament_id = tournament_id,
				eliminators = eliminators,
				eliminatee = eliminatee
			)
			eliminations.append(elimination)
		return eliminations

	"""
	Undo tournament completion.
	When you do this, all the elimations and rebuys data is deleted. Essentially you start a blank slate.
	"""
	def undo_complete_tournament(self, user, tournament_id):
		tournament = self.get(pk=tournament_id)
		if tournament.admin != user:
			raise ValidationError("You cannot update a Tournament if you're not the admin.")
		if tournament.completed_at is None:
			raise ValidationError("The tournament is not completed. Nothing to undo.")

		self.delete_all_rebuys_and_eliminations(
			admin = user,
			tournament_id = tournament.id
		)

		tournament.started_at = None
		tournament.completed_at = None
		tournament.save(using=self._db)

		# Delete any Tournament results.
		TournamentPlayerResult.objects.delete_results_for_tournament(tournament_id)

		return tournament

	def delete_all_rebuys_and_eliminations(self, admin, tournament_id):
		tournament = self.get(pk=tournament_id)
		if tournament.admin != admin:
			raise ValidationError("You cannot update a Tournament if you're not the admin.")

		# Delete all eliminations
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(tournament_id)
		for elimination in eliminations:
			elimination.delete()

		# Delete all split eliminations
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(tournament_id)
		for split_elimination in split_eliminations:
			split_elimination.delete()

		# Delete all the rebuy data
		TournamentRebuy.objects.delete_tournament_rebuys(
			tournament_id = tournament.id
		)

		return tournament

	def start_tournament(self, user, tournament_id):
		tournament = self.get(pk=tournament_id)
		if tournament.admin != user:
			raise ValidationError("You cannot update a Tournament if you're not the admin.")
		if tournament.completed_at is not None:
			raise ValidationError("You can't start a Tournament that has already been completed.")

		tournament.started_at = timezone.now()
		tournament.save(using=self._db)
		return tournament

	def undo_start_tournament(self, user, tournament_id):
		tournament = self.get(pk=tournament_id)
		if tournament.admin != user:
			raise ValidationError("You cannot update a Tournament if you're not the admin.")
		if tournament.started_at is None:
			raise ValidationError("You can't deactivate a Tournament that has not been activated.")

		self.delete_all_rebuys_and_eliminations(
			admin = user,
			tournament_id = tournament.id
		)

		tournament.started_at = None
		tournament.save(using=self._db)

		# Delete any Tournament results.
		TournamentPlayerResult.objects.delete_results_for_tournament(tournament.id)

		return tournament

	def get_by_id(self, tournament_id):
		try:
			tournament = self.get(pk=tournament_id)
		except Tournament.DoesNotExist:
			tournament = None
		return tournament

	def get_by_user(self, user):
		tournaments = super().get_queryset().filter(admin=user).order_by("-started_at")
		return tournaments

	"""
	A Tournament is completable if every player except 1 has been completely eliminated.
	Meaning, all players have no remaining rebuys.

	If players remain, raise ValidationError.

	If only 1 player remains, return True.
	"""
	def is_completable(self, tournament_id):
		tournament = self.get_by_id(tournament_id)
		players = TournamentPlayer.objects.get_tournament_players(tournament_id)
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(tournament_id)
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(tournament_id)

		# sum buyins + rebuys
		rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
			tournament_id = tournament.id
		)
		total_buyins = len(rebuys) + len(players)

		# Find the number of eliminations
		total_eliminations = len(eliminations) + len(split_eliminations)

		# If every play is eliminated, the difference will be 1
		if total_buyins - total_eliminations != 1:
			raise ValidationError("Every player must be eliminated before completing a Tournament")
		return True

	"""
	Calculate the total value of a particular Tournament.
	Value cannot be calculated until a Tournament is complete.
	"""
	def calculate_tournament_value(self, tournament_id, num_rebuys):
		tournament = Tournament.objects.get_by_id(tournament_id)
		if tournament.completed_at == None:
			raise ValidationError("Tournament value cannot be calculated until a Tournament is complete.")
		buyin_amount = tournament.tournament_structure.buyin_amount
		# Sum the initial buyin amounts
		players = TournamentPlayer.objects.get_tournament_players(tournament_id)
		total_tournament_value = buyin_amount * len(players)
		# Add amount from rebuys
		total_tournament_value += buyin_amount * num_rebuys
		return round(Decimal(total_tournament_value), 2)

	"""
	Returns all the Tournaments this user has joined and is not an admin of.
	"""
	def get_joined_tournaments(self, user_id):
		tournament_players = TournamentPlayer.objects.get_all_tournament_players_by_user_id(user_id)
		tournaments = []
		for player in tournament_players:
			if player.tournament.admin != player.user:
				tournaments.append(player.tournament)
		return tournaments

"""
The states a tournament can be in.
INACTIVE: started_at == None and completed_at == None.
ACTIVE: started_at != None and completed_at == None.
COMPLETED: started_at != None and complated_at != None.
"""
class TournamentState(Enum):
	INACTIVE = 0
	ACTIVE = 1
	COMPLETED = 2

class Tournament(models.Model):
	title										= models.CharField(max_length=254, blank=False, null=False)
	admin										= models.ForeignKey(User, on_delete=models.CASCADE)
	tournament_structure		= models.ForeignKey(TournamentStructure, on_delete=models.CASCADE)

	# Set once the tournament has started.
	started_at							= models.DateTimeField(null=True, blank=True)

	# Set once the tournament has finished.
	completed_at						= models.DateTimeField(null=True, blank=True)

	objects = TournamentManager()

	def __str__(self):
		return self.title

	def get_state(self):
		if self.started_at == None and self.completed_at == None:
			return TournamentState.INACTIVE
		if self.started_at != None and self.completed_at == None:
			return TournamentState.ACTIVE 
		if self.started_at != None and self.completed_at != None:
			return TournamentState.COMPLETED

	def get_state_string(self):
		if self.get_state() == TournamentState.INACTIVE:
			return "INACTIVE"
		if self.get_state() == TournamentState.ACTIVE:
			return "ACTIVE"
		if self.get_state() == TournamentState.COMPLETED:
			return "COMPLETED"

class TournamentPlayerManager(models.Manager):

	def create_player_for_tournament(self, user_id, tournament_id):
		added_user = User.objects.get_by_id(user_id)
		tournament = Tournament.objects.get_by_id(tournament_id)

		if tournament.completed_at != None:
			raise ValidationError("You can't add players to a Tournment that is completed.")

		if tournament.started_at != None:
			raise ValidationError("You can't add players to a Tournment that is started.")

		player = self.get_tournament_player_by_user_id(added_user.id, tournament_id)

		# This player is already added to this tournament
		if player != None:
			raise ValidationError(f"{added_user.username} is already added to this tournament.")

		# This player has not been added to the tournament - add them.
		player = self.model(
			user=added_user,
			tournament=tournament
		)
		player.save(using=self._db)

		return player

	def remove_player_from_tournament(self, removed_by_user_id, removed_user_id, tournament_id):
		removed_by_user = User.objects.get_by_id(removed_by_user_id)
		removed_user = User.objects.get_by_id(removed_user_id)
		tournament = Tournament.objects.get_by_id(tournament_id)

		player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			user_id = removed_user.id,
			tournament_id = tournament_id
		)

		if tournament.admin == player.user:
			raise ValidationError("The admin cannot be removed from a Tournament.")

		if tournament.admin != removed_by_user and removed_user != removed_by_user:
			raise ValidationError("Only the admin can remove players.")

		if tournament.completed_at != None:
			raise ValidationError("You can't remove players from a Tournment that is completed.")

		if tournament.started_at != None:
			raise ValidationError("You can't remove players from a Tournment that is started.")

		if player.tournament != tournament:
			raise ValidationError(f"{player.user.username} is not part of this tournament.")

		player.delete()

		return removed_user


	# from tournament.models import TournamentPlayer
	# TournamentPlayer.objects.get_tournament_player(user.id, tourament.id)
	"""
	If the query returns multiple players, the tournament is corrupt - multiple instances of the same player
	have been added. Attempt to fix by removing them. The player will have to be re-added.

	If the query returns a single list item, return that player.

	If the query returns no results, return None.
	"""
	def get_tournament_player_by_user_id(self, user_id, tournament_id):
		user = User.objects.get_by_id(user_id)
		tournament = Tournament.objects.get_by_id(tournament_id)
		players = super().get_queryset().filter(user=user, tournament=tournament)
		if len(players) > 1:
			for player in players:
				player.delete()
			raise ValidationError("This tournament is corrupt. The same user has been added multiple times.  Attempting to fix...")
		
		if len(players) == 1:
			return players.first()
		else:
			return None

	"""
	Get all the TournamentPlayers for this tournament.
	"""
	def get_tournament_players(self, tournament_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		players = super().get_queryset().filter(tournament=tournament).order_by("user__username")
		return players

	"""
	Get all the TournamentPlayers for this user.
	"""
	def get_all_tournament_players_by_user_id(self, user_id):
		user = User.objects.get_by_id(user_id)
		return super().get_queryset().filter(user=user).select_related('tournament', 'user')

	"""
	Get TournamentPlayer by pk.
	"""
	def get_by_id(self, pk):
		try:
			player = self.get(id=pk)
			return player
		except TournamentPlayer.DoesNotExist:
			return None

	"""
	Return True is a player has been eliminated from a Tournament (and has no more rebuys).
	How?
	Compare the number of times they've been eliminated against the number of rebuys.
	Remember: If they've rebought once they will have one existing elimination.
	"""
	def is_player_eliminated(self, player_id):
		player = TournamentPlayer.objects.get_by_id(pk = player_id)
		eliminations = TournamentElimination.objects.get_eliminations_by_eliminatee(player_id = player.id)
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminatee(player_id = player.id)
		rebuys = TournamentRebuy.objects.get_rebuys_for_player(
			player = player
		)
		if len(eliminations) + len(split_eliminations) > len(rebuys):
			return True
		return False

"""
A player associated with specific tournament.
"""
class TournamentPlayer(models.Model):
	user							= models.ForeignKey(User, on_delete=models.CASCADE)	
	tournament				= models.ForeignKey(Tournament, on_delete=models.CASCADE)
	
	objects = TournamentPlayerManager()

	def __str__(self):
		return self.user.username

class TournamentEliminationManager(models.Manager):
	def get_eliminations_by_tournament(self, tournament_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		eliminations = []
		for player in players:
			eliminations_for_player = self.get_eliminations_by_eliminatee(
				player_id = player.id
			)
			for elimination in eliminations_for_player:
				eliminations.append(elimination)
		return eliminations

	def get_eliminations_by_eliminator(self, player_id):
		player = TournamentPlayer.objects.get_by_id(
			pk = player_id
		)
		# Eliminations where this player was the eliminator.
		eliminations = super().get_queryset().filter(
			eliminator=player,
		)
		return eliminations

	def get_eliminations_by_eliminatee(self, player_id):
		player = TournamentPlayer.objects.get_by_id(
			pk = player_id
		)
		# Eliminations where this player was the eliminatee.
		eliminations = super().get_queryset().filter(
			eliminatee=player,
		)
		return eliminations

	"""
	eliminator_id: id of the TournamentPlayer doing the eliminating.
	eliminatee_id: id of the TournamentPlayer being eliminated.
	"""
	def create_elimination(self, tournament_id, eliminator_id, eliminatee_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		eliminator_player = TournamentPlayer.objects.get_by_id(
			pk = eliminator_id
		)
		eliminatee_player = TournamentPlayer.objects.get_by_id(
			pk = eliminatee_id
		)

		if eliminator_player == None:
			raise ValidationError("Eliminator is not part of that Tournament.")

		if eliminatee_player == None:
			raise ValidationError("Eliminatee is not part of that Tournament.")

		# Verify the Tournament has started
		if tournament.get_state() != TournamentState.ACTIVE:
			raise ValidationError("You can only eliminate players if the Tournament is Active.")
		
		# Make sure a player isn't trying to eliminate themself.
		if eliminator_player == eliminatee_player:
			raise ValueError(f"{eliminator_player.user.username} can't eliminate themselves!")

		# Verify this is not the last player in the Tournament.
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		num_rebuys = 0
		if tournament.tournament_structure.allow_rebuys:
			tournament_rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
				tournament_id = tournament.id
			)
			num_rebuys += len(tournament_rebuys)
		total_buyins = num_rebuys + len(players)
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		if total_buyins <= (len(eliminations) + 1):
			raise ValidationError("You can't eliminate any more players. Complete the Tournament.")

		# Verify a multiple-eliminations aren't happening unless they've rebought.
		is_player_eliminated = TournamentPlayer.objects.is_player_eliminated(
			player_id = eliminatee_player.id
		)
		if is_player_eliminated:
			raise ValidationError(f"{eliminatee_player.user.username} has already been eliminated and has no more re-buys.")

		elimination = self.model(
			eliminator=eliminator_player,
			eliminatee=eliminatee_player
		)
		elimination.save(using=self._db)
		return elimination

	"""
	Creates an elimination for a backfilled tournament. Because its a backfill, the `is_backfill' flag is set to True.
	"""
	def create_backfill_elimination(self, tournament_id, eliminator_id, eliminatee_id):
		elimination = self.create_elimination(
			tournament_id = tournament_id,
			eliminator_id = eliminator_id,
			eliminatee_id = eliminatee_id,
		)
		elimination.is_backfill = True
		elimination.save()
		return elimination

"""
Tracks the data for eliminations. 

eliminator: Person who did the eliminating.

eliminatee: Person who got eliminated.

eliminated_at: When they were eliminated. This is used to calculate placements.

is_backfill: Is this elimination the result of a Tournament backfill? If it is, this TournamentElimination should be
exluded from any timeline related analytics.
"""
class TournamentElimination(models.Model):
	eliminator				= models.ForeignKey(TournamentPlayer, related_name="Eliminator", on_delete=models.CASCADE)	
	eliminatee				= models.ForeignKey(TournamentPlayer, related_name="Eliminatee", on_delete=models.CASCADE)
	eliminated_at			= models.DateTimeField(auto_now_add=True)
	is_backfill				= models.BooleanField(default=False)
	
	objects = TournamentEliminationManager()

	def __str__(self):
		return f"{self.eliminator.user.username} eliminated {self.eliminatee.user.username}."

	def get_tournament_title(self):
		return self.eliminator.tournament.title

class TournamentSplitEliminationManager(models.Manager):

	def get_split_eliminations_by_tournament(self, tournament_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		split_eliminations = []
		for player in players:
			split_eliminations_for_player = self.get_split_eliminations_by_eliminatee(
				player_id = player.id
			)
			for split_elimination in split_eliminations_for_player:
				split_eliminations.append(split_elimination)
		return split_eliminations

	def get_split_eliminations_by_eliminator(self, player_id):
		player = TournamentPlayer.objects.get_by_id(
			pk = player_id
		)
		# Get the split eliminations for the tournament
		split_eliminations = self.get_split_eliminations_by_tournament(
			tournament_id = player.tournament.id
		)
		# Find Split eliminations where this player was the eliminator.
		player_split_eliminations = []
		for split_elimination in split_eliminations:
			if player in split_elimination.eliminators.all():
				player_split_eliminations.append(split_elimination)
		return player_split_eliminations

	def get_split_eliminations_by_eliminatee(self, player_id):
		player = TournamentPlayer.objects.get_by_id(
			pk = player_id
		)
		# SplitEliminations where this player was the eliminatee.
		eliminations = super().get_queryset().filter(
			eliminatee=player,
		)
		return eliminations

	"""
	Creates a TournamentSplitElimination using the list of eliminators in 'eliminator_ids'.
	"""
	def create_split_elimination(self, tournament_id, eliminator_ids, eliminatee_id):
		tournament = Tournament.objects.get_by_id(tournament_id)

		# Get eliminated player
		eliminatee_player = TournamentPlayer.objects.get_by_id(
			pk = eliminatee_id
		)
		if eliminatee_player == None:
			raise ValidationError("Eliminatee is not part of that Tournament.")

		# Get the players doing the eliminating (splitting the elimination)
		eliminator_players = []
		for eliminator_id in eliminator_ids:
			eliminator_player = TournamentPlayer.objects.get_by_id(
				pk = eliminator_id
			)
			
			# Verify they are part of this tournament
			if eliminator_player == None:
				raise ValidationError("Eliminator is not part of that Tournament.")
			
			# Make sure a player isn't trying to eliminate themself.
			if eliminator_player == eliminatee_player:
				raise ValidationError(f"{eliminator_player.user.username} can't eliminate themselves!")

			# Make sure they didn't specify the same user twice
			if eliminator_player in eliminator_players:
				raise ValidationError(f"You specified {eliminator_player.user.username} more than once as an eliminator.")

			eliminator_players.append(eliminator_player)

		if len(eliminator_players) <= 1:
			raise ValidationError("You must choose more than one eliminator for a split elimination.")

		# Verify the Tournament has started
		if tournament.get_state() != TournamentState.ACTIVE:
			raise ValidationError("You can only eliminate players if the Tournament is Active.")

		# Verify this is not the last player in the Tournament.
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		num_rebuys = 0
		if tournament.tournament_structure.allow_rebuys:
			tournament_rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
				tournament_id = tournament.id
			)
			num_rebuys += len(tournament_rebuys)
		total_buyins = num_rebuys + len(players)
		eliminations = TournamentElimination.objects.get_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		if total_buyins <= (len(eliminations) + 1):
			raise ValidationError("You can't eliminate any more players. Complete the Tournament.")

		# Verify a multiple-eliminations aren't happening unless they've rebought.
		is_player_eliminated = TournamentPlayer.objects.is_player_eliminated(
			player_id = eliminatee_player.id
		)
		if is_player_eliminated:
			raise ValidationError(f"{eliminatee_player.user.username} has already been eliminated and has no more re-buys.")

		split_elimination = self.model(
			eliminatee = eliminatee_player
		)
		split_elimination.save(using=self._db)
		split_elimination.eliminators.add(*eliminator_players)
		split_elimination.save()
		return split_elimination

	"""
	Creates a TouramentSplitElimination for a backfilled tournament. Because its a backfill, the `is_backfill' flag is set to True.
	"""
	def create_backfill_split_elimination(self, tournament_id, eliminators, eliminatee):
		split_elimination = self.create_split_elimination(
			tournament_id = tournament_id,
			eliminator_ids = [eliminator.id for eliminator in eliminators],
			eliminatee_id = eliminatee.id,
		)
		split_elimination.is_backfill = True
		split_elimination.save()
		return split_elimination

class TournamentSplitElimination(models.Model):
	eliminators				= models.ManyToManyField(TournamentPlayer, related_name="Eliminators_for_split")
	eliminatee				= models.ForeignKey(TournamentPlayer, related_name="Eliminatee_for_split", on_delete=models.CASCADE)
	eliminated_at			= models.DateTimeField(auto_now_add=True)
	is_backfill				= models.BooleanField(default=False)
	
	objects = TournamentSplitEliminationManager()

	def __str__(self):
		return f"Split elimination of {self.eliminatee.user.username} by {self.get_eliminators()}."

	def get_eliminators(self):
		eliminators = ""
		for i, eliminator in enumerate(self.eliminators.all()):
			eliminators += f"{eliminator.user.username}"
			if i < len(self.eliminators.all()) - 1:
				eliminators += ", "
		return eliminators

	def get_tournament_title(self):
		return self.eliminatee.tournament.title

class TournamentRebuyManager(models.Manager):

	def rebuy(self, tournament_id, player_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		player = TournamentPlayer.objects.get_by_id(player_id)

		# Verify this player is in this tournament
		if player == None or player.tournament != tournament:
			raise ValidationError("That player is not part of this tournament.")

		# Verify the tournament allows rebuys
		if not tournament.tournament_structure.allow_rebuys:
			raise ValidationError("This tournament does not allow rebuys. Update the Tournament Structure.")

		# Verify Tournament is active
		if tournament.get_state() != TournamentState.ACTIVE:
			raise ValidationError("Cannot rebuy if Tournament is not active.")

		# Verify they're out of rebuys.
		num_eliminations = len(
			TournamentElimination.objects.get_eliminations_by_eliminatee(
				player_id = player.id
			)
		)
		num_eliminations += len(
			TournamentSplitElimination.objects.get_split_eliminations_by_eliminatee(
				player_id = player.id
			)
		)
		rebuys = self.get_rebuys_for_player(
			player = player
		)
		if num_eliminations <= len(rebuys):
			raise ValidationError(
				f"{player.user.username} has not been eliminated. Eliminate them before adding another rebuy."
			)
		tournament_rebuy = self.model(
			player = player
		)
		tournament_rebuy.save(using=self._db)
		return tournament_rebuy

	"""
	Similar to 'rebuy', but because this is used in a "tournament backfill" context, some of the validation is ignored.
	Basically rebuys are added without determining if one is actually needed. Also the 'is_backfill' flag is set to true.
	"""
	def backfill_rebuy(self, tournament_id, player_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		player = TournamentPlayer.objects.get_by_id(player_id)

		# Verify this player is in this tournament
		if player == None or player.tournament != tournament:
			raise ValidationError("That player is not part of this tournament.")

		# Verify the tournament allows rebuys
		if not tournament.tournament_structure.allow_rebuys:
			raise ValidationError("This tournament does not allow rebuys. Update the Tournament Structure.")

		tournament_rebuy = self.model(
			player = player,
			is_backfill = True
		)
		tournament_rebuy.save(using=self._db)
		return tournament_rebuy

	def get_rebuys_for_player(self, player):
		rebuys = super().get_queryset().filter(
			player = player
		)
		return rebuys

	def get_rebuys_for_tournament(self, tournament_id):
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament_id
		)
		rebuys = []
		for player in players:
			rebuys_for_player = self.get_rebuys_for_player(
				player = player
			)
			for rebuy in rebuys_for_player:
				rebuys.append(rebuy)
		return rebuys

	"""
	Delete all the rebuy data for a Tournament.
	"""
	def delete_tournament_rebuys(self, tournament_id):
		rebuys = self.get_rebuys_for_tournament(tournament_id)
		for rebuy in rebuys:
			rebuy.delete()

"""
Denotes a "Rebuy" event for a particular TournamentPlayer.

is_backfill: Is this Rebuy the result of a Tournament backfill? If it is, this TournamentRebuy should be
exluded from any timeline related analytics.
"""
class TournamentRebuy(models.Model):
	player					= models.ForeignKey(TournamentPlayer, related_name="player", on_delete=models.CASCADE)	
	timestamp				= models.DateTimeField(auto_now_add=True)
	is_backfill				= models.BooleanField(default=False)
	
	objects = TournamentRebuyManager()

	def __str__(self):
		return f"{self.player.user.username} rebought at {self.timestamp}."

	def get_tournament_title(self):
		return self.player.tournament.title

	def get_player_username(self):
		return self.player.user.username


class TournamentPlayerResultManager(models.Manager):

	def get_results_for_tournament(self, tournament_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		return super().get_queryset().filter(tournament=tournament)

	def get_results_for_user_by_tournament(self, user_id, tournament_id):
		player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			tournament_id = tournament_id,
			user_id = user_id,
		)
		tournament = Tournament.objects.get_by_id(tournament_id)
		return super().get_queryset().filter(tournament=tournament, player=player)

	def delete_results_for_tournament(self, tournament_id):
		results = self.get_results_for_tournament(tournament_id)
		for result in results:
			result.delete()

	"""
	Build TournamentPlayerResult's for each player in the Tournament. This is different from
	build_results_for_tournament because this is used for Tournament backfills. In otherwords,
	Tournaments that were completed at some point in the past and the admin is just now filling
	in the data.

	See complete_tournament_for_backfill for information about the args.
	"""
	def build_results_for_backfilled_tournament(self, tournament_id, player_tournament_placements):
		tournament = Tournament.objects.get_by_id(tournament_id)
		if tournament.completed_at == None:
			raise ValidationError("You cannot build Tournament results until the Tournament is complete.")

		# First, make sure all these players are part of this tournament.
		for player_placement in player_tournament_placements:
			player = TournamentPlayer.objects.get_by_id(player_placement.player_id)
			if player.tournament != tournament:
				raise ValidationError(f"{player.user.username} is not part of tournament: {tournament.title}.")
		
		# Build the results
		results = []

		# First build the results for the players who placed
		for player_placement in player_tournament_placements:
			if player_placement.placement != DID_NOT_PLACE_VALUE:
				# Build result using forced placement
				player = TournamentPlayer.objects.get_by_id(player_placement.player_id)
				placement = player_placement.placement
				result = self.create_tournament_player_result(
					user_id = player.user.id,
					tournament_id = tournament.id,
					placement = placement,
					is_backfill = True
				)
				results.append(result)
			else:
				# Build result using placement = DID_NOT_PLACE_VALUE
				player = TournamentPlayer.objects.get_by_id(player_placement.player_id)
				result = self.create_tournament_player_result(
					user_id = player.user.id,
					tournament_id = tournament.id,
					placement = DID_NOT_PLACE_VALUE,
					is_backfill = True
				)
				results.append(result)

		return results


	def build_results_for_tournament(self, tournament_id):
		tournament = Tournament.objects.get_by_id(tournament_id)
		if tournament.completed_at == None:
			raise ValidationError("You cannot build Tournament results until the Tournament is complete.")
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament_id
		)
		results = []
		for player in players:
			placement = self.determine_placement(user_id=player.user.id, tournament_id=tournament_id)
			result = self.create_tournament_player_result(
				user_id = player.user.id,
				placement = placement,
				tournament_id = tournament_id,
				is_backfill = False
			)
			results.append(result)
		return results

	"""
	Determine what a player placed in a tournament.
	Note: This is -1 indexed! So whoever came first will have placement = 0
	"""
	def determine_placement(self, user_id, tournament_id):
		player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			user_id = user_id,
			tournament_id = tournament_id
		)
		tournament = Tournament.objects.get_by_id(tournament_id)

		# Verify the tournament is completed
		if tournament.completed_at == None:
			raise ValidationError("Cannot determine placement until tourment is completed.")

		# -- Determine placement --
		placement = None
		# First, figure out if this player came first. They came first if:
		# (1) They did not get eliminated at all
		# (2) OR the number of rebuys exceeds the number of times they were eliminated.
		player_eliminations = TournamentElimination.objects.get_eliminations_by_eliminatee(
			player_id = player.id
		)
		player_split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminatee(
			player_id = player.id
		)
		rebuys = TournamentRebuy.objects.get_rebuys_for_player(
			player = player
		)
		if len(player_eliminations) == 0 and len(player_split_eliminations) == 0:
			# They were never eliminated
			placement = 0
		if len(player_eliminations) + len(player_split_eliminations) < len(rebuys) + 1:
			# The Tournament completed and they still had a rebuy remaining
			placement = 0
		if placement == None:
			# If they didn't come first, figure out what they placed.
			# This queryset is ordered from (last elim) -> (first elim)
			all_eliminations = TournamentElimination.objects.get_eliminations_by_tournament(tournament_id)
			# {player_id: (eliminated_at, elimination_id)} - id used as tiebreaker for same-timestamp eliminations
			elimations_dict = {}
			for elimination in all_eliminations:
				entry = (elimination.eliminated_at, elimination.id)
				if elimination.eliminatee.id not in elimations_dict.keys():
					elimations_dict[elimination.eliminatee.id] = entry
				elif entry > elimations_dict[elimination.eliminatee.id]:
					# Only replace the value in the dictionary if the timestamp is newer (more recent)
					elimations_dict[elimination.eliminatee.id] = entry
			tournament_split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(
				tournament_id = tournament.id
			)
			for split_elimination in tournament_split_eliminations:
				entry = (split_elimination.eliminated_at, split_elimination.id)
				if split_elimination.eliminatee.id not in elimations_dict.keys():
					elimations_dict[split_elimination.eliminatee.id] = entry
				elif entry > elimations_dict[split_elimination.eliminatee.id]:
					# Only replace the value in the dictionary if the timestamp is newer (more recent)
					elimations_dict[split_elimination.eliminatee.id] = entry

			# Loop through the sorted list. Whatever index this player is in, thats what they placed
			sorted_reversed_list = [k for k, v in sorted(elimations_dict.items(), key=lambda p: p[1], reverse=True)]
			for i,player_id in enumerate(sorted_reversed_list):
				if player_id == player.id:
					placement = i + 1 # add 1 b/c person in first won't show up in eliminations lists
					break
		return placement

	"""
	Determine the amount this player made from where they placed in the Tournament.
	This does not include bounties. This is strictly earnings from how they placed.
	"""
	def determine_placement_earnings(self, tournament, placement):
		placement_earnings = 0
		tournament_id = tournament.id
		players = TournamentPlayer.objects.get_tournament_players(tournament_id)
		rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(
			tournament_id = tournament_id,
		)
		num_rebuys = len(rebuys)
		total_tournament_value = Tournament.objects.calculate_tournament_value(
			tournament_id = tournament_id, 
			num_rebuys = num_rebuys
		)
		bounty_amount = tournament.tournament_structure.bounty_amount
		if bounty_amount != None:
			# subtract the bounties from total value
			total_tournament_value -= Decimal(len(players) * bounty_amount)
			total_tournament_value -= Decimal(num_rebuys * bounty_amount)
		# Determine the % paid to this users placement
		for i,pct in enumerate(tournament.tournament_structure.payout_percentages):
			if i == placement:
				placement_earnings = Decimal(float(pct) / float(100.00) * float(total_tournament_value))
		return round(placement_earnings, 2)

	def create_tournament_player_result(self, user_id, tournament_id, placement, is_backfill):
		player = TournamentPlayer.objects.get_tournament_player_by_user_id(
			user_id = user_id,
			tournament_id = tournament_id
		)
		# Make sure a result doesn't already exist.
		results = TournamentPlayerResult.objects.get_results_for_user_by_tournament(
			user_id = user_id,
			tournament_id = tournament_id
		)
		# If any exist, delete them.
		for result in results:
			result.delete()

		tournament = Tournament.objects.get_by_id(tournament_id)

		# -- Get eliminations --
		eliminations = TournamentElimination.objects.get_eliminations_by_eliminator(
			player_id = player.id
		)
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
			player_id = player.id
		)

		# Determine what fraction comes from split eliminations
		split_eliminations_count = 0.00
		for split_elimination in split_eliminations:
			eliminators = split_elimination.eliminators.all()
			split_eliminations_count += round(1.00 / len(eliminators), 2)

		# -- Get bounty earnings (if this is a bounty tournament). Otherwise 0.00. --
		bounty_earnings = None
		if tournament.tournament_structure.bounty_amount != None:
			bounty_earnings = round((Decimal(len(eliminations)) + Decimal(split_eliminations_count)) * Decimal(tournament.tournament_structure.bounty_amount), 2)
		else:
			bounty_earnings = round(Decimal(0.00), 2)

		# -- Get rebuys --
		rebuys = TournamentRebuy.objects.get_rebuys_for_player(
			player = player
		)

		# -- Calculate 'investment' --
		buyin_amount = tournament.tournament_structure.buyin_amount
		investment = buyin_amount + (len(rebuys) * buyin_amount)

		# -- Calculate placement earnings --
		placement_earnings = 0
		if placement != DID_NOT_PLACE_VALUE:
			placement_earnings = self.determine_placement_earnings(
				tournament = tournament,
				placement = placement
			)

		# -- Calculate 'gross_earnings' --
		# Sum of placement_earnings + bounty_earnings
		gross_earnings = placement_earnings + bounty_earnings

		# -- Calculate 'net_earnings' --
		# Difference of gross_earnings - investment
		net_earnings = gross_earnings - investment

		result = self.model(
			player = player,
			tournament = tournament,
			investment = investment,
			placement = placement,
			placement_earnings = placement_earnings,
			bounty_earnings = bounty_earnings,
			gross_earnings = gross_earnings,
			net_earnings = net_earnings,
			is_backfill = is_backfill
		)
		result.save(using=self._db)
		return result

	def get_results_by_player(self, player):
		return super().get_queryset().filter(player=player)

class TournamentPlayerResult(models.Model):
	player			 						= models.ForeignKey(TournamentPlayer, on_delete=models.CASCADE)
	tournament							= models.ForeignKey(Tournament, on_delete=models.CASCADE)

	# Total amount invested into this tournament. Initial buyin + rebuys
	investment							= models.DecimalField(max_digits=9, decimal_places=2, blank=False, null=False)

	# Placement in the tournament (1st, 2nd, etc). Nullable for backfill Tournaments where it's possible only the paid 
	# placements show.
	placement								= models.IntegerField(blank=True, null=True)

	# Earnings strictle from placement
	placement_earnings			= models.DecimalField(max_digits=9, decimal_places=2, blank=False, null=False)

	# Earnings from eliminations (Defaults to 0.00 if not a bounty tournament)
	bounty_earnings					= models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)

	# bounty_earnings + placement_earnings
	gross_earnings					= models.DecimalField(max_digits=9, decimal_places=2, blank=False, null=False)

	# gross_earnings - investment
	net_earnings						= models.DecimalField(max_digits=9, decimal_places=2, blank=False, null=False)

	# Were these results produced from a Tournament backfill?
	is_backfill							= models.BooleanField(default=False)

	objects = TournamentPlayerResultManager()

	def __str__(self):
		return f"TournamentPlayerResult data for {self.player.user.username}"

	def placement_string(self):
		return build_placement_string(self.placement)





























