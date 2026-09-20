"""
server.py — TCP Game Server for Terminal Mafia

Handles:
- Accepting client connections via TCP sockets
- Threading: one thread per client for receiving messages
- Lobby management: tracking connected players, broadcasting updates
- Disconnect detection and graceful cleanup
- Message routing to the appropriate handler
"""

import socket
import threading
import time
import json
import random

from common.constants import (
    DEFAULT_HOST, DEFAULT_PORT, BUFFER_SIZE, MESSAGE_DELIMITER,
    MIN_PLAYERS, MAX_PLAYERS, PHASE_LOBBY, PHASE_GAME_OVER
)
from common.protocol import (
    parse_messages, msg_welcome, msg_player_joined, msg_player_left,
    msg_lobby_status, msg_error, msg_server_announcement, msg_ping,
    MSG_JOIN, MSG_CHAT, MSG_PONG, MSG_START_GAME,
    MSG_VOTE, MSG_NIGHT_ACTION,
    create_message, MSG_CHAT_MSG,
    MSG_TASK_SUBMIT
)
from common.utils import generate_player_id, sanitize_name, get_local_ip
from bots.bot_player import BotPlayer


class PlayerConnection:
    """Represents a connected player's socket and metadata."""

    def __init__(self, conn: socket.socket, addr: tuple, player_id: str):
        self.conn = conn
        self.addr = addr
        self.player_id = player_id
        self.name = None          # Set after JOIN message
        self.is_alive = True      # Game status (alive/eliminated)
        self.role = None          # Assigned during game start
        self.joined = False       # True after successful JOIN handshake
        self.last_pong = time.time()
        self._recv_buffer = ""    # Partial message buffer for TCP stream reassembly
        self._lock = threading.Lock()

    def send(self, message: str) -> bool:
        """
        Send a message string to this player's socket.
        Thread-safe via lock.
        
        Returns:
            True if sent successfully, False if connection is broken.
        """
        with self._lock:
            try:
                self.conn.sendall(message.encode("utf-8"))
                return True
            except (ConnectionResetError, BrokenPipeError, OSError):
                return False

    def close(self):
        """Close the socket connection."""
        try:
            self.conn.close()
        except OSError:
            pass

    def __repr__(self):
        return f"Player({self.name or 'unnamed'}, id={self.player_id})"


