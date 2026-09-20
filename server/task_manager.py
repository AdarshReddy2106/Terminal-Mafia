"""
task_manager.py — Task generation, tracking, and task-bar logic for Terminal Mafia

Generates terminal mini-games for players during the Night phase:
  - Easy: Typing challenge (type a word/phrase exactly)
  - Medium: Math problem (solve arithmetic)
  - Hard: Word unscramble (rearrange jumbled letters)

Tracks completion per-player and globally for the task-bar win condition.
"""

import random
import threading

from common.constants import TASKS_PER_PLAYER, ENGINEER_BONUS_TASKS


# ──────────────────────────────────────────────
# Task Pools
# ──────────────────────────────────────────────

EASY_WORDS = [
    "shadow", "whisper", "midnight", "silence", "suspect",
    "danger", "hidden", "alibi", "evidence", "betrayal",
    "criminal", "witness", "verdict", "mystery", "tension",
    "deception", "guilty", "innocent", "paranoia", "vigilante",
    "conspiracy", "detective", "undercover", "fugitive", "interrogate",
]

HARD_WORDS = [
    "conspiracy", "elimination", "investigation", "surveillance",
    "interrogation", "suspicious", "accomplice", "anonymous",
    "blackmail", "confession", "testimony", "prosecutor",
    "fingerprint", "camouflage", "subterfuge", "treacherous",
    "infiltrate", "counterspy", "incriminate", "masquerade",
]


def _generate_easy_task() -> dict:
    """Generate a typing challenge task."""
    word = random.choice(EASY_WORDS)
    return {
        "id": f"easy_{random.randint(1000, 9999)}",
        "difficulty": "easy",
        "type": "typing",
        "prompt": f"Type this word exactly: {word}",
        "answer": word,
        "display": f"⌨️  TYPE: \"{word}\"",
    }


def _generate_medium_task() -> dict:
    """Generate a math problem task."""
    ops = [
        ("+", lambda a, b: a + b),
        ("-", lambda a, b: a - b),
        ("×", lambda a, b: a * b),
    ]
    op_symbol, op_func = random.choice(ops)

    if op_symbol == "×":
        a = random.randint(2, 12)
        b = random.randint(2, 12)
    else:
        a = random.randint(10, 99)
        b = random.randint(10, 99)
        if op_symbol == "-" and b > a:
            a, b = b, a  # Keep result positive

    answer = op_func(a, b)
    return {
        "id": f"med_{random.randint(1000, 9999)}",
        "difficulty": "medium",
        "type": "math",
        "prompt": f"Solve: {a} {op_symbol} {b} = ?",
        "answer": str(answer),
        "display": f"🧮 SOLVE: {a} {op_symbol} {b} = ?",
    }


def _generate_hard_task() -> dict:
    """Generate a word unscramble task."""
    word = random.choice(HARD_WORDS)
    letters = list(word)
    # Shuffle until different from original
    for _ in range(20):
        random.shuffle(letters)
        if "".join(letters) != word:
            break
    scrambled = "".join(letters)

    return {
        "id": f"hard_{random.randint(1000, 9999)}",
        "difficulty": "hard",
        "type": "unscramble",
        "prompt": f"Unscramble: {scrambled}",
        "answer": word,
        "display": f"🔀 UNSCRAMBLE: \"{scrambled}\"",
        "hint": f"({len(word)} letters)",
    }


def generate_player_tasks(count: int = TASKS_PER_PLAYER) -> list[dict]:
    """
    Generate a set of tasks for one player.
    Default: 1 easy, 1 medium, 1 hard.
    """
    tasks = []
    if count >= 1:
        tasks.append(_generate_easy_task())
    if count >= 2:
        tasks.append(_generate_medium_task())
    if count >= 3:
        tasks.append(_generate_hard_task())
    # If more than 3 tasks requested (e.g. bonus), add random difficulties
    for _ in range(max(0, count - 3)):
        gen = random.choice([_generate_easy_task, _generate_medium_task, _generate_hard_task])
        tasks.append(gen())
    return tasks


def generate_bonus_task() -> dict:
    """Generate a single bonus task for the Engineer."""
    gen = random.choice([_generate_medium_task, _generate_hard_task])
    task = gen()
    task["id"] = f"bonus_{random.randint(1000, 9999)}"
    task["is_bonus"] = True
    return task




