"""
client.py — TCP Game Client for Terminal Mafia

Handles:
- Connecting to the game server via TCP
- Sending JOIN, CHAT, and other messages
- Receiving and dispatching server messages in a background thread
- Heartbeat (PONG) responses to keep connection alive
- Reconnection-safe disconnect handling
"""

import socket
import threading
import sys
import time

from common.constants import (
    BUFFER_SIZE, MESSAGE_DELIMITER, DEFAULT_HOST, DEFAULT_PORT,
    PHASE_LOBBY, PHASE_NIGHT, PHASE_DAWN, PHASE_DISCUSSION,
    PHASE_VOTING, PHASE_GAME_OVER, ROLE_MAFIA
)
from common.protocol import (
    parse_messages, msg_join, msg_chat, msg_pong,
    create_message,
    MSG_WELCOME, MSG_PLAYER_JOINED, MSG_PLAYER_LEFT, MSG_PLAYER_LIST,
    MSG_LOBBY_STATUS, MSG_CHAT_MSG, MSG_ERROR, MSG_PING,
    MSG_SERVER_MSG, MSG_PHASE_CHANGE, MSG_ROLE_ASSIGN,
    MSG_VOTE_RESULT, MSG_NIGHT_RESULT, MSG_GAME_OVER,
    MSG_START_GAME, MSG_VOTE, MSG_NIGHT_ACTION
)

# Try to import colorama for colored output; fall back gracefully
try:
    from colorama import init as colorama_init, Fore, Style
    colorama_init()
    HAS_COLOR = True
except ImportError:
    HAS_COLOR = False
    # Stub out color codes
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""


