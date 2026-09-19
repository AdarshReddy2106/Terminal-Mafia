"""
game_engine.py — Core game loop controller for Terminal Mafia

Orchestrates the full game lifecycle:
    Lobby → Role Assignment → [Night → Dawn → Discussion → Voting] → Game Over

Runs the game loop in its own thread, managing phase transitions,
timers, collecting votes/actions, and broadcasting results.

Supports special roles: Detective, Doctor, Double Agent
Supports spectator mode for eliminated players.
"""

import threading
import time

from common.constants import (
    PHASE_LOBBY, PHASE_NIGHT, PHASE_DAWN, PHASE_DISCUSSION,
    PHASE_VOTING, PHASE_GAME_OVER,
    NIGHT_PHASE_DURATION, DISCUSSION_PHASE_DURATION,
    VOTING_PHASE_DURATION, DAWN_REVEAL_DURATION,
    ROLE_MAFIA, ROLE_DETECTIVE, ROLE_DOCTOR, ROLE_DOUBLE_AGENT,
    TEAM_TOWN, TEAM_MAFIA
)
from common.protocol import (
    create_message, msg_server_announcement,
    MSG_ROLE_ASSIGN, MSG_PHASE_CHANGE, MSG_NIGHT_RESULT,
    MSG_VOTE_RESULT, MSG_GAME_OVER, MSG_CHAT_MSG, MSG_PLAYER_LIST,
    MSG_SUSPICION_DATA, MSG_INVESTIGATION_RESULT, MSG_SPECTATOR_START
)
from server.role_manager import assign_roles, get_role_description, get_team, has_night_action
from server.state_manager import GameState


