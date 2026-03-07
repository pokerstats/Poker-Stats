from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import datetime
import random
import json

from tournament.models import Tournament, TournamentPlayer, TournamentState
from tournament_group.forms import CreateTournamentGroupForm
from tournament_group.models import TournamentGroup
from tournament_group.util import (
	build_json_from_net_earnings_data,
	build_json_from_pot_contributions_data,
	build_json_from_eliminations_and_rebuys_data,
	build_json_from_tournaments_played_data
)
from user.models import User

@login_required
def tournament_group_list_view(request, *args, **kwargs):
	context = {}
	try:
		tournament_groups = TournamentGroup.objects.get_tournament_groups(
			user_id=request.user.id
		).order_by("-start_at")
		context['tournament_groups'] = tournament_groups
	except Exception as e:
		messages.error(request, e.args[0])
	return render(request=request, template_name='tournament_group/tournament_group_list.html', context=context)

@login_required
def tournament_group_create_view(request, *args, **kwargs):
	context = {}
	try:
		if request.method == 'POST':
			form = CreateTournamentGroupForm(request.POST)
			if form.is_valid():
				tournament_group = TournamentGroup.objects.create_tournament_group(
					admin = request.user,
					title = form.cleaned_data['title'],
				)
				messages.success(request, "Tournament Group Created!")

				return redirect('tournament_group:view', pk=tournament_group.id)
		else:
			form = CreateTournamentGroupForm()
		context['form'] = form
	except Exception as e:
		messages.error(request, e.args[0])
		form = CreateTournamentGroupForm()
		context['form'] = form
	return render(request=request, template_name='tournament_group/create_tournament_group.html', context=context)

@login_required
def tournament_group_update_view(request, *args, **kwargs):
	context = {}
	try:
		pk = kwargs['pk']
		tournament_group = TournamentGroup.objects.get_by_id(pk)
		if tournament_group == None:
			raise ValidationError("Our records indicate that TournamentGroup does not exist.")

		if request.user != tournament_group.admin:
			return redirect("tournament_group:view", pk=tournament_group.id)

		context['tournament_group'] = tournament_group

		# Current start_at date.
		start_at_date = tournament_group.start_at
		if start_at_date != None:
			context['start_at_date_raw'] = start_at_date
			context['start_at_date'] = datetime.strftime(start_at_date, "%Y/%m/%d %H:%M")

		# Current end_at date
		end_at_date = tournament_group.end_at
		if end_at_date != None:
			context['end_at_date_raw'] = end_at_date
			context['end_at_date'] = datetime.strftime(end_at_date, "%Y/%m/%d %H:%M")

		# Get the updated title
		new_title = request.POST.get("new_title")
		if new_title == None or new_title == "":
			new_title = tournament_group.title
		context['new_title'] = new_title

		if_title_save_btn_enabled = False
		if new_title != tournament_group.title:
			if_title_save_btn_enabled = True
		context['if_title_save_btn_enabled'] = if_title_save_btn_enabled

		current_tournaments = tournament_group.get_tournaments()
		context['current_tournaments'] = current_tournaments

		# Search for tournaments with htmx
		search_tournaments = request.GET.get("search_tournaments")
		if search_tournaments != None and search_tournaments != "":
			tournament_search_result = Tournament.objects.all().filter(title__icontains=search_tournaments)
			
			# Exclude Tournaments that are already added
			for tournament in current_tournaments:
				tournament_search_result = tournament_search_result.exclude(id=tournament.id)

			# Exclude tournaments where:
			# 1. Not completed
			# 2. Not within the allowed date range
			for tournament in tournament_search_result:
				if tournament.get_state() != TournamentState.COMPLETED:
					tournament_search_result = tournament_search_result.exclude(id=tournament.id)
				if tournament.completed_at != None:
					if tournament_group.start_at != None and tournament.completed_at < tournament_group.start_at:
						tournament_search_result = tournament_search_result.exclude(id=tournament.id)
					if tournament_group.end_at != None and tournament.completed_at > tournament_group.end_at:
						tournament_search_result = tournament_search_result.exclude(id=tournament.id)

			context['tournament_search_result'] = tournament_search_result
			context['search_tournaments'] = search_tournaments

		# Update end_at date with htmx
		end_at_date = request.GET.get("update_end_at_date")
		if end_at_date != None:
			updated_group = TournamentGroup.objects.update_end_at_date(
				user = request.user,
				group = tournament_group,
				end_at_date = end_at_date
			)
			context['end_at_date_raw'] = updated_group.end_at
			context['end_at_date'] = datetime.strftime(updated_group.end_at, "%Y/%m/%d")

		# Update start_at date with htmx
		start_at_date = request.GET.get("update_start_at_date")
		if start_at_date != None:
			updated_group = TournamentGroup.objects.update_start_at_date(
				user = request.user,
				group = tournament_group,
				start_at_date = start_at_date
			)
			context['start_at_date_raw'] = updated_group.start_at
			context['start_at_date'] = datetime.strftime(updated_group.start_at, "%Y/%m/%d")

		current_tournaments = tournament_group.get_tournaments()
		context['current_tournaments'] = current_tournaments

		context['edit_mode'] = True

		# Remove tournaments that do not fall within new date range.
		# Get an updated version of the group at this point b/c if may have changed.
		tournament_group = TournamentGroup.objects.get_by_id(tournament_group.id)
		removed_tournaments = []
		for tournament in current_tournaments:
			if tournament.completed_at != None:
				if tournament_group.end_at != None and tournament.completed_at > tournament_group.end_at:
					TournamentGroup.objects.remove_tournament_from_group(
							admin = tournament_group.admin,
							group = tournament_group,
							tournament = tournament
						)
					removed_tournaments.append(tournament)
					continue
				if tournament_group.start_at != None and tournament.completed_at < tournament_group.start_at:
					TournamentGroup.objects.remove_tournament_from_group(
							admin = tournament_group.admin,
							group = tournament_group,
							tournament = tournament
						)
					removed_tournaments.append(tournament)
					continue
					
		if len(removed_tournaments) > 0:
			warning_message = "Removed tournaments: "
			for index,tournament in enumerate(removed_tournaments):
				if index > 0:
					warning_message += ", "
				warning_message += f"({tournament.title})"
			messages.warning(request, warning_message)
			current_tournaments = tournament_group.get_tournaments()
			context['current_tournaments'] = current_tournaments
	except Exception as e:
		messages.error(request, e.args[0])
	return render(request=request, template_name='tournament_group/update_tournament_group.html', context=context)