class GameClient:
    """
    TCP client that connects to a Terminal Mafia server.
    
    Provides methods to send messages and a background receiver
    that dispatches incoming messages to registered handlers.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, player_name: str = "Player"):
        self.host = host
        self.port = port
        self.player_name = player_name

        # Connection state
        self.sock = None
        self.connected = False
        self.player_id = None

        # Receiver thread
        self._recv_thread = None
        self._recv_buffer = ""

        # Lobby state (updated by server messages)
        self.lobby_players: list[str] = []
        self.lobby_can_start = False

        # Game state (updated by server messages)
        self.phase = PHASE_LOBBY
        self.role = None
        self.team = None
        self.is_alive = True
        self.alive_players: list[str] = []

        # Callbacks for message handling (set by the display/UI layer)
        self.on_message_handlers: dict[str, callable] = {}

    # ──────────────────────────────────────────
    # Connection
    # ──────────────────────────────────────────

    def connect(self) -> bool:
        """
        Connect to the game server and send JOIN message.
        
        Returns:
            True if connection and join succeeded, False otherwise.
        """
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10)
            self.sock.connect((self.host, self.port))
            self.connected = True

            # Start receiver thread
            self._recv_thread = threading.Thread(
                target=self._receive_loop, daemon=True, name="ClientRecv"
            )
            self._recv_thread.start()

            # Send JOIN
            self._send_raw(msg_join(self.player_name))
            return True

        except ConnectionRefusedError:
            self._print_error(f"Connection refused. Is the server running at {self.host}:{self.port}?")
            return False
        except socket.timeout:
            self._print_error(f"Connection timed out trying to reach {self.host}:{self.port}")
            return False
        except OSError as e:
            self._print_error(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from the server."""
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass

    # ──────────────────────────────────────────
    # Sending
    # ──────────────────────────────────────────

    def send_chat(self, message: str):
        """Send a chat message to the server."""
        if self.connected:
            self._send_raw(msg_chat(message))

    def send_start_game(self):
        """Request the server to start the game."""
        if self.connected:
            self._send_raw(create_message(MSG_START_GAME))

    def send_vote(self, target_name: str):
        """Send a vote to eliminate a player during day voting."""
        if self.connected:
            self._send_raw(create_message(MSG_VOTE, {"target": target_name}))

    def send_night_action(self, target_name: str, action: str = "kill"):
        """Send a night action (e.g., Mafia kill vote)."""
        if self.connected:
            self._send_raw(create_message(MSG_NIGHT_ACTION, {
                "action": action,
                "target": target_name
            }))

    def _send_raw(self, message: str) -> bool:
        """Send a raw message string to the server."""
        if not self.connected or not self.sock:
            return False
        try:
            self.sock.sendall(message.encode("utf-8"))
            return True
        except (ConnectionResetError, BrokenPipeError, OSError):
            self.connected = False
            return False

    # ──────────────────────────────────────────
    # Receiving
    # ──────────────────────────────────────────

    def _receive_loop(self):
        """
        Background receiver loop. Reads from socket, parses messages,
        and dispatches to handlers.
        """
        self.sock.settimeout(2.0)

        while self.connected:
            try:
                data = self.sock.recv(BUFFER_SIZE)
                if not data:
                    # Server closed connection
                    break

                self._recv_buffer += data.decode("utf-8")
                messages = parse_messages(self._recv_buffer)

                if messages:
                    last_delim = self._recv_buffer.rfind(MESSAGE_DELIMITER)
                    if last_delim != -1:
                        self._recv_buffer = self._recv_buffer[last_delim + len(MESSAGE_DELIMITER):]

                    for msg in messages:
                        self._dispatch_message(msg)

            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                break

        self.connected = False
        self._print_system("Disconnected from server.")

    def _dispatch_message(self, msg: dict):
        """Route incoming server message to the appropriate handler."""
        msg_type = msg.get("type")
        data = msg.get("data", {})

        # Handle heartbeat internally
        if msg_type == MSG_PING:
            self._send_raw(msg_pong())
            return

        # Built-in handlers
        handler_map = {
            MSG_WELCOME: self._on_welcome,
            MSG_PLAYER_JOINED: self._on_player_joined,
            MSG_PLAYER_LEFT: self._on_player_left,
            MSG_LOBBY_STATUS: self._on_lobby_status,
            MSG_CHAT_MSG: self._on_chat_msg,
            MSG_ERROR: self._on_error,
            MSG_SERVER_MSG: self._on_server_msg,
            MSG_ROLE_ASSIGN: self._on_role_assign,
            MSG_PHASE_CHANGE: self._on_phase_change,
            MSG_NIGHT_RESULT: self._on_night_result,
            MSG_VOTE_RESULT: self._on_vote_result,
            MSG_GAME_OVER: self._on_game_over,
            MSG_PLAYER_LIST: self._on_player_list,
        }

        handler = handler_map.get(msg_type)
        if handler:
            handler(data)

        # Also call any externally registered handler
        if msg_type in self.on_message_handlers:
            self.on_message_handlers[msg_type](data)

    # ──────────────────────────────────────────
    # Built-in Message Handlers
    # ──────────────────────────────────────────

    def _on_welcome(self, data: dict):
        """Handle WELCOME — server accepted our join."""
        self.player_id = data.get("player_id")
        name = data.get("player_name", self.player_name)
        self.player_name = name
        self._print_system(f"Welcome to Terminal Mafia, {Fore.GREEN}{Style.BRIGHT}{name}{Style.RESET_ALL}!")
        self._print_system(f"Your player ID: {Fore.CYAN}{self.player_id}{Style.RESET_ALL}")

    def _on_player_joined(self, data: dict):
        """Handle PLAYER_JOINED — another player entered the lobby."""
        name = data.get("player_name", "???")
        count = data.get("player_count", "?")
        plural = "player" if count == 1 else "players"
        self._print_system(
            f"{Fore.GREEN}➕ {name}{Style.RESET_ALL} joined the lobby "
            f"({count} {plural} joined)"
        )

    def _on_player_left(self, data: dict):
        """Handle PLAYER_LEFT — a player disconnected."""
        name = data.get("player_name", "???")
        count = data.get("player_count", "?")
        self._print_system(
            f"{Fore.RED}➖ {name}{Style.RESET_ALL} left the lobby "
            f"({count} players remaining)"
        )

    def _on_lobby_status(self, data: dict):
        """Handle LOBBY_STATUS — update local lobby state."""
        self.lobby_players = data.get("players", [])
        self.lobby_can_start = data.get("can_start", False)
        count = data.get("player_count", 0)
        min_p = data.get("min_players", 4)
        max_p = data.get("max_players", 10)

        print()
        print(f"  {Style.BRIGHT}📋 LOBBY ({count}/{max_p}){Style.RESET_ALL}")
        print(f"  {'─' * 30}")
        for i, name in enumerate(self.lobby_players, 1):
            marker = f"{Fore.YELLOW}★{Style.RESET_ALL}" if name == self.player_name else " "
            print(f"  {marker} {i}. {name}")
        print(f"  {'─' * 30}")
        if self.lobby_can_start:
            print(f"  {Fore.GREEN}✅ Ready to start! Type /start to begin.{Style.RESET_ALL}")
        else:
            need = min_p - count
            print(f"  {Fore.YELLOW}⏳ Waiting for {need} more player(s)...{Style.RESET_ALL}")
        print()

    def _on_chat_msg(self, data: dict):
        """Handle CHAT_MSG — display a chat message."""
        sender = data.get("from", "???")
        message = data.get("message", "")

        if sender == self.player_name:
            color = Fore.CYAN
        else:
            color = Fore.WHITE

        print(f"  {Style.DIM}[chat]{Style.RESET_ALL} {color}{Style.BRIGHT}{sender}{Style.RESET_ALL}: {message}")

    def _on_error(self, data: dict):
        """Handle ERROR — display error from server."""
        message = data.get("message", "Unknown error")
        self._print_error(message)

    def _on_server_msg(self, data: dict):
        """Handle SERVER_MSG — display a server announcement."""
        message = data.get("message", "")
        self._print_system(message)

    def _on_role_assign(self, data: dict):
        """Handle ROLE_ASSIGN — display the player's secret role."""
        self.role = data.get("role", "Unknown")
        self.team = data.get("team", "Unknown")
        description = data.get("description", "")
        teammates = data.get("teammates", [])

        role_color = Fore.RED if self.role == ROLE_MAFIA else Fore.GREEN

        print()
        print(f"  {'=' * 50}")
        print(f"  {Style.BRIGHT}YOUR SECRET ROLE{Style.RESET_ALL}")
        print(f"  {'=' * 50}")
        print(f"  Role: {role_color}{Style.BRIGHT}{self.role}{Style.RESET_ALL}")
        print(f"  Team: {role_color}{self.team}{Style.RESET_ALL}")
        print(f"  {Style.DIM}{description}{Style.RESET_ALL}")
        if teammates:
            print(f"  {Fore.RED}Your Mafia teammates: {', '.join(teammates)}{Style.RESET_ALL}")
        print(f"  {'=' * 50}")
        print()

    def _on_phase_change(self, data: dict):
        """Handle PHASE_CHANGE — display phase transition."""
        phase = data.get("phase", "")
        round_num = data.get("round", "?")
        duration = data.get("duration", "")
        alive_players = data.get("alive_players", [])
        self.phase = phase

        if alive_players:
            self.alive_players = alive_players

        print()
        if phase == "NIGHT":
            print(f"  {Fore.BLUE}{Style.BRIGHT}{'=' * 50}")
            print(f"  \U0001f319  NIGHT PHASE  \u2014  Round {round_num}")
            print(f"  {'=' * 50}{Style.RESET_ALL}")
            if duration:
                print(f"  {Style.DIM}Duration: {duration} seconds{Style.RESET_ALL}")
            if self.role == ROLE_MAFIA:
                print(f"  {Fore.RED}{Style.BRIGHT}Choose your target! Use: /kill <name>{Style.RESET_ALL}")
            else:
                print(f"  {Style.DIM}The town sleeps... wait for dawn.{Style.RESET_ALL}")

        elif phase == "DAWN":
            print(f"  {Fore.YELLOW}{Style.BRIGHT}{'=' * 50}")
            print(f"  \U0001f305  DAWN  \u2014  Round {round_num}")
            print(f"  {'=' * 50}{Style.RESET_ALL}")

        elif phase == "DISCUSSION":
            print(f"  {Fore.CYAN}{Style.BRIGHT}{'=' * 50}")
            print(f"  \U0001f4ac  DISCUSSION PHASE  \u2014  Round {round_num}")
            print(f"  {'=' * 50}{Style.RESET_ALL}")
            if duration:
                print(f"  {Style.DIM}Duration: {duration} seconds{Style.RESET_ALL}")
            if alive_players:
                print(f"  {Style.DIM}Alive: {', '.join(alive_players)}{Style.RESET_ALL}")
            print(f"  {Fore.CYAN}Discuss! Who do you think is Mafia?{Style.RESET_ALL}")

        elif phase == "VOTING":
            print(f"  {Fore.YELLOW}{Style.BRIGHT}{'=' * 50}")
            print(f"  \U0001f5f3\ufe0f  VOTING PHASE  \u2014  Round {round_num}")
            print(f"  {'=' * 50}{Style.RESET_ALL}")
            if duration:
                print(f"  {Style.DIM}Duration: {duration} seconds{Style.RESET_ALL}")
            if alive_players:
                print(f"  {Style.DIM}Alive: {', '.join(alive_players)}{Style.RESET_ALL}")
            print(f"  {Fore.YELLOW}Vote to eliminate! Use: /vote <name>{Style.RESET_ALL}")
        print()

    def _on_night_result(self, data: dict):
        """Handle NIGHT_RESULT — display who was killed at night."""
        message = data.get("message", "")
        killed = data.get("killed")

        print()
        if killed:
            print(f"  {Fore.RED}{Style.BRIGHT}{message}{Style.RESET_ALL}")
        else:
            print(f"  {Fore.GREEN}{Style.BRIGHT}{message}{Style.RESET_ALL}")
        print()

    def _on_vote_result(self, data: dict):
        """Handle VOTE_RESULT — display voting outcome."""
        message = data.get("message", "")
        eliminated = data.get("eliminated")
        vote_tally = data.get("vote_tally", {})
        individual_votes = data.get("individual_votes", {})
        is_tie = data.get("is_tie", False)

        print()
        print(f"  {'\u2500' * 40}")
        if eliminated:
            print(f"  {Fore.RED}{Style.BRIGHT}{message}{Style.RESET_ALL}")
        elif is_tie:
            print(f"  {Fore.YELLOW}{Style.BRIGHT}{message}{Style.RESET_ALL}")
        else:
            print(f"  {Style.DIM}{message}{Style.RESET_ALL}")

        # Show vote breakdown
        if vote_tally:
            print(f"  {Style.DIM}Vote tally:{Style.RESET_ALL}")
            for target, count in sorted(vote_tally.items(), key=lambda x: -x[1]):
                bar = '\u2588' * count
                print(f"    {target}: {bar} ({count})")
        if individual_votes:
            print(f"  {Style.DIM}Individual votes:{Style.RESET_ALL}")
            for voter, target in individual_votes.items():
                print(f"    {voter} \u2192 {target}")
        print(f"  {'\u2500' * 40}")
        print()

    def _on_game_over(self, data: dict):
        """Handle GAME_OVER — display winner and full role reveal."""
        winner = data.get("winner", "?")
        reason = data.get("reason", "")
        roles = data.get("roles", {})
        rounds_played = data.get("rounds_played", 0)
        elimination_log = data.get("elimination_log", [])

        winner_color = Fore.GREEN if winner == "Town" else Fore.RED

        print()
        print(f"  {Style.BRIGHT}{'\u2550' * 50}{Style.RESET_ALL}")
        print(f"  {Style.BRIGHT}\U0001f3c6  GAME OVER  \U0001f3c6{Style.RESET_ALL}")
        print(f"  {Style.BRIGHT}{'\u2550' * 50}{Style.RESET_ALL}")
        print(f"  Winner: {winner_color}{Style.BRIGHT}{winner}{Style.RESET_ALL}")
        print(f"  {reason}")
        print(f"  Rounds played: {rounds_played}")
        print()

        # Role reveal
        print(f"  {Style.BRIGHT}All Roles:{Style.RESET_ALL}")
        print(f"  {'\u2500' * 40}")
        for name, info in roles.items():
            role = info.get('role', '?')
            survived = info.get('survived', False)
            role_color = Fore.RED if role == ROLE_MAFIA else Fore.GREEN
            status = f"{Fore.GREEN}survived{Style.RESET_ALL}" if survived else f"{Fore.RED}eliminated{Style.RESET_ALL}"
            print(f"    {name}: {role_color}{role}{Style.RESET_ALL} ({status})")
        print(f"  {'\u2500' * 40}")

        # Elimination timeline
        if elimination_log:
            print(f"\n  {Style.BRIGHT}Elimination Timeline:{Style.RESET_ALL}")
            for entry in elimination_log:
                phase_icon = "\U0001f319" if entry.get('phase') == 'night' else "\u2600\ufe0f"
                print(f"    {phase_icon} Round {entry.get('round', '?')}: "
                      f"{entry.get('eliminated', '?')} ({entry.get('role', '?')})")
        print()

        self.phase = PHASE_LOBBY
        self.role = None
        self.is_alive = True

    def _on_player_list(self, data: dict):
        """Handle PLAYER_LIST — display target list for voting/night actions."""
        players = data.get("players", [])
        context = data.get("context", "")

        if context == "night_targets":
            print(f"  {Fore.RED}{Style.BRIGHT}Choose your target:{Style.RESET_ALL}")
            for i, p in enumerate(players, 1):
                print(f"    {i}. {p.get('name', '?')}")
            print(f"  {Style.DIM}Use: /kill <name>{Style.RESET_ALL}")
        elif context == "vote_targets":
            print(f"  {Fore.YELLOW}{Style.BRIGHT}Vote to eliminate:{Style.RESET_ALL}")
            for i, p in enumerate(players, 1):
                print(f"    {i}. {p.get('name', '?')}")
            print(f"  {Style.DIM}Use: /vote <name>{Style.RESET_ALL}")
        print()

    # ──────────────────────────────────────────
    # Output Helpers
    # ──────────────────────────────────────────

    def _print_system(self, text: str):
        """Print a system/server message with formatting."""
        print(f"  {Fore.MAGENTA}[server]{Style.RESET_ALL} {text}")

    def _print_error(self, text: str):
        """Print an error message with formatting."""
        print(f"  {Fore.RED}[error]{Style.RESET_ALL} {text}")
