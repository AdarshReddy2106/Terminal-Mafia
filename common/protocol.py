"""
protocol.py — Message protocol definitions for Terminal Mafia

Defines all message types exchanged between server and clients,
plus helper functions to create and parse protocol messages.
Every message is a JSON object with the structure:
    { "type": "<MSG_TYPE>", "data": { ... } }
Messages are delimited by newlines for stream-based TCP.
"""

import json
from common.constants import MESSAGE_DELIMITER


# ══════════════════════════════════════════════
# Message Type Constants
# ══════════════════════════════════════════════

# --- Client → Server ---
MSG_JOIN = "JOIN"                   # Player requests to join the lobby
MSG_CHAT = "CHAT"                  # Player sends a chat message
MSG_VOTE = "VOTE"                  # Player votes to eliminate someone
MSG_NIGHT_ACTION = "NIGHT_ACTION"  # Player performs a night action (Mafia kill, Detective investigate, etc.)
MSG_START_GAME = "START_GAME"      # Host requests to start the game
MSG_PONG = "PONG"                  # Response to server ping (heartbeat)

# --- Server → Client ---
MSG_WELCOME = "WELCOME"            # Server acknowledges join, sends player id
MSG_PLAYER_LIST = "PLAYER_LIST"    # Broadcast updated player list
MSG_ROLE_ASSIGN = "ROLE_ASSIGN"    # Server assigns a role to the player
MSG_PHASE_CHANGE = "PHASE_CHANGE"  # Announce phase transition
MSG_CHAT_MSG = "CHAT_MSG"          # Broadcast a chat message to players
MSG_VOTE_RESULT = "VOTE_RESULT"    # Announce vote tally and elimination
MSG_NIGHT_RESULT = "NIGHT_RESULT"  # Announce night phase outcome (who died / was saved)
MSG_GAME_OVER = "GAME_OVER"       # Announce game winner and reveal all roles
MSG_ERROR = "ERROR"                # Error message (invalid action, etc.)
MSG_PING = "PING"                  # Server heartbeat check
MSG_PLAYER_JOINED = "PLAYER_JOINED"    # Notify lobby that a new player joined
MSG_PLAYER_LEFT = "PLAYER_LEFT"        # Notify lobby that a player disconnected
MSG_LOBBY_STATUS = "LOBBY_STATUS"      # Current lobby state (player count, waiting status)
MSG_SERVER_MSG = "SERVER_MSG"          # Generic server announcement
MSG_SUSPICION_DATA = "SUSPICION_DATA"              # Chat mention counts for suspicion meter
MSG_INVESTIGATION_RESULT = "INVESTIGATION_RESULT"  # Detective's investigation result (private)
MSG_SPECTATOR_START = "SPECTATOR_START"            # Player enters spectator mode (all roles revealed)

# --- Task System ---
MSG_TASK_ASSIGN = "TASK_ASSIGN"        # Server sends tasks to a player at night
MSG_TASK_SUBMIT = "TASK_SUBMIT"        # Client submits a task answer
MSG_TASK_RESULT = "TASK_RESULT"        # Server responds with correct/incorrect
MSG_TASK_PROGRESS = "TASK_PROGRESS"    # Server broadcasts task bar progress to all

# ══════════════════════════════════════════════
# Message Builder Functions
# ══════════════════════════════════════════════

def create_message(msg_type: str, data: dict = None) -> str:
    """
    Build a JSON message string with a trailing delimiter.
    
    Args:
        msg_type: One of the MSG_* constants
        data: Optional dict of message payload
    
    Returns:
        JSON string ending with MESSAGE_DELIMITER, ready to send over TCP.
    """
    message = {
        "type": msg_type,
        "data": data if data is not None else {}
    }
    return json.dumps(message) + MESSAGE_DELIMITER


def parse_messages(raw_data: str) -> list[dict]:
    """
    Parse one or more JSON messages from a raw TCP data chunk.
    
    Since TCP is stream-based, a single recv() may contain multiple
    messages or partial messages. This function splits on the delimiter
    and parses each complete message.
    
    Args:
        raw_data: Raw string received from TCP socket
    
    Returns:
        List of parsed message dicts. Malformed messages are skipped.
    """
    messages = []
    parts = raw_data.split(MESSAGE_DELIMITER)
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        try:
            msg = json.loads(part)
            if isinstance(msg, dict) and "type" in msg:
                messages.append(msg)
        except json.JSONDecodeError:
            # Skip malformed messages
            continue
    
    return messages


# ══════════════════════════════════════════════
# Convenience Builders (Server → Client)
# ══════════════════════════════════════════════

def msg_welcome(player_id: str, player_name: str) -> str:
    """Server acknowledges a player's join request."""
    return create_message(MSG_WELCOME, {
        "player_id": player_id,
        "player_name": player_name
    })


def msg_player_joined(player_name: str, player_count: int, min_players: int) -> str:
    """Broadcast that a new player has joined the lobby."""
    return create_message(MSG_PLAYER_JOINED, {
        "player_name": player_name,
        "player_count": player_count,
        "min_players": min_players
    })


def msg_player_left(player_name: str, player_count: int) -> str:
    """Broadcast that a player has disconnected."""
    return create_message(MSG_PLAYER_LEFT, {
        "player_name": player_name,
        "player_count": player_count
    })


def msg_player_list(players: list[dict]) -> str:
    """Send the full list of players in the lobby/game."""
    return create_message(MSG_PLAYER_LIST, {
        "players": players
    })


def msg_lobby_status(player_count: int, min_players: int, max_players: int, players: list[str]) -> str:
    """Send current lobby status."""
    return create_message(MSG_LOBBY_STATUS, {
        "player_count": player_count,
        "min_players": min_players,
        "max_players": max_players,
        "players": players,
        "can_start": player_count >= min_players
    })


def msg_error(message: str) -> str:
    """Send an error message to a client."""
    return create_message(MSG_ERROR, {
        "message": message
    })


def msg_server_announcement(message: str) -> str:
    """Send a generic server announcement."""
    return create_message(MSG_SERVER_MSG, {
        "message": message
    })


def msg_ping() -> str:
    """Server heartbeat ping."""
    return create_message(MSG_PING)


def msg_pong() -> str:
    """Client heartbeat response."""
    return create_message(MSG_PONG)


def msg_last_words(message: str) -> str:
    """Client sends their last words after being eliminated."""
    return create_message(MSG_LAST_WORDS, {
        "message": message
    })


# ══════════════════════════════════════════════
# Convenience Builders (Client → Server)
# ══════════════════════════════════════════════

def msg_join(player_name: str) -> str:
    """Client requests to join with a given name."""
    return create_message(MSG_JOIN, {
        "name": player_name
    })


def msg_chat(message: str) -> str:
    """Client sends a chat message."""
    return create_message(MSG_CHAT, {
        "message": message
    })
