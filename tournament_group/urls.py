from django.urls import include, path

from tournament_group.views import (
	add_tournament_to_group,
	fetch_rbg_colors,
	fetch_tournament_group_eliminations_and_rebuys_data,
	fetch_tournament_group_net_earnings_data,
	fetch_tournament_group_pot_contributions_data,
	fetch_tournament_group_touraments_played_data,
	remove_tournament_from_group,
	tournament_group_create_view,
	tournament_group_list_view,
	tournament_group_update_view,
	update_tournament_group_title,
	view_tournament_group
)

app_name = 'tournament_group'

urlpatterns = [
    path('add_tourament_to_group/<int:tournament_id>/<int:tournament_group_id>/', add_tournament_to_group, name="add_tournament_to_group"),
    path('remove_tournament_from_group/<int:tournament_id>/<int:tournament_group_id>/', remove_tournament_from_group, name="remove_tournament_from_group"),
    path('fetch_elim_and_rebuys_data/<int:pk>/', fetch_tournament_group_eliminations_and_rebuys_data, name="fetch_elim_and_rebuys_data"),
    path('fetch_net_earnings_data/<int:pk>/', fetch_tournament_group_net_earnings_data, name="fetch_net_earnings_data"),
    path('fetch_pot_contributions_data/<int:pk>/', fetch_tournament_group_pot_contributions_data, name="fetch_pot_contributions_data"),
    path('fetch_rbg_colors/<int:num_colors>/', fetch_rbg_colors, name="fetch_rbg_colors"),
    path('fetch_tournaments_played_data/<int:pk>/', fetch_tournament_group_touraments_played_data, name="fetch_tournaments_played_data"),
    path('', tournament_group_list_view, name="list"),
    path('create/', tournament_group_create_view, name="create"),
    path('update/<int:pk>/', tournament_group_update_view, name="update"),
    path('update_tournament_group_title/<int:tournament_group_id>/<path:title>/', update_tournament_group_title, name="update_tournament_group_title"),
    path('view_tournament_group/<int:pk>/', view_tournament_group, name="view"),
]
