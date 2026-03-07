import json
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone

from tournament.forms import CreateTournamentForm, CreateTournamentStructureForm, EditTournamentForm
from tournament.models import (
	Tournament,
	TournamentStructure,
	TournamentState,
	TournamentPlayer,
	TournamentElimination,
	TournamentPlayerResult,
	TournamentRebuy,
	TournamentSplitElimination
)
from tournament.util import (
	PlayerTournamentData,
	payout_positions,
	PlayerEliminationsData,
	build_placement_string,
	PlayerTournamentPlacement,
	DID_NOT_PLACE_VALUE,
	build_elimination_event,
	build_rebuy_event,
	build_completion_event,
	build_in_progress_event,
	build_split_elimination_event,
	build_split_eliminations_data,
	build_player_eliminations_data_from_eliminations,
	build_player_eliminations_summary_data_from_eliminations,
	get_tournament_started_at
)
from user.models import User

@login_required
def tournament_create_view(request, *args, **kwargs):
	context = {}
	if request.method == 'POST':
		form = CreateTournamentForm(request.POST, user=request.user)
		if form.is_valid():
			tournament = Tournament.objects.create_tournament(
				user = request.user,
				title = form.cleaned_data['title'],
				tournament_structure = form.cleaned_data['tournament_structure'],
			)
			if tournament is not None:
				messages.success(request, "Tournament Created!")

			redirect_url = request.GET.get('next')
			if redirect_url is not None:
				return redirect(redirect_url)
			return redirect("tournament:tournament_view", pk=tournament.id)
	else:
		form = CreateTournamentForm(user=request.user)

	context['form'] = form
	return render(request=request, template_name='tournament/create_tournament.html', context=context)

@login_required
def tournament_list_view(request, *args, **kwargs):
	context = {}
	try:
		# The tournament where they are the admin
		context['tournaments'] = Tournament.objects.get_by_user(
			user=request.user
		).order_by("-started_at")

		# The tournaments they have joined (with accepted invite) but are not admin
		joined_tournaments = Tournament.objects.get_joined_tournaments(
			user_id = request.user.id
		)
		joined_tournaments.sort(
			key=get_tournament_started_at,
			reverse=True
		)

		context['joined_tournaments'] = joined_tournaments

	except Exception as e:
		messages.error(request, e.args[0])
	return render(request=request, template_name="tournament/tournament_list.html", context=context)

@login_required
def tournament_view(request, *args, **kwargs):
	tournament = Tournament.objects.get_by_id(kwargs['pk'])
	return render_tournament_view(request, tournament.id)

@login_required
def start_tournament(request, *args, **kwargs):
	tournament_id = kwargs['pk']
	try:
		user = request.user
		
		# Verify the admin is performing this action
		verify_admin(
			user = user,
			tournament_id = tournament_id,
			error_message = "You are not the admin of this Tournament."
		)

		tournament = Tournament.objects.start_tournament(user=user, tournament_id=tournament_id)
	except Exception as e:
		messages.error(request, e.args[0])
		return redirect(request.META['HTTP_REFERER'])
	return redirect("tournament:tournament_view", pk=tournament_id)

@login_required
def complete_tournament(request, *args, **kwargs):
	tournament_id = kwargs['pk']
	try:
		user = request.user
		
		# Verify the admin is performing this action
		verify_admin(
			user = user,
			tournament_id = tournament_id,
			error_message = "You are not the admin of this Tournament."
		)

		tournament = Tournament.objects.complete_tournament(user, tournament_id)
	except Exception as e:
		messages.error(request, e.args[0])
		return redirect(request.META['HTTP_REFERER'])
	return redirect("tournament:tournament_view", pk=tournament_id)

