"""
constants.py — Game constants for Terminal Mafia

All configurable values (timers, player limits, role counts, network settings)
are centralized here for easy tuning.
"""

# ──────────────────────────────────────────────
# Network Settings
# ──────────────────────────────────────────────
DEFAULT_HOST = "0.0.0.0"       # Bind to all interfaces
DEFAULT_PORT = 5555
BUFFER_SIZE = 4096             # Max bytes per recv call
MESSAGE_DELIMITER = "\n"       # Delimiter between JSON messages

# ──────────────────────────────────────────────
# Lobby Settings
# ──────────────────────────────────────────────
MIN_PLAYERS = 4
MAX_PLAYERS = 10
LOBBY_COUNTDOWN_SECONDS = 10   # Countdown before game starts after min players reached

# ──────────────────────────────────────────────
# Game Timers (seconds)
# ──────────────────────────────────────────────
NIGHT_PHASE_DURATION = 60
DISCUSSION_PHASE_DURATION = 90
VOTING_PHASE_DURATION = 30
DAWN_REVEAL_DURATION = 5
MAFIA_KILL_DELAY = 15          # Mafia must wait this many seconds before using /kill
GHOST_TASK_DURATION = 30       # How long ghosts have to complete tasks after death

# ──────────────────────────────────────────────
# Task Settings
# ──────────────────────────────────────────────
TASKS_PER_PLAYER = 3           # Each player gets 3 tasks (1 easy, 1 medium, 1 hard)
ENGINEER_BONUS_TASKS = 1       # Engineer gets 1 bonus task after finishing their 3

# ──────────────────────────────────────────────
# Role Distribution
# ──────────────────────────────────────────────
# Format: (min_players, max_players): num_mafia
MAFIA_DISTRIBUTION = {
    (4, 6): 1,
    (7, 9): 2,
    (10, 15): 3,
}

# ──────────────────────────────────────────────
# Role Names
# ──────────────────────────────────────────────
ROLE_VILLAGER = "Villager"
ROLE_MAFIA = "Mafia"
ROLE_DETECTIVE = "Detective"
ROLE_DOCTOR = "Doctor"
ROLE_DOUBLE_AGENT = "Double Agent"  # Kept for backward compat, no longer assigned
ROLE_ENGINEER = "Engineer"

# Teams
TEAM_TOWN = "Town"
TEAM_MAFIA = "Mafia"

# ──────────────────────────────────────────────
# Game Phases
# ──────────────────────────────────────────────
PHASE_LOBBY = "LOBBY"
PHASE_NIGHT = "NIGHT"
PHASE_DAWN = "DAWN"
PHASE_DISCUSSION = "DISCUSSION"
PHASE_VOTING = "VOTING"
PHASE_GAME_OVER = "GAME_OVER"

