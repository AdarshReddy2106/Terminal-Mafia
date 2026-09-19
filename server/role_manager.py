"""
role_manager.py — Role assignment logic for Terminal Mafia

Handles:
- Determining how many Mafia members based on player count
- Randomly assigning roles to players
- Querying role properties (team, night ability, etc.)
"""

import random

from common.constants import (
    MAFIA_DISTRIBUTION,
    ROLE_VILLAGER, ROLE_MAFIA,
    TEAM_TOWN, TEAM_MAFIA
)


def get_mafia_count(player_count: int) -> int:
    """
    Determine how many Mafia members to assign based on total player count.
    
    Uses the MAFIA_DISTRIBUTION table from constants:
        4-6 players  → 1 Mafia
        7-9 players  → 2 Mafia
        10+ players  → 3 Mafia
    """
    # Handle testing scenarios with fewer than 4 players
    if player_count < 4:
        return 1

    for (min_p, max_p), num_mafia in MAFIA_DISTRIBUTION.items():
        if min_p <= player_count <= max_p:
            return num_mafia
    # Fallback for very large games
    return 3


def assign_roles(player_ids: list[str]) -> dict[str, str]:
    """
    Randomly assign roles to all players.
    
    Args:
        player_ids: List of player IDs to assign roles to.
    
    Returns:
        Dict mapping player_id -> role name (e.g., "Mafia", "Villager")
    """
    player_count = len(player_ids)
    mafia_count = get_mafia_count(player_count)

    # Shuffle player list to randomize assignment
    shuffled = list(player_ids)
    random.shuffle(shuffled)

    roles = {}

    # First N players become Mafia
    for i in range(mafia_count):
        roles[shuffled[i]] = ROLE_MAFIA

    # Remaining players become Villagers
    for i in range(mafia_count, player_count):
        roles[shuffled[i]] = ROLE_VILLAGER

    return roles


def get_team(role: str) -> str:
    """Get the team a role belongs to."""
    if role in (ROLE_MAFIA,):
        return TEAM_MAFIA
    return TEAM_TOWN


def get_role_description(role: str) -> str:
    """Get a human-readable description of a role."""
    descriptions = {
        ROLE_VILLAGER: "You are a Villager. Find and eliminate the Mafia through voting!",
        ROLE_MAFIA: "You are Mafia. Eliminate Villagers at night without being caught!",
    }
    return descriptions.get(role, "Unknown role.")
