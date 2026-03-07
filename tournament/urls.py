from django.urls import include, path

from tournament.views import (
    add_player_to_tournament,
    complete_tournament,
    eliminate_player_from_tournament,
    get_tournament_structure,
    rebuy_player_in_tournament,
    remove_player_from_tournament,
    search_tournament_players,
    split_eliminate_player_from_tournament,
    start_tournament,
    tournament_admin_view,
    tournament_backfill_view,
    tournament_create_view,
    tournament_edit_view,
    tournament_list_view,
    tournament_structure_create_view,
    tournament_view,
    undo_completed_at,
    undo_started_at,
)

app_name = 'tournament'

urlpatterns = [
    path('add_player/<int:player_id>/<int:tournament_id>/', add_player_to_tournament, name="add_player"),
    path('complete/<int:pk>/', complete_tournament, name="complete"),
    path('create_tournament/', tournament_create_view, name="create_tournament"),
    path('create_tournament_structure/', tournament_structure_create_view, name="create_tournament_structure"),
    path('eliminate_player/<int:tournament_id>/<int:eliminator_id>/<int:eliminatee_id>/', eliminate_player_from_tournament, name="eliminate_player"),
    path('get_tournament_structure/', get_tournament_structure, name="get_tournament_structure"),
    path('player_rebuy/<int:player_id>/<int:tournament_id>/', rebuy_player_in_tournament, name="player_rebuy"),
    path('remove_player/<int:user_id>/<int:tournament_id>/', remove_player_from_tournament, name="remove_player"),
    path('split_eliminate_player/<int:tournament_id>/<str:eliminator_ids>/<int:eliminatee_id>/', split_eliminate_player_from_tournament, name="split_eliminate_player"),
    path('start/<int:pk>/', start_tournament, name="start"),
    path('tournament_admin_view/<int:pk>/', tournament_admin_view, name="tournament_admin_view"),
    path('tournament_backfill_view/<int:pk>/', tournament_backfill_view, name="tournament_backfill"),
    path('tournament_edit/<int:pk>/', tournament_edit_view, name="tournament_edit"),
    path('tournament_list/', tournament_list_view, name="tournament_list"),
    path('tournament_view/<int:pk>/', tournament_view, name="tournament_view"),
    path('search_players/<int:pk>/', search_tournament_players, name="search_players"),
    path('undo_complete/<int:pk>/', undo_completed_at, name="undo_complete"),
    path('undo_started/<int:pk>/', undo_started_at, name="undo_started"),
]