class GameServer:
    """
    The main TCP game server.
    
    Manages the lobby, accepts connections, handles message routing,
    and provides broadcast/unicast messaging to connected clients.
    """

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT,
                 min_players: int = MIN_PLAYERS, max_players: int = MAX_PLAYERS):
        self.host = host
        self.port = port
        self.min_players = min_players
        self.max_players = max_players

        # Server socket
        self.server_socket = None

        # Connected players: player_id -> PlayerConnection
        self.players: dict[str, PlayerConnection] = {}
        self.players_lock = threading.RLock()

        # Game state
        self.phase = PHASE_LOBBY
        self.running = False

        # Game engine (initialized on first game start)
        self.game_engine = None

        # Heartbeat
        self._heartbeat_thread = None
        self._accept_thread = None

    # ──────────────────────────────────────────
    # Server Lifecycle
    # ──────────────────────────────────────────

    def start(self):
        """Initialize the server socket, start accepting connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(self.max_players + 2)
        self.running = True

        local_ip = get_local_ip()

        print("=" * 56)
        print("       🎭  TERMINAL MAFIA — SERVER STARTED  🎭")
        print("=" * 56)
        print(f"  LAN IP   : {local_ip}")
        print(f"  Port     : {self.port}")
        print(f"  Players  : {self.min_players}–{self.max_players}")
        print("-" * 56)
        print(f"  Players should connect with:")
        print(f"    python run_client.py --host {local_ip} --port {self.port}")
        print("=" * 56)
        print()

        # Start accept thread
        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="AcceptThread"
        )
        self._accept_thread.start()

        # Start heartbeat thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="HeartbeatThread"
        )
        self._heartbeat_thread.start()

    def stop(self):
        """Shut down the server and disconnect all clients."""
        self.running = False
        print("\n[Server] Shutting down...")

        with self.players_lock:
            for player in list(self.players.values()):
                player.send(msg_server_announcement("Server is shutting down."))
                player.close()
            self.players.clear()

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass

        print("[Server] Stopped.")

    def add_bot(self, name: str, model: str = "google/gemma-4-31b-it:free"):
        """Add an LLM-powered bot player to the server."""
        if self.phase != PHASE_LOBBY:
            return False

        with self.players_lock:
            if len(self.players) >= self.max_players:
                return False

            bot_id = generate_player_id()
            bot = BotPlayer(self, bot_id, name, model)
            
            self.players[bot_id] = bot
            player_count = len(self.players)

        print(f"[Server] 🤖 Bot {name} joined the lobby! ({player_count}/{self.max_players})")
        
        # Broadcast to everyone
        self.broadcast(msg_player_joined(name, player_count, self.min_players))
        self._broadcast_lobby_status()
        return True

    # ──────────────────────────────────────────
    # Connection Management
    # ──────────────────────────────────────────

    def _accept_loop(self):
        """Continuously accept new TCP connections."""
        while self.running:
            try:
                self.server_socket.settimeout(1.0)
                try:
                    conn, addr = self.server_socket.accept()
                except socket.timeout:
                    continue

                player_id = generate_player_id()
                player = PlayerConnection(conn, addr, player_id)

                print(f"[Server] New connection from {addr[0]}:{addr[1]} (id: {player_id})")

                # Start a receiver thread for this client
                thread = threading.Thread(
                    target=self._client_receiver,
                    args=(player,),
                    daemon=True,
                    name=f"Recv-{player_id}"
                )
                thread.start()

            except OSError:
                if self.running:
                    print("[Server] Error accepting connection.")
                break

    def _client_receiver(self, player: PlayerConnection):
        """
        Receive loop for a single client.
        Runs in its own thread. Handles TCP stream reassembly,
        message parsing, and dispatching to handlers.
        """
        conn = player.conn
        conn.settimeout(5.0)  # Timeout for recv, allows periodic disconnect checking

        while self.running:
            try:
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    # Client disconnected cleanly
                    break

                # Append to buffer and process complete messages
                player._recv_buffer += data.decode("utf-8")
                messages = parse_messages(player._recv_buffer)

                if messages:
                    # Find the last complete message boundary to keep partial data
                    last_delim = player._recv_buffer.rfind(MESSAGE_DELIMITER)
                    if last_delim != -1:
                        player._recv_buffer = player._recv_buffer[last_delim + len(MESSAGE_DELIMITER):]
                    
                    for msg in messages:
                        self._handle_message(player, msg)

            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                break

        # Client disconnected — cleanup
        self._handle_disconnect(player)

    def _handle_disconnect(self, player: PlayerConnection):
        """Handle a player disconnecting from the server."""
        player.close()

        joined = False
        name = ""
        player_count = 0

        with self.players_lock:
            if player.player_id in self.players:
                del self.players[player.player_id]
                joined = player.joined
                name = player.name
                player_count = len(self.players)
            else:
                return

        if joined and name:
            print(f"[Server] 💔 {name} disconnected. ({player_count} players remaining)")

            # Notify remaining players
            self.broadcast(msg_player_left(name, player_count))

            if self.phase == PHASE_LOBBY:
                # Send updated lobby status
                self._broadcast_lobby_status()
            elif self.phase != PHASE_GAME_OVER and self.game_engine:
                # Mid-game disconnect: mark player dead and check win
                self.game_engine.state.handle_player_disconnect(player.player_id)
                self.broadcast(msg_server_announcement(
                    f"💔 {name} has disconnected and is out of the game."
                ))
                win = self.game_engine.state.check_win_condition()
                if win:
                    self.game_engine._end_game()
        else:
            print(f"[Server] Connection from {player.addr[0]} dropped (never joined).")

    # ──────────────────────────────────────────
    # Message Handling
    # ──────────────────────────────────────────

    def _handle_message(self, player: PlayerConnection, msg: dict):
        """
        Route an incoming message to the appropriate handler.
        
        Args:
            player: The PlayerConnection that sent the message
            msg: Parsed message dict with 'type' and 'data' keys
        """
        msg_type = msg.get("type")
        data = msg.get("data", {})

        if msg_type == MSG_JOIN:
            self._handle_join(player, data)
        elif msg_type == MSG_CHAT:
            self._handle_chat(player, data)
        elif msg_type == MSG_PONG:
            player.last_pong = time.time()
        elif msg_type == MSG_START_GAME:
            self._handle_start_game(player)
        elif msg_type == MSG_VOTE:
            self._handle_vote(player, data)
        elif msg_type == MSG_NIGHT_ACTION:
            self._handle_night_action(player, data)
        elif msg_type == MSG_TASK_SUBMIT:
            self._handle_task_submit(player, data)
        else:
            # Unknown or not-yet-implemented message type
            player.send(msg_error(f"Unknown message type: {msg_type}"))

    def _handle_join(self, player: PlayerConnection, data: dict):
        """Handle a player's JOIN request."""
        name = data.get("name", "")
        name = sanitize_name(name)

        # Check if lobby is full
        with self.players_lock:
            if len(self.players) >= self.max_players:
                player.send(msg_error("Lobby is full. Cannot join."))
                player.close()
                return

            # Check for duplicate names
            for p in self.players.values():
                if p.name and p.name.lower() == name.lower():
                    name = f"{name}_{player.player_id[:3]}"
                    break

            # Register the player
            player.name = name
            player.joined = True
            self.players[player.player_id] = player
            player_count = len(self.players)

        print(f"[Server] ✅ {name} joined the lobby! ({player_count}/{self.max_players})")

        # Send welcome to the joining player
        player.send(msg_welcome(player.player_id, name))

        # Broadcast to everyone that a new player joined
        self.broadcast(msg_player_joined(name, player_count, self.min_players))

        # Send updated lobby status
        self._broadcast_lobby_status()

    def _handle_chat(self, player: PlayerConnection, data: dict):
        """Handle a chat message from a player — broadcast to all or route per game phase."""
        if not player.joined:
            return

        message = data.get("message", "").strip()
        if not message:
            return

        # Lobby admin commands
        if self.phase == PHASE_LOBBY and message.lower().startswith("/addbots "):
            try:
                count = int(message.split()[1])
                for i in range(count):
                    bot_name = f"Bot_{random.randint(100, 999)}"
                    self.add_bot(bot_name)
                player.send(msg_server_announcement(f"Added {count} bots."))
            except (IndexError, ValueError):
                player.send(msg_error("Usage: /addbots <number>"))
            return

        # During game, enforce phase-specific chat rules
        if self.game_engine and self.phase != PHASE_LOBBY:
            result = self.game_engine.handle_chat_in_game(player.player_id, message)
            if result == "MAFIA_CHAT":
                return  # Already handled by game engine (private Mafia chat)
            elif result is not None:
                player.send(msg_error(result))
                return

        # Normal broadcast (lobby or discussion phase)
        chat_msg = create_message(MSG_CHAT_MSG, {
            "from": player.name,
            "message": message
        })
        self.broadcast(chat_msg)

    def _handle_start_game(self, player: PlayerConnection):
        """Handle a request to start the game."""
        if self.phase != PHASE_LOBBY:
            player.send(msg_error("A game is already in progress!"))
            return

        with self.players_lock:
            player_count = len(self.players)

        if player_count < self.min_players:
            player.send(msg_error(
                f"Need at least {self.min_players} players to start. Currently {player_count}."
            ))
            return

        print(f"[Server] 🎮 Game start requested by {player.name} with {player_count} players.")

        # Initialize and start the game engine
        from server.game_engine import GameEngine
        self.game_engine = GameEngine(self)
        if not self.game_engine.start_game():
            player.send(msg_error("Failed to start game. Not enough players."))
            self.game_engine = None
            return

    def _handle_vote(self, player: PlayerConnection, data: dict):
        """Handle a VOTE message during day voting phase."""
        if not self.game_engine:
            player.send(msg_error("No game in progress."))
            return

        error = self.game_engine.handle_vote(player.player_id, data)
        if error:
            player.send(msg_error(error))

    def _handle_night_action(self, player: PlayerConnection, data: dict):
        """Handle a NIGHT_ACTION message during night phase."""
        if not self.game_engine:
            player.send(msg_error("No game in progress."))
            return

        action = data.get("action", "")
        error = self.game_engine.handle_night_action(player.player_id, data)

        if error:
            player.send(msg_error(error))

    def _handle_task_submit(self, player: PlayerConnection, data: dict):
        """Handle a TASK_SUBMIT message — player submitting a task answer."""
        if not self.game_engine:
            player.send(msg_error("No game in progress."))
            return

        error = self.game_engine.handle_task_submit(player.player_id, data)
        if error:
            player.send(msg_error(error))


    # ──────────────────────────────────────────
    # Broadcasting
    # ──────────────────────────────────────────

    def broadcast(self, message: str, exclude: PlayerConnection = None):
        """
        Send a message to all connected, joined players.
        
        Args:
            message: The JSON message string to send
            exclude: Optionally exclude one player (e.g., the sender)
        """
        with self.players_lock:
            for player in list(self.players.values()):
                if player.joined and player != exclude:
                    if not player.send(message):
                        # Failed to send — will be cleaned up by receiver thread
                        pass

    def send_to_player(self, player_id: str, message: str) -> bool:
        """Send a message to a specific player by ID."""
        with self.players_lock:
            player = self.players.get(player_id)
        if player:
            return player.send(message)
        return False

    def _broadcast_lobby_status(self):
        """Send current lobby status to all players."""
        with self.players_lock:
            player_names = [p.name for p in self.players.values() if p.joined]
            player_count = len(player_names)

        status = msg_lobby_status(
            player_count, self.min_players, self.max_players, player_names
        )
        self.broadcast(status)

    # ──────────────────────────────────────────
    # Heartbeat / Disconnect Detection
    # ──────────────────────────────────────────

    def _heartbeat_loop(self):
        """
        Periodically ping all clients to detect silent disconnects.
        Runs in its own daemon thread.
        """
        while self.running:
            time.sleep(15)  # Ping every 15 seconds
            if not self.running:
                break

            ping = msg_ping()
            now = time.time()

            with self.players_lock:
                stale_players = []
                for player in list(self.players.values()):
                    if player.joined:
                        # Check if player has responded to the last ping
                        if now - player.last_pong > 45:
                            stale_players.append(player)
                        else:
                            player.send(ping)

            # Disconnect stale players outside the lock
            for player in stale_players:
                print(f"[Server] ⏰ {player.name} timed out (no heartbeat).")
                self._handle_disconnect(player)

    # ──────────────────────────────────────────
    # Utility
    # ──────────────────────────────────────────

    def get_player_count(self) -> int:
        """Get number of connected, joined players."""
        with self.players_lock:
            return sum(1 for p in self.players.values() if p.joined)

    def get_player_names(self) -> list[str]:
        """Get list of all joined player names."""
        with self.players_lock:
            return [p.name for p in self.players.values() if p.joined]