class GameEngine:
    """
    The game loop controller.

    Works with the GameServer to:
    - Assign roles and notify players
    - Run timed phases (night, discussion, voting)
    - Collect and resolve votes (including Detective/Doctor actions)
    - Check win conditions after each elimination
    - Announce game over and reveal all roles
    - Manage spectator mode for eliminated players
    """

    def __init__(self, server):
        """
        Args:
            server: The GameServer instance (used for sending messages
                    and accessing player connections)
        """
        self.server = server
        self.state = GameState()
        self.phase = PHASE_LOBBY
        self._game_thread = None
        self._phase_event = threading.Event()  # Used to signal early phase completion
        self._chat_log: list[dict] = []  # Track chat messages for suspicion meter

    # ──────────────────────────────────────────
    # Game Start
    # ──────────────────────────────────────────

    def start_game(self) -> bool:
        """
        Initialize and start the game.

        Returns True if game started successfully, False if conditions not met.
        """
        with self.server.players_lock:
            player_ids = [
                pid for pid, p in self.server.players.items() if p.joined
            ]
            player_names = {
                pid: p.name for pid, p in self.server.players.items() if p.joined
            }

        if len(player_ids) < self.server.min_players:
            return False

        # Assign roles
        roles = assign_roles(player_ids)

        # Initialize game state
        self.state.initialize(roles, player_names)

        # Notify each player of their role privately
        self._send_role_assignments(roles, player_ids)

        # Update server phase
        self.phase = PHASE_NIGHT
        self.server.phase = PHASE_NIGHT

        print(f"[Game] Roles assigned. Starting game loop.")

        # Start the game loop in its own thread
        self._game_thread = threading.Thread(
            target=self._game_loop, daemon=True, name="GameLoop"
        )
        self._game_thread.start()

        return True

    def _send_role_assignments(self, roles: dict[str, str], player_ids: list[str]):
        """Send each player their role and relevant info (privately)."""
        # Find Mafia team members (Mafia + Double Agent know each other)
        mafia_team_ids = [pid for pid, role in roles.items()
                         if role in (ROLE_MAFIA, ROLE_DOUBLE_AGENT)]
        mafia_team_names = [self.state.get_name(pid) for pid in mafia_team_ids]

        for pid in player_ids:
            role = roles[pid]
            description = get_role_description(role)

            data = {
                "role": role,
                "team": get_team(role),
                "description": description,
            }

            # Mafia team members learn who their teammates are
            if role in (ROLE_MAFIA, ROLE_DOUBLE_AGENT):
                teammates = [self.state.get_name(mid) for mid in mafia_team_ids if mid != pid]
                data["teammates"] = teammates

            msg = create_message(MSG_ROLE_ASSIGN, data)
            self.server.send_to_player(pid, msg)

        # Also broadcast how many of each role exist (without revealing who)
        total = len(player_ids)
        mafia_count = sum(1 for r in roles.values() if get_team(r) == TEAM_MAFIA)
        town_count = total - mafia_count

        # Build role count summary
        role_counts = {}
        for role in roles.values():
            role_counts[role] = role_counts.get(role, 0) + 1

        role_summary = ", ".join(f"{count} {role}" for role, count in role_counts.items())

        self.server.broadcast(msg_server_announcement(
            f"Roles have been assigned! "
            f"{total} players: {town_count} Town vs {mafia_count} Mafia. "
            f"Roles in play: {role_summary}. "
            f"The game begins NOW!"
        ))

    # ──────────────────────────────────────────
    # Game Loop
    # ──────────────────────────────────────────

    def _game_loop(self):
        """
        Main game loop. Runs in its own thread.

        Repeats: Night → Dawn → Discussion → Voting
        until a win condition is met.
        """
        try:
            time.sleep(2)  # Brief pause after role reveal

            while self.phase != PHASE_GAME_OVER:
                self.state.increment_round()
                round_num = self.state.round_number

                print(f"\n[Game] ═══ Round {round_num} ═══")

                # ── NIGHT PHASE ──
                winner = self._run_night_phase(round_num)
                if winner:
                    break

                # ── DISCUSSION PHASE ──
                self._run_discussion_phase(round_num)

                # ── VOTING PHASE ──
                winner = self._run_voting_phase(round_num)
                if winner:
                    break

            # Game over
            self._end_game()

        except Exception as e:
            print(f"[Game] ERROR in game loop: {e}")
            import traceback
            traceback.print_exc()

    # ──────────────────────────────────────────
    # Night Phase
    # ──────────────────────────────────────────

    def _run_night_phase(self, round_num: int) -> dict | None:
        """
        Execute the night phase.

        - Broadcast PHASE_CHANGE to all
        - Mafia members choose a target (timed)
        - Detective investigates a player
        - Doctor protects a player
        - Resolve night kills (with Doctor save check)
        - Broadcast results

        Returns win_result dict if game is over, else None.
        """
        self.phase = PHASE_NIGHT
        self.server.phase = PHASE_NIGHT
        self.state.clear_night_votes()
        self._phase_event.clear()

        print(f"[Game] 🌙 Night Phase (Round {round_num})")

        # Notify all players
        self.server.broadcast(create_message(MSG_PHASE_CHANGE, {
            "phase": PHASE_NIGHT,
            "round": round_num,
            "duration": NIGHT_PHASE_DURATION
        }))

        # Send alive player list to Mafia for targeting
        alive_list = self.state.get_alive_player_list()
        mafia_members = self.state.get_alive_mafia()
        for mid in mafia_members:
            # Show Mafia who they can target (exclude fellow Mafia team)
            mafia_team = self.state.get_alive_mafia_team()
            targets = [p for p in alive_list if p["id"] not in mafia_team]
            self.server.send_to_player(mid, create_message(MSG_PLAYER_LIST, {
                "players": targets,
                "context": "night_targets"
            }))

        # Send target list to Detective (if alive)
        detective_id = self.state.get_alive_detective()
        if detective_id:
            # Detective can investigate anyone alive except themselves
            det_targets = [p for p in alive_list if p["id"] != detective_id]
            self.server.send_to_player(detective_id, create_message(MSG_PLAYER_LIST, {
                "players": det_targets,
                "context": "investigate_targets"
            }))

        # Send target list to Doctor (if alive)
        doctor_id = self.state.get_alive_doctor()
        if doctor_id:
            # Doctor can protect anyone alive (including themselves)
            self.server.send_to_player(doctor_id, create_message(MSG_PLAYER_LIST, {
                "players": alive_list,
                "context": "protect_targets"
            }))

        # Wait for night duration or until all night-role players have acted
        self._wait_for_phase(NIGHT_PHASE_DURATION, self._all_night_actions_done)

        # Resolve Detective investigation (send result privately BEFORE dawn)
        investigation = self.state.resolve_detective()
        if investigation:
            det_id = investigation["detective_id"]
            target_name = investigation["target_name"]
            result = investigation["result"]
            is_mafia = (result == TEAM_MAFIA)
            print(f"[Game] 🔍 Detective investigated {target_name}: {result}")

            self.server.send_to_player(det_id, create_message(MSG_INVESTIGATION_RESULT, {
                "target": target_name,
                "result": result,
                "is_mafia": is_mafia
            }))

        # Resolve night (with Doctor save check)
        night_result = self.state.resolve_night()

        # ── Dawn Reveal ──
        self.phase = PHASE_DAWN
        self.server.phase = PHASE_DAWN

        self.server.broadcast(create_message(MSG_PHASE_CHANGE, {
            "phase": PHASE_DAWN,
            "round": round_num,
        }))

        if night_result["saved"]:
            # Doctor saved someone!
            print(f"[Game] 💉 Doctor saved {night_result['saved_name']}!")
            self.server.broadcast(create_message(MSG_NIGHT_RESULT, {
                "killed": None,
                "killed_role": None,
                "saved": True,
                "saved_name": night_result["saved_name"],
                "message": (
                    f"🌅 Dawn breaks... The Mafia struck, but someone was saved! "
                    f"The Doctor's intervention kept everyone alive."
                )
            }))
        elif night_result["killed_name"]:
            killed_name = night_result["killed_name"]
            killed_role = night_result["killed_role"]
            print(f"[Game] 💀 Night kill: {killed_name} ({killed_role})")

            self.server.broadcast(create_message(MSG_NIGHT_RESULT, {
                "killed": killed_name,
                "killed_role": killed_role,
                "saved": False,
                "message": f"☠️  {killed_name} was found dead! They were a {killed_role}."
            }))

            # Send spectator mode to the killed player
            self._start_spectator(night_result["killed_id"])
        else:
            print(f"[Game] Night: No one was killed.")
            self.server.broadcast(create_message(MSG_NIGHT_RESULT, {
                "killed": None,
                "killed_role": None,
                "saved": False,
                "message": "🌅 The town wakes up... everyone survived the night!"
            }))

        time.sleep(DAWN_REVEAL_DURATION)

        # Check win condition after night kill
        win = self.state.check_win_condition()
        if win:
            return win

        return None

    def _all_night_actions_done(self) -> bool:
        """Check if all night-role players have submitted their actions."""
        with self.state.lock:
            # Check Mafia
            alive_mafia = [pid for pid, role in self.state.roles.items()
                          if role == ROLE_MAFIA and self.state.alive.get(pid, False)]
            if not all(mid in self.state.mafia_votes for mid in alive_mafia):
                return False

            # Check Detective
            for pid, role in self.state.roles.items():
                if role == ROLE_DETECTIVE and self.state.alive.get(pid, False):
                    if pid not in self.state.detective_target:
                        return False

            # Check Doctor
            for pid, role in self.state.roles.items():
                if role == ROLE_DOCTOR and self.state.alive.get(pid, False):
                    if pid not in self.state.doctor_target:
                        return False

            return True

    # ──────────────────────────────────────────
    # Discussion Phase
    # ──────────────────────────────────────────

    def _run_discussion_phase(self, round_num: int):
        """
        Execute the discussion phase.

        - Broadcast PHASE_CHANGE
        - Players can chat freely (handled by existing chat logic)
        - Timed — ends after DISCUSSION_PHASE_DURATION seconds
        """
        self.phase = PHASE_DISCUSSION
        self.server.phase = PHASE_DISCUSSION
        self._phase_event.clear()
        self._chat_log.clear()

        print(f"[Game] 💬 Discussion Phase (Round {round_num}) — {DISCUSSION_PHASE_DURATION}s")

        # Send alive player list to everyone
        alive_list = self.state.get_alive_player_list()

        self.server.broadcast(create_message(MSG_PHASE_CHANGE, {
            "phase": PHASE_DISCUSSION,
            "round": round_num,
            "duration": DISCUSSION_PHASE_DURATION,
            "alive_players": [p["name"] for p in alive_list]
        }))

        # Wait for discussion timer
        self._wait_for_phase(DISCUSSION_PHASE_DURATION)

        # Broadcast suspicion data (name mentions in chat)
        self._broadcast_suspicion_data()

    # ──────────────────────────────────────────
    # Voting Phase
    # ──────────────────────────────────────────

    def _run_voting_phase(self, round_num: int) -> dict | None:
        """
        Execute the voting phase.

        Returns win_result dict if game is over, else None.
        """
        self.phase = PHASE_VOTING
        self.server.phase = PHASE_VOTING
        self.state.clear_day_votes()
        self._phase_event.clear()

        print(f"[Game] 🗳️  Voting Phase (Round {round_num}) — {VOTING_PHASE_DURATION}s")

        alive_list = self.state.get_alive_player_list()

        self.server.broadcast(create_message(MSG_PHASE_CHANGE, {
            "phase": PHASE_VOTING,
            "round": round_num,
            "duration": VOTING_PHASE_DURATION,
            "alive_players": [p["name"] for p in alive_list]
        }))

        # Send voteable player list to each alive player
        alive_ids = self.state.get_alive_players()
        for pid in alive_ids:
            # Can vote for anyone alive except themselves
            targets = [p for p in alive_list if p["id"] != pid]
            self.server.send_to_player(pid, create_message(MSG_PLAYER_LIST, {
                "players": targets,
                "context": "vote_targets"
            }))

        # Wait for voting duration or until all alive players have voted
        self._wait_for_phase(VOTING_PHASE_DURATION, self._all_alive_voted)

        # Resolve votes
        vote_result = self.state.resolve_day_vote()

        # Broadcast results
        if vote_result["eliminated_name"]:
            print(f"[Game] ⚖️  Day vote: {vote_result['eliminated_name']} eliminated ({vote_result['eliminated_role']})")

            self.server.broadcast(create_message(MSG_VOTE_RESULT, {
                "eliminated": vote_result["eliminated_name"],
                "eliminated_role": vote_result["eliminated_role"],
                "vote_tally": vote_result["vote_tally"],
                "individual_votes": vote_result["individual_votes"],
                "is_tie": False,
                "message": (
                    f"⚖️  The town has spoken! {vote_result['eliminated_name']} "
                    f"has been eliminated. They were a {vote_result['eliminated_role']}."
                )
            }))

            # Send spectator mode to the eliminated player
            self._start_spectator(vote_result["eliminated_id"])

        elif vote_result["is_tie"]:
            print(f"[Game] ⚖️  Day vote: TIE — no elimination.")
            self.server.broadcast(create_message(MSG_VOTE_RESULT, {
                "eliminated": None,
                "eliminated_role": None,
                "vote_tally": vote_result["vote_tally"],
                "individual_votes": vote_result["individual_votes"],
                "is_tie": True,
                "message": "⚖️  It's a tie! No one was eliminated today."
            }))
        else:
            print(f"[Game] ⚖️  Day vote: No votes cast — no elimination.")
            self.server.broadcast(create_message(MSG_VOTE_RESULT, {
                "eliminated": None,
                "eliminated_role": None,
                "vote_tally": {},
                "individual_votes": {},
                "is_tie": False,
                "message": "🤷 No votes were cast. No one was eliminated."
            }))

        time.sleep(3)  # Pause to let players read results

        # Check win condition
        win = self.state.check_win_condition()
        if win:
            return win

        return None

    def _all_alive_voted(self) -> bool:
        """Check if all alive players have submitted a day vote."""
        alive = self.state.get_alive_players()
        with self.state.lock:
            return all(pid in self.state.day_votes for pid in alive)

    # ──────────────────────────────────────────
    # Spectator Mode
    # ──────────────────────────────────────────

    def _start_spectator(self, player_id: str):
        """Send spectator mode data to an eliminated player."""
        if not player_id:
            return

        summary = self.state.get_game_summary()

        self.server.send_to_player(player_id, create_message(MSG_SPECTATOR_START, {
            "roles": summary["roles"],
            "mafia_members": [self.state.get_name(pid) for pid in self.state.get_mafia_members()],
            "message": "You are now a spectator. You can see all roles and actions, but cannot interact."
        }))

    def _send_to_spectators(self, message: str):
        """Send a message to all dead (spectating) players."""
        dead_players = self.state.get_dead_players()
        for pid in dead_players:
            self.server.send_to_player(pid, message)

    # ──────────────────────────────────────────
    # Game Over
    # ──────────────────────────────────────────

    def _end_game(self):
        """Handle game over — announce winner, reveal all roles."""
        self.phase = PHASE_GAME_OVER
        self.server.phase = PHASE_GAME_OVER

        win_result = self.state.check_win_condition()
        summary = self.state.get_game_summary()

        if win_result:
            winner = win_result["winner"]
            reason = win_result["reason"]
            print(f"\n[Game] 🏆 GAME OVER — {winner} wins! {reason}")
        else:
            winner = "Unknown"
            reason = "Game ended."

        # Build role reveal
        role_reveal = {}
        for name, info in summary["roles"].items():
            role_reveal[name] = {
                "role": info["role"],
                "team": info["team"],
                "survived": info["survived"]
            }

        self.server.broadcast(create_message(MSG_GAME_OVER, {
            "winner": winner,
            "reason": reason,
            "roles": role_reveal,
            "rounds_played": summary["rounds_played"],
            "elimination_log": summary["elimination_log"],
            "detective_results": summary.get("detective_results", []),
            "doctor_saves": summary.get("doctor_saves", []),
        }))

        # Reset to lobby after a delay
        time.sleep(5)
        self.phase = PHASE_LOBBY
        self.server.phase = PHASE_LOBBY
        self.server.broadcast(msg_server_announcement(
            "Game over! Returning to lobby. Type /start to play again."
        ))

    # ──────────────────────────────────────────
    # Phase Timer Utility
    # ──────────────────────────────────────────

    def _wait_for_phase(self, duration: int, early_exit_check=None):
        """
        Wait for a phase duration, broadcasting countdown alerts.

        Optionally exits early if early_exit_check() returns True.
        """
        start_time = time.time()
        alerts_sent = set()

        while time.time() - start_time < duration:
            elapsed = time.time() - start_time
            remaining = duration - elapsed

            # Send countdown alerts at key intervals
            for alert_at in [30, 15, 10, 5]:
                if remaining <= alert_at and alert_at not in alerts_sent and remaining > alert_at - 1:
                    alerts_sent.add(alert_at)
                    self.server.broadcast(msg_server_announcement(
                        f"⏰ {alert_at} seconds remaining!"
                    ))

            # Check for early exit
            if early_exit_check and early_exit_check():
                self.server.broadcast(msg_server_announcement(
                    "All actions received! Moving on..."
                ))
                time.sleep(1)
                return

            # Check if phase was externally cancelled
            if self._phase_event.is_set():
                return

            time.sleep(0.5)

    # ──────────────────────────────────────────
    # External Action Handlers (called by server)
    # ──────────────────────────────────────────

    def handle_night_action(self, player_id: str, data: dict) -> str | None:
        """
        Process a night action from a player.
        Called by the server when it receives a NIGHT_ACTION message.

        Supports: Mafia kill, Detective investigate, Doctor protect

        Returns an error message string if invalid, else None.
        """
        if self.phase != PHASE_NIGHT:
            return "It's not night time!"

        action = data.get("action", "")
        target_name = data.get("target", "")

        if not target_name:
            return "You must specify a target."

        target_id = self.state.get_player_id_by_name(target_name)
        if not target_id:
            return f"Player '{target_name}' not found."

        if not self.state.is_alive(target_id):
            return f"{target_name} is already dead."

        role = self.state.get_role(player_id)

        # ── Mafia Kill ──
        if role == ROLE_MAFIA and action in ("kill", "vote", ""):
            if not self.state.add_mafia_vote(player_id, target_id):
                return "Invalid target. You can't target yourself or another Mafia member."

            voter_name = self.state.get_name(player_id)
            print(f"[Game] 🔪 {voter_name} (Mafia) voted to kill {target_name}")

            # Notify other Mafia team members of the vote
            mafia_team = self.state.get_alive_mafia_team()
            for mid in mafia_team:
                self.server.send_to_player(mid, create_message(MSG_CHAT_MSG, {
                    "from": f"[Mafia] {voter_name}",
                    "message": f"voted to kill {target_name}"
                }))

            # Also forward to spectators
            self._send_to_spectators(create_message(MSG_CHAT_MSG, {
                "from": f"[Mafia] {voter_name}",
                "message": f"voted to kill {target_name}"
            }))

            return None  # Success

        # ── Detective Investigate ──
        if role == ROLE_DETECTIVE and action in ("investigate", ""):
            if player_id == target_id:
                return "You can't investigate yourself."
            if not self.state.add_detective_action(player_id, target_id):
                return "Invalid investigation target."

            voter_name = self.state.get_name(player_id)
            print(f"[Game] 🔍 {voter_name} (Detective) investigating {target_name}")
            return None  # Success

        # ── Doctor Protect ──
        if role == ROLE_DOCTOR and action in ("protect", ""):
            if not self.state.add_doctor_action(player_id, target_id):
                return "Invalid protection target."

            voter_name = self.state.get_name(player_id)
            print(f"[Game] 💉 {voter_name} (Doctor) protecting {target_name}")
            return None  # Success

        # ── Double Agent (can chat with Mafia but no kill vote) ──
        if role == ROLE_DOUBLE_AGENT:
            return "As the Double Agent, you don't perform night actions. Chat with your Mafia allies!"

        return f"You can't perform that action as {role}."

    def handle_vote(self, player_id: str, data: dict) -> str | None:
        """
        Process a day vote from a player.
        Called by the server when it receives a VOTE message.

        Returns an error message string if invalid, else None.
        """
        if self.phase != PHASE_VOTING:
            return "Voting is not open right now!"

        target_name = data.get("target", "")
        if not target_name:
            return "You must specify who to vote for."

        target_id = self.state.get_player_id_by_name(target_name)
        if not target_id:
            return f"Player '{target_name}' not found."

        if not self.state.is_alive(target_id):
            return f"{target_name} is already dead."

        if not self.state.add_day_vote(player_id, target_id):
            return "Invalid vote. You can't vote for yourself."

        voter_name = self.state.get_name(player_id)
        print(f"[Game] 🗳️  {voter_name} voted to eliminate {target_name}")

        # Broadcast that this player has voted (but not who for — secret ballot)
        self.server.broadcast(msg_server_announcement(
            f"📩 {voter_name} has cast their vote."
        ))

        # Spectators see the actual vote
        self._send_to_spectators(create_message(MSG_CHAT_MSG, {
            "from": "[Spectator Info]",
            "message": f"{voter_name} voted for {target_name}"
        }))

        return None  # Success

    def handle_chat_in_game(self, player_id: str, message: str) -> str | None:
        """
        Validate chat during game phases.

        - During discussion: all alive players can chat
        - During night: only Mafia team can chat (to each other)
        - During voting: no chat
        - Dead players can't chat (they are spectating)
        """
        if not self.state.is_alive(player_id):
            return "You are dead. You cannot send messages."

        if self.phase == PHASE_DISCUSSION:
            # Normal broadcast chat (handled by server)
            self._chat_log.append({
                "from": self.state.get_name(player_id),
                "message": message
            })
            return None

        if self.phase == PHASE_NIGHT:
            role = self.state.get_role(player_id)
            if role in (ROLE_MAFIA, ROLE_DOUBLE_AGENT):
                # Mafia team private chat — send to all Mafia team members
                sender_name = self.state.get_name(player_id)
                mafia_team = self.state.get_alive_mafia_team()
                chat_msg = create_message(MSG_CHAT_MSG, {
                    "from": f"[Mafia] {sender_name}",
                    "message": message
                })
                for mid in mafia_team:
                    self.server.send_to_player(mid, chat_msg)

                # Also send to spectators
                self._send_to_spectators(chat_msg)

                return "MAFIA_CHAT"  # Signal to server: don't broadcast
            else:
                return "It's nighttime. Only Mafia can communicate."

        if self.phase == PHASE_VOTING:
            return "No chatting during voting! Cast your vote."

        return None

    # ──────────────────────────────────────────
    # Suspicion Data
    # ──────────────────────────────────────────

    def _broadcast_suspicion_data(self):
        """Calculate and broadcast suspicion data based on chat mentions."""
        from collections import Counter
        counts = Counter()
        alive_players = [p["name"] for p in self.state.get_alive_player_list()]

        for player in alive_players:
            for entry in self._chat_log:
                msg = entry.get("message", "").lower()
                sender = entry.get("from", "")
                if sender != player and player.lower() in msg:
                    counts[player] += 1

        # Include players with 0 mentions
        for player in alive_players:
            if player not in counts:
                counts[player] = 0

        self.server.broadcast(create_message(MSG_SUSPICION_DATA, {
            "mention_counts": dict(counts)
        }))
