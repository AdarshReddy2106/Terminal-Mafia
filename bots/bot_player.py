"""
bot_player.py — AI Bot Player for Terminal Mafia

Acts as a virtual client. Intercepts messages from the server,
uses an LLM to decide actions, and sends commands back to the server.
"""

import json
import threading
import time
import random
from queue import Queue

from common.protocol import (
    parse_messages, MSG_PHASE_CHANGE, MSG_ROLE_ASSIGN,
    MSG_PLAYER_LIST, MSG_CHAT_MSG, MSG_NIGHT_RESULT, MSG_VOTE_RESULT,
    MSG_TASK_ASSIGN
)
from common.constants import MAFIA_KILL_DELAY
from bots.llm_client import LLMClient


# Personalities to make bots more interesting
PERSONALITIES = [
    "You are an aggressive accuser. You jump to conclusions quickly and suspect everyone.",
    "You are a quiet observer. You speak little, but when you do, it's analytical.",
    "You are extremely paranoid. You think everyone is out to get you.",
    "You are overly friendly and trusting, trying to keep the peace.",
    "You are sarcastic and dismissive, rolling your eyes at everyone's theories."
]


class BotPlayer:
    """
    Virtual player connection.
    Duck-types server.server.PlayerConnection.
    """

    def __init__(self, server, player_id: str, name: str, model: str):
        self.server = server
        self.player_id = player_id
        self.name = name
        self.joined = True
        self.is_bot = True
        
        # Game state tracking for the LLM context
        self.role = None
        self.team = None
        self.is_alive = True
        self.phase = "LOBBY"
        self.alive_players = []
        self.chat_history = []
        
        # Bot logic components
        self.llm = LLMClient(model=model)
        self.personality = random.choice(PERSONALITIES)
        
        # Message processing queue
        self.msg_queue = Queue()
        self.running = True
        self.thread = threading.Thread(target=self._bot_loop, daemon=True, name=f"Bot-{name}")
        self.thread.start()

    # ── PlayerConnection Interface ──

    def send(self, message: str) -> bool:
        """
        Intercept messages from the server.
        Instead of sending over a socket, queue them for the bot thread to process.
        """
        if not self.running:
            return False
            
        messages = parse_messages(message)
        for msg in messages:
            self.msg_queue.put(msg)
        return True

    def close(self):
        """Shut down the bot."""
        self.running = False
        self.msg_queue.put(None)  # Sentinel to unblock queue

    # ── Internal Bot Logic ──

    def _bot_loop(self):
        """Background thread to process messages and make LLM calls."""
        while self.running:
            msg = self.msg_queue.get()
            if msg is None:
                break
                
            self._handle_message(msg)
            self.msg_queue.task_done()

    def _handle_message(self, msg: dict):
        """Update internal state and decide if action is needed."""
        msg_type = msg.get("type")
        data = msg.get("data", {})

        if msg_type == MSG_ROLE_ASSIGN:
            self.role = data.get("role")
            self.team = data.get("team")
            
        elif msg_type == MSG_PHASE_CHANGE:
            self.phase = data.get("phase")
            if "alive_players" in data:
                self.alive_players = data.get("alive_players")
                
            # If entering a phase, possibly take an action
            if self.phase == "DISCUSSION":
                self._do_discussion()
            elif self.phase == "VOTING":
                # Wait a random bit so it doesn't instantly vote
                time.sleep(random.uniform(2.0, 5.0))
                self._do_vote()
                
        elif msg_type == MSG_PLAYER_LIST:
            context = data.get("context")
            targets = [p["name"] for p in data.get("players", [])]
            
            if context == "night_targets" and self.role == "Mafia":
                time.sleep(MAFIA_KILL_DELAY + random.uniform(1.0, 3.0))
                self._do_target_action(targets, "kill")
            elif context == "investigate_targets" and self.role == "Detective":
                time.sleep(random.uniform(2.0, 4.0))
                self._do_target_action(targets, "investigate")
            elif context == "protect_targets" and self.role == "Doctor":
                time.sleep(random.uniform(2.0, 4.0))
                self._do_target_action(targets, "protect")
                
        elif msg_type in (MSG_TASK_ASSIGN, MSG_GHOST_TASKS):
            tasks = data.get("tasks", [])
            self._do_tasks(tasks)

        elif msg_type == MSG_CHAT_MSG:
            sender = data.get("from")
            message = data.get("message")
            if sender != self.name and not sender.startswith("[Spectator"):
                self.chat_history.append(f"{sender}: {message}")
                # Keep history short to save tokens
                if len(self.chat_history) > 10:
                    self.chat_history.pop(0)
                    
        elif msg_type in (MSG_NIGHT_RESULT, MSG_VOTE_RESULT):
            # If we died, stop acting
            killed = data.get("killed")
            eliminated = data.get("eliminated")
            if killed == self.name or eliminated == self.name:
                self.is_alive = False
    # ── Actions ──

    def _send_to_server(self, msg: dict):
        """Simulate sending a message to the server's handler."""
        # Convert to JSON and immediately let the server parse it
        # Actually, we can just call the server handlers directly to avoid socket loopback
        if not self.server.game_engine:
            return
            
        engine = self.server.game_engine
        msg_type = msg.get("type")
        data = msg.get("data", {})
        
        if msg_type == "CHAT":
            message = data.get("message")
            error = engine.handle_chat_in_game(self.player_id, message)
            if not error:
                # Need to route it properly
                from common.protocol import create_message
                out_msg = create_message(MSG_CHAT_MSG, {"from": self.name, "message": message})
                self.server.broadcast(out_msg)
            elif error == "MAFIA_CHAT":
                pass # Handled internally
                
        elif msg_type == "VOTE":
            engine.handle_vote(self.player_id, data)
            
        elif msg_type == "NIGHT_ACTION":
            engine.handle_night_action(self.player_id, data)

        elif msg_type == "DOCTOR_PROTECT":
            engine.handle_doctor_protect(self.player_id, data)

        elif msg_type == "TASK_SUBMIT":
            engine.handle_task_submit(self.player_id, data)
            

    def _build_system_prompt(self) -> str:
        """Create the context for the LLM."""
        return f"""You are playing Terminal Mafia, a text-based social deduction game.
Your name is '{self.name}'.
Your role is {self.role} (Team: {self.team}).
Personality: {self.personality}

Rules of your role:
- If Town (Villager/Detective/Doctor): You win by eliminating all Mafia. Find who is lying.
- If Mafia/Double Agent: You win by eliminating Town. You must BLUFF and pretend to be Town. Never admit you are Mafia.

Current alive players: {', '.join(self.alive_players)}
"""

    def _do_discussion(self):
        """Generate a chat message using the LLM."""
        if not self.is_alive or not self.llm.is_configured():
            return
            
        # Give humans a chance to talk first
        time.sleep(random.uniform(3.0, 8.0))
        
        recent_chat = "\n".join(self.chat_history[-5:])
        if not recent_chat:
            recent_chat = "(No one has spoken yet this round)"
            
        prompt = f"""Recent chat:
{recent_chat}

Generate a short (1-2 sentences) chat message to say to the group.
Do not use quotes around your message. Act in character."""

        response = self.llm.generate(self._build_system_prompt(), prompt, max_tokens=60)
        if response:
            # Clean up response (sometimes LLMs add quotes)
            response = response.strip('"\'')
            self._send_to_server({"type": "CHAT", "data": {"message": response}})

    def _do_vote(self):
        """Generate a vote target using the LLM."""
        if not self.is_alive:
            return
            
        if not self.llm.is_configured():
            self._random_vote(self.alive_players)
            return

        valid_targets = [p for p in self.alive_players if p != self.name]
        recent_chat = "\n".join(self.chat_history)
        
        prompt = f"""Recent chat:
{recent_chat}

It is time to vote someone out. Valid targets: {', '.join(valid_targets)}.
Who do you vote for?

Reply ONLY with the exact name of the player you are voting for. No other text."""

        response = self.llm.generate(self._build_system_prompt(), prompt, max_tokens=10)
        
        if response:
            target = response.strip(".,'\" \n")
            # Verify LLM gave a valid target
            if any(target.lower() == p.lower() for p in valid_targets):
                self._send_to_server({"type": "VOTE", "data": {"target": target}})
                return
                
        # Fallback
        self._random_vote(valid_targets)

    def _do_tasks(self, tasks: list):
        """Bots auto-complete tasks using the answers provided in the task dict."""
        # Note: In a real game we wouldn't send the answer in the dict, but for this prototype
        # we can just have the bot instantly or slowly submit the correct answer.
        # Actually, wait, the client task dict doesn't contain the answer!
        # The prompt is "Type this word exactly: shadow" or "Solve: 5 + 3 = ?".
        # We can use the LLM to solve the task, or parse the prompt!
        # Parsing is faster and more reliable.
        for t in tasks:
            time.sleep(random.uniform(1.0, 3.0))
            prompt = t["prompt"]
            answer = ""
            if t["type"] == "typing":
                # "Type this word exactly: shadow"
                parts = prompt.split(":")
                if len(parts) > 1:
                    answer = parts[1].strip()
            elif t["type"] == "math":
                # "Solve: 5 + 3 = ?"
                parts = prompt.replace("Solve:", "").replace("?", "").replace("=", "").strip().split()
                if len(parts) == 3:
                    a, op, b = parts
                    try:
                        if op == "+": answer = str(int(a) + int(b))
                        elif op == "-": answer = str(int(a) - int(b))
                        elif op == "×": answer = str(int(a) * int(b))
                    except:
                        pass
            elif t["type"] == "unscramble":
                # Bot cheating by using LLM to unscramble
                res = self.llm.generate("You are a helpful assistant.", f"Unscramble this word: {prompt.split(': ')[1]}. Reply with ONLY the unscrambled word.", max_tokens=10)
                if res:
                    answer = res.strip(".,'\" \n")
            
            if answer:
                self._send_to_server({"type": "TASK_SUBMIT", "data": {"task_id": t["id"], "answer": answer}})

    def _do_target_action(self, targets: list, action: str):
        """Generate a target action (kill, investigate, protect) using the LLM."""
        if not self.is_alive:
            return
            
        msg_type = "DOCTOR_PROTECT" if action == "protect" else "NIGHT_ACTION"
            
        if not self.llm.is_configured():
            if targets:
                target = random.choice(targets)
                self._send_to_server({"type": msg_type, "data": {"action": action, "target": target}})
            return
            
        recent_chat = "\n".join(self.chat_history[-8:])
        
        action_desc = {
            "kill": "Who do you want to kill?",
            "investigate": "Who do you want to investigate to see if they are Mafia?",
            "protect": "Who do you want to protect from the Mafia's kill? (You can protect yourself)"
        }.get(action, "Select a target.")
        
        prompt = f"""Recent chat for context:
{recent_chat}

Valid targets for this action: {', '.join(targets)}.
{action_desc}

Reply ONLY with the exact name of the player. No other text."""

        response = self.llm.generate(self._build_system_prompt(), prompt, max_tokens=10)
        
        if response:
            target = response.strip(".,'\" \n")
            if any(target.lower() == p.lower() for p in targets):
                self._send_to_server({"type": msg_type, "data": {"action": action, "target": target}})
                return
                
        # Fallback
        if targets:
            target = random.choice(targets)
            self._send_to_server({"type": msg_type, "data": {"action": action, "target": target}})

    def _random_vote(self, valid_targets):
        """Fallback to random voting if API fails."""
        if valid_targets:
            target = random.choice(valid_targets)
            self._send_to_server({"type": "VOTE", "data": {"target": target}})
