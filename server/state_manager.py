"""
state_manager.py — Game state tracking for Terminal Mafia

Manages all mutable game state:
- Player alive/dead status
- Role assignments
- Vote collection and tallying
- Night action collection and resolution (Mafia kill, Detective, Doctor)
- Round tracking
- Win condition evaluation
- Match history for end-game summary
"""

import threading
from collections import Counter

from common.constants import (
    ROLE_MAFIA, ROLE_VILLAGER, ROLE_DETECTIVE, ROLE_DOCTOR, ROLE_DOUBLE_AGENT,
    TEAM_TOWN, TEAM_MAFIA
)
from server.role_manager import get_team


class GameState:
    """
    Thread-safe container for all game state.

    Tracks which players are alive, their roles, votes for
    each phase, and provides win-condition checking.
    """

    def __init__(self):
        self.lock = threading.Lock()

        # Player roles: player_id -> role string
        self.roles: dict[str, str] = {}

        # Alive status: player_id -> bool
        self.alive: dict[str, bool] = {}

        # Player names: player_id -> name string
        self.names: dict[str, str] = {}

        # Current round number (increments each full night+day cycle)
        self.round_number: int = 0

        # ── Night phase state ──
        # Mafia kill votes: voter_player_id -> target_player_id
        self.mafia_votes: dict[str, str] = {}
        # Detective investigation: detective_player_id -> target_player_id
        self.detective_target: dict[str, str] = {}
        # Doctor protection: doctor_player_id -> target_player_id
        self.doctor_target: dict[str, str] = {}

        # ── Day phase state ──
        # Day elimination votes: voter_player_id -> target_player_id
        self.day_votes: dict[str, str] = {}

        # ── History tracking (for end-game summary) ──
        self.elimination_log: list[dict] = []
        # Each entry: {"round": N, "phase": "night"/"day", "eliminated": name, "role": role, "votes": {...}}

        # ── Special role action history (for match history) ──
        self.detective_results: list[dict] = []
        # Each entry: {"round": N, "detective": name, "target": name, "result": "Town"/"Mafia"}
        self.doctor_saves: list[dict] = []
        # Each entry: {"round": N, "doctor": name, "saved": name}

    # ──────────────────────────────────────────
    # Initialization
    # ──────────────────────────────────────────

    def initialize(self, roles: dict[str, str], names: dict[str, str]):
        """
        Set up initial game state after roles are assigned.

        Args:
            roles: player_id -> role mapping
            names: player_id -> display name mapping
        """
        with self.lock:
            self.roles = dict(roles)
            self.names = dict(names)
            self.alive = {pid: True for pid in roles}
            self.round_number = 0
            self.mafia_votes.clear()
            self.detective_target.clear()
            self.doctor_target.clear()
            self.day_votes.clear()
            self.elimination_log.clear()
            self.detective_results.clear()
            self.doctor_saves.clear()

    # ──────────────────────────────────────────
    # Player Queries
    # ──────────────────────────────────────────

    def get_alive_players(self) -> list[str]:
        """Get list of player_ids who are still alive."""
        with self.lock:
            return [pid for pid, alive in self.alive.items() if alive]

    def get_alive_player_names(self) -> list[str]:
        """Get display names of alive players."""
        with self.lock:
            return [self.names[pid] for pid, alive in self.alive.items() if alive]

    def get_dead_players(self) -> list[str]:
        """Get list of player_ids who are eliminated."""
        with self.lock:
            return [pid for pid, alive in self.alive.items() if not alive]

    def is_alive(self, player_id: str) -> bool:
        """Check if a specific player is alive."""
        with self.lock:
            return self.alive.get(player_id, False)

    def get_role(self, player_id: str) -> str:
        """Get a player's role."""
        with self.lock:
            return self.roles.get(player_id, "Unknown")

    def get_name(self, player_id: str) -> str:
        """Get a player's display name."""
        with self.lock:
            return self.names.get(player_id, "Unknown")

    def get_mafia_members(self) -> list[str]:
        """Get player_ids of all Mafia team members (alive or dead), including Double Agent."""
        with self.lock:
            return [pid for pid, role in self.roles.items()
                    if role in (ROLE_MAFIA, ROLE_DOUBLE_AGENT)]

    def get_alive_mafia(self) -> list[str]:
        """Get player_ids of alive Mafia members (not Double Agent — they don't vote to kill)."""
        with self.lock:
            return [pid for pid, role in self.roles.items()
                    if role == ROLE_MAFIA and self.alive.get(pid, False)]

    def get_alive_mafia_team(self) -> list[str]:
        """Get player_ids of alive Mafia team (Mafia + Double Agent)."""
        with self.lock:
            return [pid for pid, role in self.roles.items()
                    if role in (ROLE_MAFIA, ROLE_DOUBLE_AGENT) and self.alive.get(pid, False)]

    def get_alive_town(self) -> list[str]:
        """Get player_ids of alive Town members."""
        with self.lock:
            return [pid for pid, role in self.roles.items()
                    if get_team(role) == TEAM_TOWN and self.alive.get(pid, False)]

    def get_player_id_by_name(self, name: str) -> str | None:
        """Look up a player_id from their display name (case-insensitive)."""
        with self.lock:
            for pid, pname in self.names.items():
                if pname.lower() == name.lower():
                    return pid
            return None

    def get_alive_player_list(self) -> list[dict]:
        """Get detailed list of alive players with their names and ids."""
        with self.lock:
            return [
                {"id": pid, "name": self.names[pid], "alive": True}
                for pid in self.alive if self.alive[pid]
            ]

    def get_alive_detective(self) -> str | None:
        """Get player_id of the alive Detective, or None."""
        with self.lock:
            for pid, role in self.roles.items():
                if role == ROLE_DETECTIVE and self.alive.get(pid, False):
                    return pid
            return None

    def get_alive_doctor(self) -> str | None:
        """Get player_id of the alive Doctor, or None."""
        with self.lock:
            for pid, role in self.roles.items():
                if role == ROLE_DOCTOR and self.alive.get(pid, False):
                    return pid
            return None

    # ──────────────────────────────────────────
    # Night Phase
    # ──────────────────────────────────────────

    def clear_night_votes(self):
        """Reset all night actions for a new night phase."""
        with self.lock:
            self.mafia_votes.clear()
            self.detective_target.clear()
            self.doctor_target.clear()

    def clear_doctor_target(self):
        """Reset the doctor's protection target."""
        with self.lock:
            self.doctor_target.clear()

    def add_mafia_vote(self, voter_id: str, target_id: str) -> bool:
        """
        Record a Mafia member's kill vote.

        Returns True if the vote was valid and recorded.
        """
        with self.lock:
            # Verify voter is alive Mafia
            if self.roles.get(voter_id) != ROLE_MAFIA or not self.alive.get(voter_id, False):
                return False
            # Verify target is alive
            if not self.alive.get(target_id, False):
                return False
            # Mafia can't target themselves
            if voter_id == target_id:
                return False
            self.mafia_votes[voter_id] = target_id
            return True

    def add_detective_action(self, detective_id: str, target_id: str) -> bool:
        """
        Record the Detective's investigation target.

        Returns True if valid.
        """
        with self.lock:
            if self.roles.get(detective_id) != ROLE_DETECTIVE:
                return False
            if not self.alive.get(detective_id, False):
                return False
            if not self.alive.get(target_id, False):
                return False
            if detective_id == target_id:
                return False
            self.detective_target[detective_id] = target_id
            return True

    def add_doctor_action(self, doctor_id: str, target_id: str) -> bool:
        """
        Record the Doctor's protection target.

        Returns True if valid. Doctor CAN protect themselves.
        """
        with self.lock:
            if self.roles.get(doctor_id) != ROLE_DOCTOR:
                return False
            if not self.alive.get(doctor_id, False):
                return False
            if not self.alive.get(target_id, False):
                return False
            self.doctor_target[doctor_id] = target_id
            return True

    def resolve_detective(self) -> dict | None:
        """
        Resolve the Detective's investigation.

        Returns dict with investigation result, or None if no investigation.
        Double Agent appears as "Town" to the Detective.
        """
        with self.lock:
            if not self.detective_target:
                return None

            for det_id, target_id in self.detective_target.items():
                target_role = self.roles.get(target_id, "Unknown")
                target_name = self.names.get(target_id, "Unknown")
                detective_name = self.names.get(det_id, "Unknown")

                # Double Agent appears as Town!
                if target_role == ROLE_DOUBLE_AGENT:
                    apparent_team = TEAM_TOWN
                else:
                    apparent_team = get_team(target_role)

                result = {
                    "detective_id": det_id,
                    "detective_name": detective_name,
                    "target_id": target_id,
                    "target_name": target_name,
                    "result": apparent_team,  # "Town" or "Mafia"
                }

                # Log for match history
                self.detective_results.append({
                    "round": self.round_number,
                    "detective": detective_name,
                    "target": target_name,
                    "result": apparent_team,
                })

                return result

        return None

    def resolve_night(self) -> dict:
        """
        Resolve the night phase — tally Mafia votes and determine the kill.
        Takes Doctor protection into account.

        Returns:
            dict with keys:
                "killed_id": player_id of victim (or None if saved/no kill)
                "killed_name": name of victim (or None)
                "killed_role": role of victim (or None)
                "saved": bool — True if Doctor saved the target
                "saved_name": name of player who was saved (or None)
                "votes": dict of voter_name -> target_name
        """
        with self.lock:
            result = {
                "killed_id": None,
                "killed_name": None,
                "killed_role": None,
                "saved": False,
                "saved_name": None,
                "votes": {}
            }

            if not self.mafia_votes:
                return result

            # Build readable vote log
            for voter_id, target_id in self.mafia_votes.items():
                result["votes"][self.names.get(voter_id, "?")] = self.names.get(target_id, "?")

            # Tally votes — most-voted target gets killed
            vote_counts = Counter(self.mafia_votes.values())
            if vote_counts:
                # Get the target with the most votes
                target_id, count = vote_counts.most_common(1)[0]

                # Check if Doctor protected this target
                protected_ids = set(self.doctor_target.values())
                if target_id in protected_ids:
                    # Doctor saved this player!
                    result["saved"] = True
                    result["saved_name"] = self.names.get(target_id, "Unknown")

                    # Log the save for match history
                    for doc_id, prot_id in self.doctor_target.items():
                        if prot_id == target_id:
                            self.doctor_saves.append({
                                "round": self.round_number,
                                "doctor": self.names.get(doc_id, "Unknown"),
                                "saved": self.names.get(target_id, "Unknown"),
                            })
                else:
                    # Kill the target
                    self.alive[target_id] = False
                    result["killed_id"] = target_id
                    result["killed_name"] = self.names.get(target_id, "Unknown")
                    result["killed_role"] = self.roles.get(target_id, "Unknown")

                    # Log the elimination
                    self.elimination_log.append({
                        "round": self.round_number,
                        "phase": "night",
                        "eliminated": result["killed_name"],
                        "role": result["killed_role"],
                        "votes": dict(result["votes"])
                    })

            return result

    # ──────────────────────────────────────────
    # Day Phase (Voting)
    # ──────────────────────────────────────────

    def clear_day_votes(self):
        """Reset day votes for a new voting phase."""
        with self.lock:
            self.day_votes.clear()

    def add_day_vote(self, voter_id: str, target_id: str) -> bool:
        """
        Record a player's elimination vote during day phase.

        Returns True if the vote was valid and recorded.
        """
        with self.lock:
            # Voter must be alive
            if not self.alive.get(voter_id, False):
                return False
            # Target must be alive
            if not self.alive.get(target_id, False):
                return False
            # Can't vote for yourself
            if voter_id == target_id:
                return False
            self.day_votes[voter_id] = target_id
            return True

    def resolve_day_vote(self) -> dict:
        """
        Resolve the day voting phase — tally votes and determine elimination.

        Handles ties: no one is eliminated on a tie.

        Returns:
            dict with keys:
                "eliminated_id": player_id (or None if tie/no votes)
                "eliminated_name": name (or None)
                "eliminated_role": role (or None)
                "vote_tally": dict of target_name -> vote_count
                "individual_votes": dict of voter_name -> target_name
                "is_tie": bool
        """
        with self.lock:
            result = {
                "eliminated_id": None,
                "eliminated_name": None,
                "eliminated_role": None,
                "vote_tally": {},
                "individual_votes": {},
                "is_tie": False
            }

            if not self.day_votes:
                return result

            # Build readable vote log
            for voter_id, target_id in self.day_votes.items():
                voter_name = self.names.get(voter_id, "?")
                target_name = self.names.get(target_id, "?")
                result["individual_votes"][voter_name] = target_name

            # Tally votes
            vote_counts = Counter(self.day_votes.values())
            for target_id, count in vote_counts.items():
                target_name = self.names.get(target_id, "?")
                result["vote_tally"][target_name] = count

            if not vote_counts:
                return result

            # Check for tie
            sorted_votes = vote_counts.most_common()
            top_count = sorted_votes[0][1]

            # If there's a tie at the top, no elimination
            tied = [pid for pid, count in sorted_votes if count == top_count]
            if len(tied) > 1:
                result["is_tie"] = True
                return result

            # Eliminate the player with the most votes
            target_id = sorted_votes[0][0]
            self.alive[target_id] = False
            result["eliminated_id"] = target_id
            result["eliminated_name"] = self.names.get(target_id, "Unknown")
            result["eliminated_role"] = self.roles.get(target_id, "Unknown")

            # Log the elimination
            self.elimination_log.append({
                "round": self.round_number,
                "phase": "day",
                "eliminated": result["eliminated_name"],
                "role": result["eliminated_role"],
                "votes": dict(result["individual_votes"])
            })

            return result

    # ──────────────────────────────────────────
    # Win Condition
    # ──────────────────────────────────────────

    def check_win_condition(self) -> dict | None:
        """
        Check if either team has won.

        Returns:
            dict with "winner" and "reason" if game is over, else None.

            Town wins: All Mafia team members are eliminated.
            Mafia wins: Mafia team equals or outnumbers Town.
        """
        with self.lock:
            alive_mafia = sum(
                1 for pid, role in self.roles.items()
                if get_team(role) == TEAM_MAFIA and self.alive.get(pid, False)
            )
            alive_town = sum(
                1 for pid, role in self.roles.items()
                if get_team(role) == TEAM_TOWN and self.alive.get(pid, False)
            )

            if alive_mafia == 0:
                return {
                    "winner": TEAM_TOWN,
                    "reason": "All Mafia members have been eliminated!",
                    "alive_town": alive_town,
                    "alive_mafia": 0
                }

            if alive_mafia >= alive_town:
                return {
                    "winner": TEAM_MAFIA,
                    "reason": "Mafia has equal or more members than Town!",
                    "alive_town": alive_town,
                    "alive_mafia": alive_mafia
                }

            return None  # Game continues

    # ──────────────────────────────────────────
    # End-Game Summary
    # ──────────────────────────────────────────

    def get_game_summary(self) -> dict:
        """
        Build a complete game summary for the end-game reveal.

        Returns dict with all roles, elimination log, special role history,
        and final status.
        """
        with self.lock:
            all_roles = {}
            for pid, role in self.roles.items():
                name = self.names.get(pid, "Unknown")
                all_roles[name] = {
                    "role": role,
                    "team": get_team(role),
                    "survived": self.alive.get(pid, False)
                }

            return {
                "roles": all_roles,
                "rounds_played": self.round_number,
                "elimination_log": list(self.elimination_log),
                "detective_results": list(self.detective_results),
                "doctor_saves": list(self.doctor_saves),
            }

    def increment_round(self):
        """Advance to the next round."""
        with self.lock:
            self.round_number += 1

    def handle_player_disconnect(self, player_id: str):
        """Handle a player disconnecting mid-game — mark them dead."""
        with self.lock:
            if player_id in self.alive:
                self.alive[player_id] = False
