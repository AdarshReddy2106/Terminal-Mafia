"""
client.py — TCP Game Client for Terminal Mafia

Handles:
- Connecting to the game server via TCP
- Sending JOIN, CHAT, and other messages
- Receiving and dispatching server messages in a background thread
- Heartbeat (PONG) responses to keep connection alive
- Rich terminal UI with ASCII art, colors, and narrative text
"""

import socket
import threading
import sys
import time
from collections import Counter

from common.constants import (
    BUFFER_SIZE, MESSAGE_DELIMITER, DEFAULT_HOST, DEFAULT_PORT,
    PHASE_LOBBY, PHASE_NIGHT, PHASE_DAWN, PHASE_DISCUSSION,
    PHASE_VOTING, PHASE_GAME_OVER, ROLE_MAFIA
)
from common.protocol import (
    parse_messages, msg_join, msg_chat, msg_pong, msg_last_words,
    create_message,
    MSG_WELCOME, MSG_PLAYER_JOINED, MSG_PLAYER_LEFT, MSG_PLAYER_LIST,
    MSG_LOBBY_STATUS, MSG_CHAT_MSG, MSG_ERROR, MSG_PING,
    MSG_SERVER_MSG, MSG_PHASE_CHANGE, MSG_ROLE_ASSIGN,
    MSG_VOTE_RESULT, MSG_NIGHT_RESULT, MSG_GAME_OVER,
    MSG_START_GAME, MSG_VOTE, MSG_NIGHT_ACTION,
    MSG_LAST_WORDS, MSG_LAST_WORDS_BROADCAST, MSG_SUSPICION_DATA
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
        LIGHTBLACK_EX = LIGHTRED_EX = LIGHTYELLOW_EX = LIGHTCYAN_EX = ""
        LIGHTGREEN_EX = LIGHTMAGENTA_EX = LIGHTBLUE_EX = LIGHTWHITE_EX = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

# Import display engine
from client.display import (
    clear_screen, terminal_bell, typewriter, glitch_effect,
    show_night_banner, show_dawn_banner, show_discussion_banner,
    show_voting_banner, show_role_reveal, show_night_kill,
    show_no_kill, show_vote_result, show_game_over,
    show_target_list, show_suspicion_meter, show_last_words,
    show_lobby, show_countdown_warning, ROLE_COLORS
)


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
        self.current_round = 0

        # Target lists for number-based voting
        self._night_targets: list[dict] = []
        self._vote_targets: list[dict] = []

        # Chat tracking for suspicion meter
        self._chat_log: list[dict] = []

        # Last words state
        self._awaiting_last_words = False
        self._last_words_name = ""

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

    def send_vote(self, target: str):
        """
        Send a vote to eliminate a player during day voting.
        Supports both name and number-based targeting.
        """
        if self.connected:
            target_name = self._resolve_target(target, self._vote_targets)
            self._send_raw(create_message(MSG_VOTE, {"target": target_name}))

    def send_night_action(self, target: str, action: str = "kill"):
        """
        Send a night action (e.g., Mafia kill vote).
        Supports both name and number-based targeting.
        """
        if self.connected:
            target_name = self._resolve_target(target, self._night_targets)
            self._send_raw(create_message(MSG_NIGHT_ACTION, {
                "action": action,
                "target": target_name
            }))

    def send_last_words(self, message: str):
        """Send last words after being eliminated."""
        if self.connected:
            self._send_raw(msg_last_words(message))
            self._awaiting_last_words = False

    def _resolve_target(self, target: str, target_list: list) -> str:
        """
        Resolve a target from name or number.
        
        If target is a digit, look up from the target list by index.
        Otherwise, do fuzzy name matching (prefix match).
        """
        target = target.strip()
        
        # Number-based selection
        if target.isdigit():
            idx = int(target) - 1
            if 0 <= idx < len(target_list):
                return target_list[idx].get("name", target)
            else:
                self._print_error(f"Invalid number. Choose 1-{len(target_list)}.")
                return target
        
        # Fuzzy name matching (case-insensitive prefix)
        if target_list:
            lower = target.lower()
            for p in target_list:
                name = p.get("name", "")
                if name.lower() == lower:
                    return name
                if name.lower().startswith(lower):
                    return name
        
        return target

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
            MSG_LAST_WORDS_BROADCAST: self._on_last_words_broadcast,
            MSG_SUSPICION_DATA: self._on_suspicion_data,
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

        show_lobby(
            players=self.lobby_players,
            player_name=self.player_name,
            can_start=self.lobby_can_start,
            player_count=count,
            min_players=min_p,
            max_players=max_p
        )

    def _on_chat_msg(self, data: dict):
        """Handle CHAT_MSG — display a chat message."""
        sender = data.get("from", "???")
        message = data.get("message", "")

        # Track chat for suspicion meter
        if self.phase == PHASE_DISCUSSION:
            self._chat_log.append({"from": sender, "message": message})

        # Color Mafia private chat differently
        if sender.startswith("[Mafia]"):
            color = Fore.RED
            prefix = f"{Fore.RED}{Style.BRIGHT}[🔪 mafia]{Style.RESET_ALL}"
        elif sender == self.player_name:
            color = Fore.CYAN
            prefix = f"{Style.DIM}[chat]{Style.RESET_ALL}"
        else:
            color = Fore.WHITE
            prefix = f"{Style.DIM}[chat]{Style.RESET_ALL}"

        print(f"  {prefix} {color}{Style.BRIGHT}{sender}{Style.RESET_ALL}: {message}")

    def _on_error(self, data: dict):
        """Handle ERROR — display error from server."""
        message = data.get("message", "Unknown error")
        self._print_error(message)

    def _on_server_msg(self, data: dict):
        """Handle SERVER_MSG — display a server announcement."""
        message = data.get("message", "")
        
        # Check for countdown warnings
        if message.startswith("⏰"):
            # Parse seconds if possible for colored countdown
            for sec in [30, 15, 10, 5]:
                if f"{sec} seconds" in message:
                    show_countdown_warning(sec)
                    return
        
        self._print_system(message)

    def _on_role_assign(self, data: dict):
        """Handle ROLE_ASSIGN — display the player's secret role with dramatic reveal."""
        self.role = data.get("role", "Unknown")
        self.team = data.get("team", "Unknown")
        description = data.get("description", "")
        teammates = data.get("teammates", [])

        clear_screen()
        show_role_reveal(self.role, self.team, description, teammates)

    def _on_phase_change(self, data: dict):
        """Handle PHASE_CHANGE — display phase transition with full UI."""
        phase = data.get("phase", "")
        round_num = data.get("round", "?")
        duration = data.get("duration", 0)
        alive_players = data.get("alive_players", [])
        self.phase = phase
        self.current_round = round_num

        if alive_players:
            self.alive_players = alive_players

        if phase == "NIGHT":
            is_mafia = (self.role == ROLE_MAFIA)
            show_night_banner(round_num, duration, is_mafia)

        elif phase == "DAWN":
            show_dawn_banner(round_num)

        elif phase == "DISCUSSION":
            # Reset chat log for new discussion
            self._chat_log = []
            show_discussion_banner(round_num, duration, alive_players)

        elif phase == "VOTING":
            show_voting_banner(round_num, duration, alive_players)

    def _on_night_result(self, data: dict):
        """Handle NIGHT_RESULT — display who was killed at night with dramatic art."""
        killed = data.get("killed")
        killed_role = data.get("killed_role", "")

        if killed:
            show_night_kill(killed, killed_role)
            # Check if WE were killed
            if killed == self.player_name:
                self.is_alive = False
                print(f"  {Fore.RED}{Style.BRIGHT}💀 YOU HAVE BEEN ELIMINATED!{Style.RESET_ALL}")
                self._awaiting_last_words = True
                self._last_words_name = self.player_name
                print(f"  {Fore.YELLOW}Type your last words (10 seconds)...{Style.RESET_ALL}")
        else:
            show_no_kill()

    def _on_vote_result(self, data: dict):
        """Handle VOTE_RESULT — display voting outcome with visuals."""
        eliminated = data.get("eliminated")
        eliminated_role = data.get("eliminated_role", "")
        vote_tally = data.get("vote_tally", {})
        individual_votes = data.get("individual_votes", {})
        is_tie = data.get("is_tie", False)

        show_vote_result(eliminated, eliminated_role,
                        vote_tally, individual_votes, is_tie)

        # Check if WE were eliminated
        if eliminated == self.player_name:
            self.is_alive = False
            print(f"  {Fore.RED}{Style.BRIGHT}💀 YOU HAVE BEEN ELIMINATED!{Style.RESET_ALL}")
            self._awaiting_last_words = True
            self._last_words_name = self.player_name
            print(f"  {Fore.YELLOW}Type your last words (10 seconds)...{Style.RESET_ALL}")

    def _on_game_over(self, data: dict):
        """Handle GAME_OVER — display winner and full role reveal."""
        winner = data.get("winner", "?")
        reason = data.get("reason", "")
        roles = data.get("roles", {})
        rounds_played = data.get("rounds_played", 0)
        elimination_log = data.get("elimination_log", [])

        show_game_over(winner, reason, roles, rounds_played, elimination_log)

        self.phase = PHASE_LOBBY
        self.role = None
        self.is_alive = True
        self._chat_log = []

    def _on_player_list(self, data: dict):
        """Handle PLAYER_LIST — display target list with numbers for easy voting."""
        players = data.get("players", [])
        context = data.get("context", "")

        # Store targets for number-based selection
        if context == "night_targets":
            self._night_targets = players
        elif context == "vote_targets":
            self._vote_targets = players

        show_target_list(players, context)

    def _on_last_words_broadcast(self, data: dict):
        """Handle LAST_WORDS_BROADCAST — display a dead player's last words."""
        name = data.get("player_name", "???")
        message = data.get("message", "")
        show_last_words(name, message)

    def _on_suspicion_data(self, data: dict):
        """Handle SUSPICION_DATA — display the suspicion meter."""
        mention_counts = data.get("mention_counts", {})
        show_suspicion_meter(mention_counts)

    # ──────────────────────────────────────────
    # Suspicion Tracking (client-side)
    # ──────────────────────────────────────────

    def get_suspicion_counts(self) -> dict:
        """
        Count name mentions in chat log for local suspicion meter.
        Returns dict of player_name -> mention_count.
        """
        counts = Counter()
        for player in self.alive_players:
            if player == self.player_name:
                continue  # Don't count self-mentions
            for entry in self._chat_log:
                msg = entry.get("message", "").lower()
                sender = entry.get("from", "")
                # Don't count the player mentioning their own name
                if sender != player and player.lower() in msg:
                    counts[player] += 1
        
        # Include players with 0 mentions
        for player in self.alive_players:
            if player != self.player_name and player not in counts:
                counts[player] = 0
        
        return dict(counts)

    # ──────────────────────────────────────────
    # Context-Aware Input Prompt
    # ──────────────────────────────────────────

    def get_input_prompt(self) -> str:
        """Get the appropriate input prompt based on current game state."""
        if self._awaiting_last_words:
            return f"  {Fore.RED}💀 Last words > {Style.RESET_ALL}"
        
        if not self.is_alive:
            return f"  {Style.DIM}👻 (spectating) > {Style.RESET_ALL}"
        
        if self.phase == PHASE_LOBBY:
            return f"  {Fore.GREEN}🎭 > {Style.RESET_ALL}"
        elif self.phase == PHASE_NIGHT:
            if self.role == ROLE_MAFIA:
                return f"  {Fore.RED}🔪 > {Style.RESET_ALL}"
            else:
                return f"  {Style.DIM}💤 > {Style.RESET_ALL}"
        elif self.phase == PHASE_DISCUSSION:
            return f"  {Fore.CYAN}💬 > {Style.RESET_ALL}"
        elif self.phase == PHASE_VOTING:
            return f"  {Fore.YELLOW}🗳️  > {Style.RESET_ALL}"
        
        return f"  > "

    # ──────────────────────────────────────────
    # Output Helpers
    # ──────────────────────────────────────────

    def _print_system(self, text: str):
        """Print a system/server message with formatting."""
        print(f"  {Fore.MAGENTA}[server]{Style.RESET_ALL} {text}")

    def _print_error(self, text: str):
        """Print an error message with formatting."""
        print(f"  {Fore.RED}[error]{Style.RESET_ALL} {text}")