class TaskTracker:
    """
    Tracks task assignment and completion across all players.
    Thread-safe.
    """

    def __init__(self):
        self.lock = threading.Lock()
        # player_id -> list of task dicts (with "completed" field added)
        self.player_tasks: dict[str, list[dict]] = {}
        # Total tasks assigned to Town (for task-bar win condition)
        self.total_town_tasks = 0
        self.completed_town_tasks = 0
        # Track which player IDs are Town (for win condition counting)
        self.town_players: set[str] = set()

    def assign_tasks(self, player_id: str, tasks: list[dict], is_town: bool = True):
        """Assign initial tasks to a player."""
        with self.lock:
            for task in tasks:
                task["completed"] = False
            self.player_tasks[player_id] = tasks
            if is_town:
                self.town_players.add(player_id)
                self.total_town_tasks += len(tasks)

    def refresh_tasks(self, player_id: str):
        """Reroll incomplete tasks for a new round, keeping completed ones."""
        with self.lock:
            if player_id not in self.player_tasks:
                return
            
            tasks = self.player_tasks[player_id]
            new_tasks = []
            for task in tasks:
                if task.get("completed"):
                    new_tasks.append(task)
                else:
                    diff = task.get("difficulty")
                    if diff == "easy":
                        new_t = _generate_easy_task()
                    elif diff == "medium":
                        new_t = _generate_medium_task()
                    elif diff == "hard":
                        new_t = _generate_hard_task()
                    else:
                        new_t = _generate_medium_task()
                    
                    new_t["completed"] = False
                    if task.get("is_bonus"):
                        new_t["is_bonus"] = True
                    new_tasks.append(new_t)
            
            self.player_tasks[player_id] = new_tasks

    def submit_answer(self, player_id: str, task_id: str, answer: str) -> dict:
        """
        Submit an answer for a task.
        If task_id is empty, checks the answer against all pending tasks.

        Returns dict with:
            - "valid": bool (was a valid task found)
            - "correct": bool (was the answer correct)
            - "task": the task dict
            - "all_done": bool (all tasks for this player completed)
        """
        with self.lock:
            tasks = self.player_tasks.get(player_id, [])
            for task in tasks:
                if not task["completed"]:
                    # Match by task_id OR if task_id is empty, match by correct answer
                    correct = answer.strip().lower() == task["answer"].strip().lower()
                    if (task["id"] == task_id) or (not task_id and correct):
                        if correct:
                            task["completed"] = True
                            if player_id in self.town_players:
                                self.completed_town_tasks += 1

                        all_done = all(t["completed"] for t in tasks)
                        return {
                            "valid": True,
                            "correct": correct,
                            "task": task,
                            "all_done": all_done,
                        }

                    all_done = all(t["completed"] for t in tasks)
                    return {
                        "valid": True,
                        "correct": correct,
                        "task": task,
                        "all_done": all_done,
                    }

            return {"valid": False, "correct": False, "task": None, "all_done": False}

    def get_pending_tasks(self, player_id: str) -> list[dict]:
        """Get list of uncompleted tasks for a player."""
        with self.lock:
            tasks = self.player_tasks.get(player_id, [])
            return [t for t in tasks if not t["completed"]]

    def get_all_tasks(self, player_id: str) -> list[dict]:
        """Get all tasks (completed and pending) for a player."""
        with self.lock:
            return list(self.player_tasks.get(player_id, []))

    def get_task_progress(self) -> dict:
        """
        Get overall task-bar progress.

        Returns dict with:
            - "total": total Town tasks
            - "completed": completed Town tasks
            - "percentage": completion percentage (0-100)
        """
        with self.lock:
            total = self.total_town_tasks
            completed = self.completed_town_tasks
            pct = round((completed / total) * 100) if total > 0 else 0
            return {
                "total": total,
                "completed": completed,
                "percentage": pct,
            }

    def check_task_win(self) -> bool:
        """Check if all Town tasks are completed (task-bar win condition)."""
        with self.lock:
            if self.total_town_tasks == 0:
                return False
            return self.completed_town_tasks >= self.total_town_tasks

    def add_bonus_task(self, player_id: str, task: dict):
        """Add a bonus task (Engineer) to a player's task list."""
        with self.lock:
            task["completed"] = False
            if player_id in self.player_tasks:
                self.player_tasks[player_id].append(task)
            else:
                self.player_tasks[player_id] = [task]
            if player_id in self.town_players:
                self.total_town_tasks += 1
