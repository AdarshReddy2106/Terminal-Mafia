"""
role_manager.py — Role assignment logic for Terminal Mafia

Handles:
- Determining how many Mafia members based on player count
- Randomly assigning roles to players (including special roles)
- Querying role properties (team, night ability, etc.)

Role Distribution:
    4 players:  1 Mafia, 3 Villagers
    5 players:  1 Mafia, 1 Detective, 3 Villagers
    6 players:  1 Mafia, 1 Detective, 1 Doctor, 3 Villagers
    7-8 players: 2 Mafia, 1 Detective, 1 Doctor, 1 Engineer, rest Villagers
    9+ players:  2 Mafia, 1 Detective, 1 Doctor, 1 Engineer, rest Villagers
"""

import random

from common.constants import (
    MAFIA_DISTRIBUTION,
    ROLE_VILLAGER, ROLE_MAFIA, ROLE_DETECTIVE, ROLE_DOCTOR, ROLE_ENGINEER,
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
    Randomly assign roles to all players, including special roles.

    Assignment order (after Mafia):
        1. Detective (5+ players)
        2. Doctor (6+ players)
        3. Engineer (7+ players)
        4. Remaining become Villagers

    Args:
        player_ids: List of player IDs to assign roles to.

    Returns:
        Dict mapping player_id -> role name
    """
    player_count = len(player_ids)
    mafia_count = get_mafia_count(player_count)

    # Shuffle player list to randomize assignment
    shuffled = list(player_ids)
    random.shuffle(shuffled)

    roles = {}
    idx = 0

    # Assign Mafia
    for i in range(mafia_count):
        roles[shuffled[idx]] = ROLE_MAFIA
        idx += 1

    # Assign Detective (5+ players)
    if player_count >= 5 and idx < player_count:
        roles[shuffled[idx]] = ROLE_DETECTIVE
        idx += 1

    # Assign Doctor (6+ players)
    if player_count >= 6 and idx < player_count:
        roles[shuffled[idx]] = ROLE_DOCTOR
        idx += 1

    # Assign Engineer (7+ players)
    if player_count >= 7 and idx < player_count:
        roles[shuffled[idx]] = ROLE_ENGINEER
        idx += 1

    # Remaining players become Villagers
    while idx < player_count:
        roles[shuffled[idx]] = ROLE_VILLAGER
        idx += 1

    return roles


def get_team(role: str) -> str:
    """Get the team a role belongs to."""
    if role == ROLE_MAFIA:
        return TEAM_MAFIA
    return TEAM_TOWN


def get_role_description(role: str) -> str:
    """Get a human-readable description of a role."""
    descriptions = {
        ROLE_VILLAGER: "You are a Villager. Complete tasks at night and find the Mafia through voting!",
        ROLE_MAFIA: (
            "You are Mafia. Eliminate Villagers at night without being caught! "
            "You must wait 15 seconds before you can use /kill. "
            "You also get tasks as cover — completing them is optional."
        ),
        ROLE_DETECTIVE: (
            "You are the Detective. Each night, investigate one player to learn "
            "if they are Mafia or Town. Use /investigate <name> during the night. "
            "Don't forget to complete your tasks too!"
        ),
        ROLE_DOCTOR: (
            "You are the Doctor. During the Discussion phase, privately choose one "
            "player to protect from the Mafia's kill tonight. Use /protect <name> "
            "during Discussion. Complete your tasks at night!"
        ),
        ROLE_ENGINEER: (
            "You are the Engineer. Complete your 3 tasks at night, then you get "
            "1 bonus task. Every task you complete counts toward the Town's task bar. "
            "Help the Town win by finishing all tasks!"
        ),
    }
    return descriptions.get(role, "Unknown role.")


def has_night_action(role: str) -> bool:
    """Check if a role has a special night action to perform (beyond tasks)."""
    return role in (ROLE_MAFIA, ROLE_DETECTIVE)