@login_required
def undo_completed_at(request, *args, **kwargs):
	tournament_id = kwargs['pk']
	try:
		user = request.user

		# Verify the admin is performing this action
		verify_admin(
			user = user,
			tournament_id = tournament_id,
			error_message = "You are not the admin of this Tournament."
		)

		Tournament.objects.undo_complete_tournament(
			user = user,
			tournament_id = tournament_id
		)
	except Exception as e:
		messages.error(request, e.args[0])
		return redirect(request.META['HTTP_REFERER'])
	return redirect("tournament:tournament_view", pk=tournament_id)

@login_required
def undo_started_at(request, *args, **kwargs):
	tournament_id = kwargs['pk']
	try:
		user = request.user
		# Verify the admin is performing this action
		verify_admin(
			user = user,
			tournament_id = tournament_id,
			error_message = "You are not the admin of this Tournament."
		)

		Tournament.objects.undo_start_tournament(
			user = user,
			tournament_id = tournament_id
		)
	except Exception as e:
		messages.error(request, e.args[0])
		return redirect(request.META['HTTP_REFERER'])
	return redirect("tournament:tournament_view", pk=tournament_id)

"""
Remove a player from a tournament.
HTMX request for tournament_view
"""
@login_required
def remove_player_from_tournament(request, *args, **kwargs):
	user = request.user
	user_id = kwargs['user_id']
	tournament_id = kwargs['tournament_id']
	try:
		removed_user = TournamentPlayer.objects.remove_player_from_tournament(
			removed_by_user_id= user.id,
			removed_user_id=user_id,
			tournament_id=tournament_id
		)
		messages.success(request, f"Removed {removed_user.username}.")
	except Exception as e:
		messages.error(request, e.args[0])
	return redirect(request.META['HTTP_REFERER'])

"""
Add a player directly to a tournament.
HTMX request for tournament_view
"""
@login_required
def add_player_to_tournament(request, *args, **kwargs):
	try:
		user = request.user
		player_id = kwargs['player_id']
		tournament_id = kwargs['tournament_id']

		verify_admin(
			user = user,
			tournament_id = tournament_id,
			error_message = "Only the admin can add players."
		)

		TournamentPlayer.objects.create_player_for_tournament(
			user_id = player_id,
			tournament_id = tournament_id
		)
		return render_tournament_view(request, tournament_id)
	except Exception as e:
		messages.error(request, e.args[0])
	return render_tournament_view(request, tournament_id)

"""
Eliminate a player from a tournament.
Returns a generic HttpResponse with a status code representing whether it was successful or not.
If it was not successful, the user will be redirected to an error page.
"""
@login_required
def eliminate_player_from_tournament(request, *args, **kwargs):
	user = request.user
	try:
		# Who is doing the eliminating
		eliminator_id = kwargs['eliminator_id']

		# Who is being eliminated
		eliminatee_id = kwargs['eliminatee_id']

		# Tournament id where this is taking place
		tournament_id = kwargs['tournament_id']

		# Verify the admin is the one eliminating
		verify_admin(
			user = request.user,
			tournament_id = tournament_id,
			error_message = "Only the admin can eliminate players."
		)

		# All the validation is performed in the create_elimination function.
		elimination = TournamentElimination.objects.create_elimination(
			tournament_id = tournament_id,
			eliminator_id = eliminator_id,
			eliminatee_id = eliminatee_id
		)
	except Exception as e:
		messages.error(request, e.args[0])
		return HttpResponse(content_type='application/json', status=400)
	return HttpResponse(content_type='application/json', status=200)

"""
Perform a split elimination.
"""
@login_required
def split_eliminate_player_from_tournament(request, *args, **kwargs):
	user = request.user
	try:
		# Who is doing the eliminating (this is a comma separated list of player ids)
		eliminator_ids = kwargs['eliminator_ids']

		# Who is being eliminated
		eliminatee_id = kwargs['eliminatee_id']

		# Tournament id where this is taking place
		tournament_id = kwargs['tournament_id']

		eliminator_id_integers = []
		for player_id in eliminator_ids.split(","):
			eliminator_id_integers.append(int(player_id))

		# Verify the admin is the one eliminating
		verify_admin(
			user = request.user,
			tournament_id = tournament_id,
			error_message = "Only the admin can eliminate players."
		)

		# All the validation is performed in the create_split_elimination function.
		elimination = TournamentSplitElimination.objects.create_split_elimination(
			tournament_id = tournament_id,
			eliminator_ids = eliminator_id_integers,
			eliminatee_id = eliminatee_id
		)
	except Exception as e:
		messages.error(request, e.args[0])
		return HttpResponse(content_type='application/json', status=400)
	return HttpResponse(content_type='application/json', status=200)	

