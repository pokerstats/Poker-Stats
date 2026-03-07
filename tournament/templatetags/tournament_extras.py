from decimal import Decimal
from django import template
from django.template.defaultfilters import stringfilter
from tournament.models import TournamentPlayer, TournamentRebuy, TournamentElimination
from tournament.util import (
	build_placement_string,
	TournamentEliminationEvent,
	TournamentRebuyEvent,
	TournamentCompleteEvent,
	TournamentInProgressEvent,
	TournamentSplitEliminationEvent
)

register = template.Library()

"""
Used to format the way money is displayed.
Ex: 0.00 -> --
Ex: 5.56 -> $5.67
"""
@register.filter(name='format_money')
@stringfilter
def format_money(money_string):
	if money_string == "0.00" or money_string == "0.0" or money_string == "0":
		return "--"
	else:
		money_value = round(Decimal(money_string), 2)
		if money_value < 0:
			return f"-${abs(money_value)}"
		return f"${money_value}"

"""
Used to format a number such that '0' becomes '--'.
Ex: 0 -> --
Ex: 5 -> 5
"""
@register.filter(name='format_table_number')
@stringfilter
def format_table_number(num_eliminations):
	if num_eliminations == "0":
		return "--"
	else:
		if Decimal(num_eliminations) % 1 > 0:
			return f"{num_eliminations}"
		else:
			return f"{num_eliminations}".split(".")[0]
		

"""
Used to format the placement color for a Player in the Tournemnt.
Ex: If payout_percentages = (50, 30, 20) then 1st, 2nd and 3rd will be "#5cb85c" (green)
"""
@register.filter(name='placement_color')
@stringfilter
def placement_color(placement, placements):
	split_placements = placements.split(",")
	if placement in split_placements:
		return "#5cb85c"
	else:
		return "#d9534f"

"""
Format the color of an earnings row.
Green for positive.
Red for negative.
Black for 0.
"""
@register.filter(name='format_table_number_color')
@stringfilter
def format_table_number_color(number):
	decimal_number = Decimal(number)
	zero = Decimal(0.00)
	if decimal_number > zero:
		return "#5cb85c"
	elif decimal_number < zero:
		return "#d9534f"
	else:
		return "#292b2c"

"""
Format the font-weight.
"""
@register.filter(name='format_number_weight')
@stringfilter
def format_number_weight(number):
	decimal_number = Decimal(number)
	zero = Decimal(0.00)
	if decimal_number != zero:
		return 550
	else: 
		return 400

"""
Format placement position.
"""
@register.filter(name='format_placement')
def format_placement(placement):
	return build_placement_string(placement)

"""
get a value from a dictionary.
"""
@register.filter
def keyvalue(dictionary, key):
	try:
		return dictionary[f'{key}']
	except KeyError:
		return ''

"""
Return true if an eliminator_id value exists in the list of dicts.
data_list is used in 'tournament_backfill_view'. Format:
[
	{
		'eliminator_number': '0',
		'eliminator_id': '<playerid1>'
	},
	{
		'eliminator_number': '1',
		'eliminator_id': '<playerid8>'
	},
	...
]

"""
@register.filter
def keyvalue_in_list(data_list, eliminator_id):
	for item in data_list:
		try:
			if item['eliminator_id'] == eliminator_id:
				return True
		except KeyError:
			pass
	return False

"""
Does a value exist in a list.
"""
@register.filter
def does_value_exist_in_list(data_list, value):
	return value in data_list


"""
Get the number of rebuys for a TournamentPlayer.
"""
@register.filter
def get_rebuys_for_player(player):
	rebuys = TournamentRebuy.objects.get_rebuys_for_player(player)
	return rebuys

"""
Determine if an object is a TournamentRebuyEvent.
"""
@register.filter
def is_tournament_rebuy(obj):
	return type(obj) is TournamentRebuyEvent

"""
Determine if an object is a TournamentEliminationEvent.
"""
@register.filter
def is_tournament_elimination(event):
	return type(event) is TournamentEliminationEvent

"""
Determine if an object is a TournamentCompleteEvent.
"""
@register.filter
def is_tournament_completion(event):
	return type(event) is TournamentCompleteEvent

"""
Determine if an object is a TournamentInProgressEvent.
"""
@register.filter
def is_tournament_in_progress(event):
	return type(event) is TournamentInProgressEvent

"""
Determine if an object is a TournamentSplitEliminationEvent.
"""
@register.filter
def is_tournament_split_elimination(event):
	return type(event) is TournamentSplitEliminationEvent

"""
Build a range from (0 -> length-substract_length)
args: 'subtract_length, starting_value'
"""
@register.filter
def build_loop_range(length, args):
	split_args = args.split(",")
	subtract_length = int(split_args[0])
	starting_value = int(split_args[1])
	counter = starting_value
	range_list = []
	for x in range(0, length - subtract_length):
		range_list.append(counter)
		counter += 1
	return range_list

"""
Change value to a string.
"""
@register.filter
def as_string(value):
	return f"{value}"

"""
If 'None', format to empty string.
"""
@register.filter
def none_as_empty(value):
	if value == None:
		return ''
	return value

"""
Concatenate a string to length of 'length'
"""
@register.filter
def concatenate_string(string, length):
	if len(string) > length:
		return f"{string[:length]}..."
	return string

"""
Get the number of completed tournaments in a list of tournaments
"""
@register.filter
def completed_count(tournaments):
	return len(tournaments.exclude(completed_at = None))















