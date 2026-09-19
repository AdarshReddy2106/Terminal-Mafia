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
ROLE_DOUBLE_AGENT = "Double Agent"

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