"""
Rebuy for an eliminated player.
Returns a generic HttpResponse with a status code representing whether it was successful or not.
If it was not successful, the user will be redirected to an error page.
"""
@login_required
def rebuy_player_in_tournament(request, *args, **kwargs):
	try:
		# Who is rebuying
		player_id = kwargs['player_id']

		# Tournament id where this is taking place
		tournament_id = kwargs['tournament_id']

		# Verify the tournament admin is executing the rebuy
		verify_admin(
			user = request.user,
			tournament_id = tournament_id,
			error_message = "Only the admin can execute a rebuy."
		)

		player = TournamentPlayer.objects.get_by_id(player_id)

		# All the validation is performed in the rebuy function.
		TournamentRebuy.objects.rebuy(
			tournament_id = tournament_id,
			player_id = player.id
		)
	except Exception as e:
		messages.error(request, e.args[0])
		return HttpResponse(content_type='application/json', status=400)
	return HttpResponse(content_type='application/json', status=200)

"""
Common function shared between tournament_view and htmx requests used in that view.
"""
def render_tournament_view(request, tournament_id):
	context = {}
	tournament = Tournament.objects.get_by_id(tournament_id)
	context['tournament'] = tournament
	context['tournament_state'] = tournament.get_state()

	# Get all the players that have joined the Tournament. They are a TournamentPlayer
	players = TournamentPlayer.objects.get_tournament_players(tournament.id)
	context['players'] = players

	# Search for users with htmx
	search = request.GET.get("search")
	if search != None and search != "":
		users = User.objects.all().filter(username__icontains=search)
		# Exclude the admin
		users = users.exclude(email__iexact=request.user.email)
		# Exclude users who are already players
		for player in players:
			users = users.exclude(email__iexact=player.user.email)
		context['users'] = users
		context['search'] = search

	context['is_bounty_tournament'] = tournament.tournament_structure.bounty_amount != None
	context['allow_rebuys'] = tournament.tournament_structure.allow_rebuys
	context['player_tournament_data'] = get_player_tournament_data(tournament_id)

	# If it's completed, determine the results
	results = None
	if tournament.get_state() == TournamentState.COMPLETED:
		results = TournamentPlayerResult.objects.get_results_for_tournament(
			tournament_id = tournament.id
		)
		context['results'] = results.order_by("placement")
		context['payout_positions'] = payout_positions(tournament.tournament_structure.payout_percentages)
		
		eliminations_summary_data = []
		eliminations_data = []
		for result in results:
			# Determine who they eliminated in this tournament.
			eliminations = TournamentElimination.objects.get_eliminations_by_eliminator(
				player_id = result.player.id
			)
			split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
				player_id = result.player.id
			)
			# --- Build PlayerEliminationsSummaryData for each player ---
			if len(eliminations) > 0 or len(split_eliminations) > 0:
				data = build_player_eliminations_summary_data_from_eliminations(
					eliminator = result.player,
					eliminations = eliminations,
					split_eliminations = split_eliminations
				)
				if data != None:
					eliminations_summary_data.append(data)

			# --- Build PlayerEliminationsData for each player ---
			if len(eliminations) > 0:
				data = build_player_eliminations_data_from_eliminations(
					eliminator = result.player,
					eliminations = eliminations,
				)
				if data != None:
					eliminations_data.append(data)

		# --- Build SplitEliminationsData for the tournament ---
		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(
			tournament_id = tournament.id
		)
		if len(split_eliminations) > 0:
			data = build_split_eliminations_data(
				split_eliminations = split_eliminations
			)
			if data != None:
				context['split_eliminations_data'] = data

		context['eliminations_summary_data'] = eliminations_summary_data
		context['eliminations_data'] = eliminations_data


	# --- Build timeline ---
	# Note: Only build a timeline if this is not a backfill tournament and the state is either ACTIVE or COMPLETED.
	eliminations = TournamentElimination.objects.get_eliminations_by_tournament(tournament.id)
	split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_tournament(tournament.id)
	events = []
	if (len(eliminations) > 0 and not eliminations[0].is_backfill) or (len(split_eliminations) > 0 and not split_eliminations[0].is_backfill):
		if tournament.get_state() == TournamentState.ACTIVE or tournament.get_state() == TournamentState.COMPLETED:
			# Get all the TournamentElimination's and TournamentRebuyEvent's and add to the context as an event.
			# Sort on timestamp. This is for building the timeline.
			# Eliminations
			for elimination in eliminations:
				event = build_elimination_event(elimination)
				events.append(event)
			# Rebuys
			rebuys = TournamentRebuy.objects.get_rebuys_for_tournament(tournament.id)
			for rebuy in rebuys:
				event = build_rebuy_event(rebuy)
				events.append(event)

			# If the tournament is completed, build the completion event.
			if results != None:
				winning_player_result = results.filter(placement=0)[0]
				event = build_completion_event(
					completed_at = tournament.completed_at,
					winning_player = winning_player_result.player
				)
				events.append(event)
			else:
				# if it's not completed, add a "TournamentInProgressEvent"
				event = build_in_progress_event(
					started_at = tournament.started_at
				)
				events.append(event)
	
	# SPLIT ELIMINATIONS for timeline
	if len(split_eliminations) > 0:
		if not split_eliminations[0].is_backfill:
			if tournament.get_state() == TournamentState.ACTIVE or tournament.get_state() == TournamentState.COMPLETED:
				for split_elimination in split_eliminations:
					event = build_split_elimination_event(split_elimination)
					events.append(event)

	if len(events) > 0:
		events.sort(key=lambda event: event.timestamp)
		context['events'] = events

	return render(request=request, template_name="tournament/tournament_view.html", context=context)


