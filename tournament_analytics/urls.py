from django.urls import include, path

from tournament_analytics.views import (
	fetch_tournament_totals_data,
	fetch_tournament_player_results_data,
	fetch_tournament_player_eliminations_data,
	fetch_tournament_eliminations_and_rebuys_data,
	stats_view,
	fetch_all_analytics_data,
)

app_name = 'tournament_analytics'

urlpatterns = [
    path('stats/', stats_view, name="stats"),
    path('fetch_all_analytics_data/<int:user_id>/', fetch_all_analytics_data, name="fetch_all_analytics_data"),
    path('fetch_tournament_totals_data/<int:user_id>/', fetch_tournament_totals_data, name="fetch_tournament_totals_data"),
    path('fetch_tournament_player_results_data/<int:user_id>/', fetch_tournament_player_results_data, name="fetch_tournament_player_results_data"),
    path('fetch_tournament_player_eliminations_data/<int:user_id>/', fetch_tournament_player_eliminations_data, name="fetch_tournament_player_eliminations_data"),
    path('fetch_tournament_eliminations_and_rebuys_data/<int:user_id>/', fetch_tournament_eliminations_and_rebuys_data, name="fetch_tournament_eliminations_and_rebuys_data"),
]

