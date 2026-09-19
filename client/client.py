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

from common.constants import BUFFER_SIZE, MESSAGE_DELIMITER, DEFAULT_HOST, DEFAULT_PORT
from common.protocol import (
    parse_messages, msg_join, msg_chat, msg_pong,
    create_message,
    MSG_WELCOME, MSG_PLAYER_JOINED, MSG_PLAYER_LEFT, MSG_PLAYER_LIST,
    MSG_LOBBY_STATUS, MSG_CHAT_MSG, MSG_ERROR, MSG_PING,
    MSG_SERVER_MSG, MSG_PHASE_CHANGE, MSG_ROLE_ASSIGN,
    MSG_VOTE_RESULT, MSG_NIGHT_RESULT, MSG_GAME_OVER,
    MSG_START_GAME
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
        min_p = data.get("min_players", "?")
        self._print_system(
            f"{Fore.GREEN}➕ {name}{Style.RESET_ALL} joined the lobby "
            f"({count}/{min_p} players)"
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

    # ──────────────────────────────────────────
    # Output Helpers
    # ──────────────────────────────────────────

    def _print_system(self, text: str):
        """Print a system/server message with formatting."""
        print(f"  {Fore.MAGENTA}[server]{Style.RESET_ALL} {text}")

    def _print_error(self, text: str):
        """Print an error message with formatting."""
        print(f"  {Fore.RED}[error]{Style.RESET_ALL} {text}")