"""
Retrieve a TournamentStructure and serialize to Json.
TODO("dont need this?")
"""
@login_required
def get_tournament_structure(request):
	structure_id = request.GET['tournament_structure_id']
	if structure_id is not None:
		structure = TournamentStructure.objects.get_by_id(structure_id)
		try:
			return JsonResponse({"structure": f"{structure.buildJson()}"}, status=200)
		except Exception as e:
			return JsonResponse({"error": "Serialization error."}, status=400)
	else:
		return JsonResponse({"error": "Unable to retrieve tournament structure details."}, status=400)

@login_required
def tournament_structure_create_view(request, *args, **kwargs):
	context = {}
	if request.method == 'POST':
		form = CreateTournamentStructureForm(request.POST)
		if form.is_valid():
			payout_percentages = [int(int_percentage) for int_percentage in (form.cleaned_data['hidden_payout_structure'].split(","))]
			tournament_structure = TournamentStructure.objects.create_tournament_struture(
				user = request.user,
				title = form.cleaned_data['title'],
				allow_rebuys = form.cleaned_data['allow_rebuys'],
				buyin_amount = form.cleaned_data['buyin_amount'],
				bounty_amount = form.cleaned_data['bounty_amount'],
				payout_percentages = payout_percentages,
			)

			messages.success(request, "Created new Tournament Structure")

			redirect_url = request.GET.get('next')
			if redirect_url is not None:
				# If they were editing a tournament, make sure to select the new tournament structure when they return.
				if "/tournament/tournament_edit/" in redirect_url:
					redirect_url = f"{redirect_url}?selected_structure_pk={tournament_structure.pk}"
				return redirect(redirect_url)
			form = CreateTournamentStructureForm()

	else:
		form = CreateTournamentStructureForm()

	context['form'] = form
	return render(request=request, template_name='tournament/create_tournament_structure.html', context=context)