@login_required
def view_tournament_group(request, *args, **kwargs):
	context = {}
	try:
		pk = kwargs['pk']
		tournament_group = TournamentGroup.objects.get_by_id(pk)
		if tournament_group == None:
			raise ValidationError("Our records indicate that TournamentGroup does not exist.")

		context['tournament_group'] = tournament_group

		users = tournament_group.get_users()
		context['users'] = users

		if request.user != tournament_group.admin and request.user not in users:
			return redirect("error", error_message="You are not part of that Tournament Group.")

		tournaments = tournament_group.get_tournaments()
		context['tournaments'] = tournaments

		start_at = tournament_group.start_at
		context['start_at'] = start_at

		end_at = tournament_group.end_at
		context['end_at'] = end_at

		if start_at and end_at:
			today = timezone.now()
			if start_at > today:
				context['days_until_start'] = (start_at - today).days
			if today > end_at:
				context['days_since_end'] = (today - end_at).days
			progress = tournament_group.get_progress()
			duration = tournament_group.get_group_duration()
			days_remaining = tournament_group.get_days_remaining()
			pct = progress / duration
			context['progress_pct'] = int(pct * 100)
			context['duration'] = duration
			context['progress'] = progress
			context['days_remaining'] = days_remaining

		context['edit_mode'] = False
	except Exception as e:
		messages.error(request, e.args[0])
	return render(request=request, template_name='tournament_group/tournament_group_view.html', context=context)