@login_required
def tournament_edit_view(request, *args, **kwargs):
	context = {}
	tournament = Tournament.objects.get_by_id(kwargs['pk'])
	state = tournament.get_state()
	if state == TournamentState.ACTIVE or state == TournamentState.ACTIVE:
		messages.error(request, "You can't edit a Tournament that is completed or active.")
		return redirect("tournament:tournament_view", pk=tournament.id)
	if request.method == 'POST':
		form = EditTournamentForm(request.POST, user=request.user, tournament_pk=tournament.id)
		if form.is_valid():
			tournament.tournament_structure = form.cleaned_data['tournament_structure']
			tournament.title = form.cleaned_data['title']
			tournament.save()

			messages.success(request, "Tournament Updated!")

			return redirect("tournament:tournament_view", pk=tournament.id)
	else:
		form = EditTournamentForm(user=request.user, tournament_pk=tournament.id)
	context['form'] = form
	context['tournament_pk'] = tournament.id
	initial_selected_structure = tournament.tournament_structure
	seleted_structure_pk_from_kwargs = None

	# Check if we are returning from creating a new structure. If we are, select that structure.
	try:
		seleted_structure_pk_from_kwargs = request.GET.get('selected_structure_pk')
	except Exception as e:
		pass
	if seleted_structure_pk_from_kwargs != None:
		initial_selected_structure = TournamentStructure.objects.get_by_id(seleted_structure_pk_from_kwargs)
	context['initial_selected_structure'] = initial_selected_structure

	# Add all TournamentStructure's for this user so we can populate a table when one is selected.
	context['tournament_structures'] = TournamentStructure.objects.get_structures_by_user(request.user)
	return render(request=request, template_name='tournament/tournament_edit_view.html', context=context)

@login_required
def tournament_admin_view(request, *args, **kwargs):
	tournament = Tournament.objects.get_by_id(kwargs['pk'])
	return render_tournament_admin_view(request, tournament.id)



"""
Convenience function for the htmx functions that happen on tournament_admin_view.
"""
@login_required
def render_tournament_admin_view(request, tournament_id):
	context = {}
	tournament = Tournament.objects.get_by_id(tournament_id)
	if tournament.get_state() != TournamentState.ACTIVE:
		messages.error(request, "Admin view is not available until Tournament is activated.")
		return redirect("tournament:tournament_view", pk=tournament.id)
	if request.user != tournament.admin:
		messages.error(request, "You are not the Tournament admin.")
		return redirect("tournament:tournament_view", pk=tournament.id)

	context['tournament_state'] = tournament.get_state()
	context['tournament'] = tournament
	context['is_bounty_tournament'] = tournament.tournament_structure.bounty_amount != None
	context['allow_rebuys'] = tournament.tournament_structure.allow_rebuys
	context['player_tournament_data'] = get_player_tournament_data(tournament_id)
	return render(request=request, template_name="tournament/tournament_admin_view.html", context=context)

"""
Builds a list of PlayerTournamentData.
"""
def get_player_tournament_data(tournament_id):
	player_tournament_data = []
	players = TournamentPlayer.objects.get_tournament_players(tournament_id)
	for player in players:
		eliminations = TournamentElimination.objects.get_eliminations_by_eliminator(
			player_id = player.id
		)
		is_eliminated = TournamentPlayer.objects.is_player_eliminated(
			player_id = player.id
		)
		rebuys = TournamentRebuy.objects.get_rebuys_for_player(
			player = player
		)

		split_eliminations = TournamentSplitElimination.objects.get_split_eliminations_by_eliminator(
			player_id = player.id
		)

		# Initialize bounties to the len(eliminations), then add the fractional quantities from split eliminations.
		bounties = len(eliminations)
		for split_elimination in split_eliminations:
			bounty_fraction = round(Decimal(1.0 / len(split_elimination.eliminators.all())), 2)
			bounties += bounty_fraction

		data = PlayerTournamentData(
					player_id = player.id,
					username = player.user.username,
					rebuys = len(rebuys),
					bounties = bounties,
					is_eliminated = is_eliminated
				)
		player_tournament_data.append(data)
	return player_tournament_data

"""
Convenience function for verifying the admin is the one trying to do something.
If it is not the admin, raise ValidationError using error_message.
"""
def verify_admin(user, tournament_id, error_message):
	tournament = Tournament.objects.get_by_id(tournament_id)
	if user != tournament.admin:
		raise ValidationError(error_message)

"""
This view is insanely complicated. The source of truth for the placements and eliminations data is held in a hidden 
field in the UI. The data structure in that hidden field is JSON.

Everytime the placements/eliminations are updated, the JSON payload is updated and htmx triggers the view to update.

Payload:
{
    "placements": {
       "0": "<player_id>",
       "1": "<player_id>",
       ...
    },
    "eliminations":[
       {
          "eliminator_id": "<player_id>",
          "eliminatee_id":"<player_id>"
       },
       {
          "eliminator_id":"<player_id>",
          "eliminatee_id":"<player_id>"
       },
       ...
    ],
    "split_eliminations":[
       {
          "eliminator_ids": [
			"<player_id5>"
			"<player_id23>"
          ],
          "eliminatee_id":"<player_id>"
       },
       {
          "eliminator_ids": [
			"<player_id6>"
			"<player_id23>"
			"<player_id12>"
          ],
          "eliminatee_id":"<player_id>"
       },
       ...
    ],
    "selected_eliminatee_id": "1" <--- Currently selected eliminatee for a split elimination. Defaults to -1.
    "selected_eliminator_ids": { <--- currently selected eliminators
       "0": "<player_id5",
       "1": "<player_id7",
       ...
     }
}
"""
@login_required
def tournament_backfill_view(request, *args, **kwargs):
	context = {}
	tournament = Tournament.objects.get_by_id(kwargs['pk'])
	error = None
	try:
		if request.user != tournament.admin:
			error = "Only the Tournment admin can backfill data."
		if tournament.get_state() != TournamentState.INACTIVE:
			error = "You can't backfill a Tournment that is ACTIVE or COMPLETED."
		if error != None:
			messages.error(request, error)
			return redirect("tournament:tournament_view", pk=tournament.id)
		context['tournament'] = tournament
		context['players'] = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		
		# --- START: Update Eliminations and Placements with htmx ---
		players = TournamentPlayer.objects.get_tournament_players(
			tournament_id = tournament.id
		)
		context['players'] = players
		player_eliminations = []
		data_json = None
		if request.method == "GET":
			data_json = request.GET.get('data_json')
		elif request.method == "POST":
			data_json = request.POST.get('data_json')
		elim_dict = {}
		num_payout_positions = len(tournament.tournament_structure.payout_percentages)
		context['num_payout_positions_iterator'] = range(0, num_payout_positions)
		placements_dict = {}
		if data_json != None and len(data_json) > 0:
			json_dict = json.loads(data_json)
			# Return the json data to the view. That is the source of truth.
			context['json_dict'] = data_json

			# parse the json placements data so its more readable in the view.
			if 'placements' in json_dict:
				for position in range(0, num_payout_positions):
					if f"{position}" in json_dict['placements']:
						player_id = json_dict['placements'][f'{position}']
						placements_dict[f"{position}"] = player_id

			# parse the json eliminations data so its more readable in the view.
			if "eliminations" in json_dict:
				for elimination in json_dict['eliminations']:
					eliminator_id = int(elimination['eliminator_id'])
					eliminatee_id = int(elimination['eliminatee_id'])
					player = TournamentPlayer.objects.get_by_id(eliminatee_id)
					if eliminator_id in elim_dict:
						current_values = elim_dict[eliminator_id]
						current_values.append(player)
						elim_dict[eliminator_id] = current_values
					else:
						elim_dict[eliminator_id] = [player]

			# parse the json selected eliminatee data so its more readable in the view.
			selected_eliminatee_player_id = None
			if "selected_eliminatee_id" in json_dict:
				selected_eliminatee_player_id = json_dict['selected_eliminatee_id']
				context['selected_eliminatee_id'] = int(selected_eliminatee_player_id)

			# parse the json selected eliminators data so its more readable in the view.
			eliminator_data_list = []
			if "selected_eliminator_ids" in json_dict:
				for eliminator_number in json_dict['selected_eliminator_ids']:
					eliminator_id = int(json_dict['selected_eliminator_ids'][eliminator_number])
					eliminator_data = {
						'eliminator_number': int(eliminator_number),
						'eliminator_id': eliminator_id
					}
					eliminator_data_list.append(eliminator_data)
				context['selected_eliminator_ids'] = eliminator_data_list

			split_eliminations = []
			if "split_eliminations" in json_dict:
				for split_elimination in json_dict['split_eliminations']:
					eliminator_players = []
					for player_id in split_elimination['eliminator_ids']:
						player = TournamentPlayer.objects.get_by_id(int(player_id))
						eliminator_players.append(player)
					eliminatee_player = TournamentPlayer.objects.get_by_id(int(split_elimination['eliminatee_id']))
					split_elim_dict = {
						'eliminatee': eliminatee_player,
						'eliminators': eliminator_players
					}
					split_eliminations.append(split_elim_dict)

			context['split_eliminations'] = split_eliminations
		# --- END: Update Eliminations and Placements with htmx ---

		context['elim_dict'] = elim_dict
		context['placements_dict'] = placements_dict

		# --- Saving ---
		if request.method == "POST":
			# --- Figure out the placements ---
			player_tournament_placements = {}
			# Populate data for positions who are getting paid
			for position in range(0, num_payout_positions):
				if f"{position}" in placements_dict:
					player_id = placements_dict[f"{position}"]
					player_tournament_placement = PlayerTournamentPlacement(
						player_id = player_id,
						placement = position
					)
					# Check for duplicates. Cannot assign the same player multiple placements
					if player_id in player_tournament_placements.keys():
						player = TournamentPlayer.objects.get_by_id(player_id)
						raise ValidationError(f"Cannot assign multiple placements to {player.user.username}.")
					player_tournament_placements[player_id] = player_tournament_placement

			# Verify a player was selected for each placement
			if len(player_tournament_placements.keys()) != num_payout_positions:
				raise ValidationError("You must select a player for each placement position.")

			# Find players who did not place
			players = TournamentPlayer.objects.get_tournament_players(
				tournament_id = tournament.id
			)
			for player in players:
				if f"{player.id}" not in player_tournament_placements.keys():
					player_tournament_placement = PlayerTournamentPlacement(
						player_id = player.id,
						placement = DID_NOT_PLACE_VALUE # assign 999999999 to players who did not place
	 				)
					player_tournament_placements[f"{player.id}"] = player_tournament_placement

			# DEBUG
			# for player_id in player_tournament_placements.keys():
			# 	player = TournamentPlayer.objects.get_by_id(player_id)
			# 	print(f"{player.user.username} placed {player_tournament_placements[player_id].placement}")

			# Complete the backfilled Tournament
			Tournament.objects.complete_tournament_for_backfill(
				user = request.user,
				tournament_id = tournament.id,
				player_tournament_placements = player_tournament_placements.values(),
				elim_dict = elim_dict,
				split_eliminations = split_eliminations
			)

			return redirect("tournament:tournament_view", pk=tournament.id)
	except Exception as e:
		if "Split Elimination Error" in e.args[0]:
			context['split_elimination_error'] = e.args[0]
		messages.error(request, e.args[0])
	return render(request=request, template_name="tournament/tournament_backfill.html", context=context)






