@login_required
def fetch_tournament_group_net_earnings_data(request, *args, **kwargs):
	context = {}
	try:
		pk = kwargs['pk']
		tournament_group = TournamentGroup.objects.get_by_id(pk)
		if tournament_group == None:
			raise ValidationError("Our records indicate that TournamentGroup does not exist.")

		net_earnings_data = TournamentGroup.objects.build_group_net_earnings_data(
			group = tournament_group
		)
		context['net_earnings_data'] = build_json_from_net_earnings_data(net_earnings_data)
	except Exception as e:
		error = {
			'error': "Unable to retrieve net earnings data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)

@login_required
def fetch_rbg_colors(request, *args, **kwargs):
	context = {}
	try:
		num_colors = kwargs['num_colors']
		colors = {}
		for x in range(0, int(num_colors)):
			color_list = list(random.choices(range(256), k=3))
			color = f"rgb({color_list[0]}, {color_list[1]}, {color_list[2]})"
			colors[f"{x}"] = color
		context['rbg_colors'] = colors
	except Exception as e:
		error = {
			'error': "Unable to retrieve colors for graphs.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)

@login_required
def fetch_tournament_group_pot_contributions_data(request, *args, **kwargs):
	context = {}
	try:
		pk = kwargs['pk']
		tournament_group = TournamentGroup.objects.get_by_id(pk)
		if tournament_group == None:
			raise ValidationError("Our records indicate that TournamentGroup does not exist.")

		pot_contributions_data = TournamentGroup.objects.build_group_pot_contributions_data(
			group = tournament_group
		)
		context['pot_contributions_data'] = build_json_from_pot_contributions_data(pot_contributions_data)
	except Exception as e:
		error = {
			'error': "Unable to retrieve pot contributions data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)

@login_required
def fetch_tournament_group_eliminations_and_rebuys_data(request, *args, **kwargs):
	context = {}
	try:
		pk = kwargs['pk']
		tournament_group = TournamentGroup.objects.get_by_id(pk)
		if tournament_group == None:
			raise ValidationError("Our records indicate that TournamentGroup does not exist.")

		eliminations_and_rebuys_data = TournamentGroup.objects.build_group_eliminations_and_rebuys_data(
			group = tournament_group
		)
		context['eliminations_and_rebuys_data'] = build_json_from_eliminations_and_rebuys_data(eliminations_and_rebuys_data)
	except Exception as e:
		error = {
			'error': "Unable to retrieve eliminations and rebuys data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)

@login_required
def fetch_tournament_group_touraments_played_data(request, *args, **kwargs):
	context = {}
	try:
		pk = kwargs['pk']
		tournament_group = TournamentGroup.objects.get_by_id(pk)
		if tournament_group == None:
			raise ValidationError("Our records indicate that TournamentGroup does not exist.")

		tournaments_played = TournamentGroup.objects.build_group_tournaments_played_data(
			group = tournament_group
		)
		context['tournaments_played'] = build_json_from_tournaments_played_data(tournaments_played)
	except Exception as e:
		error = {
			'error': "Unable to retrieve tournaments played data.",
			'message': f"{e.args[0]}"
		}
		return JsonResponse(error, status=200)
	return JsonResponse(context, status=200)


"""
HTMX request for adding a Tournament to a TournamentGroup.
"""
@login_required
def add_tournament_to_group(request, *args, **kwargs):
	try:
		tournament_id = kwargs['tournament_id']
		tournament_group_id = kwargs['tournament_group_id']

		tournament = Tournament.objects.get_by_id(tournament_id)
		tournament_group = TournamentGroup.objects.get_by_id(tournament_group_id)
		
		TournamentGroup.objects.add_tournaments_to_group(
			admin = request.user,
			group = tournament_group,
			tournaments = [tournament]
		)
	except Exception as e:
		messages.error(request, e.args[0])
	return redirect(request.META['HTTP_REFERER'])


"""
HTMX request for removing a Tournament to a TournamentGroup.
"""
@login_required
def remove_tournament_from_group(request, *args, **kwargs):
	try:
		tournament_id = kwargs['tournament_id']
		tournament_group_id = kwargs['tournament_group_id']

		tournament = Tournament.objects.get_by_id(tournament_id)
		tournament_group = TournamentGroup.objects.get_by_id(tournament_group_id)
		
		TournamentGroup.objects.remove_tournament_from_group(
			admin = request.user,
			group = tournament_group,
			tournament = tournament
		)
	except Exception as e:
		messages.error(request, e.args[0])
	return redirect(request.META['HTTP_REFERER'])

"""
HTMX request for updating the Tournament Group title.
"""
@login_required
def update_tournament_group_title(request, *args, **kwargs):
	try:
		title = kwargs['title']
		tournament_group_id = kwargs['tournament_group_id']

		tournament_group = TournamentGroup.objects.get_by_id(tournament_group_id)
		
		TournamentGroup.objects.update_tournament_group_title(
			admin = request.user,
			group = tournament_group,
			title = title
		)
	except Exception as e:
		messages.error(request, e.args[0])
	return redirect(request.META['HTTP_REFERER'])


















