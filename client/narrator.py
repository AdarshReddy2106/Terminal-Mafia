"""
narrator.py — Dramatic narrative text engine for Terminal Mafia

Provides randomized, atmospheric text for every game event.
Instead of "Player3 was killed", the narrator tells a story.
Multiple templates per event ensure each game feels unique.
"""

import random


# ══════════════════════════════════════════════
# Night Fall Narratives
# ══════════════════════════════════════════════

NIGHT_FALL = [
    "Darkness creeps across the town. Doors lock. Shutters slam. Something stirs...",
    "The last lamp flickers and dies. The town holds its breath. Night has come.",
    "Shadows pool in the streets. Footsteps echo in the dark. No one is safe.",
    "The moon rises, cold and indifferent. Somewhere, the Mafia makes its move.",
    "Night descends like a curtain. Behind closed doors, a conspiracy unfolds.",
    "The town falls silent. But silence, tonight, is a lie.",
]

# ══════════════════════════════════════════════
# Night Kill Discovery
# ══════════════════════════════════════════════

NIGHT_KILL = [
    "As dawn breaks, a scream shatters the morning air.\n  {name} was found lifeless. They were a {role}.",
    "The town gathers at first light... and finds {name} will never wake again.\n  A {role} — gone forever.",
    "A door hangs open. Inside, the truth is grim.\n  {name} ({role}) did not survive the night.",
    "The cobblestones tell the story. {name} lies still.\n  The town has lost a {role}.",
    "Whispers spread like wildfire at dawn. {name} is dead.\n  They were a {role}. The Mafia has struck again.",
]

# ══════════════════════════════════════════════
# No Kill (Everyone Survived)
# ══════════════════════════════════════════════

NO_KILL = [
    "The sun rises on a miracle — everyone survived the night!",
    "Dawn breaks peacefully. No blood was spilled tonight.",
    "Against all odds, the town wakes whole. The Mafia missed their mark.",
    "Morning comes, and every door opens. Everyone is alive! But for how long?",
]

# ══════════════════════════════════════════════
# Day Vote Elimination
# ══════════════════════════════════════════════

VOTE_ELIMINATION = [
    "The crowd has spoken. {name} is dragged to the center.\n  They were a {role}.",
    "Justice — or perhaps injustice — is served. {name} is eliminated.\n  The town reveals: {role}.",
    "The vote is decisive. {name} meets their fate.\n  Behind the mask: a {role}.",
    "No amount of pleading saves {name}. The town decides.\n  Role revealed: {role}.",
    "The gavel falls. {name} is no more.\n  They were a {role} all along.",
]

# ══════════════════════════════════════════════
# Tie Vote
# ══════════════════════════════════════════════

VOTE_TIE = [
    "The town is divided! No majority — no one is eliminated today.",
    "Voices clash and tempers flare, but the vote ends in deadlock. No execution.",
    "A tie! Suspicion hangs thick, but the town cannot agree. Everyone lives... for now.",
]

# ══════════════════════════════════════════════
# No Votes Cast
# ══════════════════════════════════════════════

NO_VOTES = [
    "Silence. No one votes. The accused walk free — but trust fractures further.",
    "Not a single hand is raised. The town does nothing. The Mafia smiles.",
]

# ══════════════════════════════════════════════
# Game Over — Town Wins
# ══════════════════════════════════════════════

TOWN_WINS = [
    "The last Mafia member falls. The town erupts in celebration!\n  Justice prevails! The streets are safe again.",
    "It's over. The Mafia is no more. The townsfolk can finally sleep in peace.",
    "Light conquers darkness! Every last Mafia member has been unmasked and eliminated.",
]

# ══════════════════════════════════════════════
# Game Over — Mafia Wins
# ══════════════════════════════════════════════

MAFIA_WINS = [
    "The Mafia takes control. The town crumbles under their rule.\n  Fear wins tonight.",
    "Too late. The town realizes the truth only as the Mafia claims victory.\n  The shadows have won.",
    "One by one, the innocents fell. The Mafia's grip is absolute.\n  This town belongs to them now.",
]

# ══════════════════════════════════════════════
# Discussion Phase Openers
# ══════════════════════════════════════════════

DISCUSSION_START = [
    "The floor is open. Accusations fly. Who do you trust?",
    "Speak now — your words could save a life... or condemn one.",
    "The town gathers to discuss. Point fingers. Defend yourself. The clock is ticking.",
    "Everyone's a suspect. Everyone's a liar. Discuss.",
]

# ══════════════════════════════════════════════
# Voting Phase Openers
# ══════════════════════════════════════════════

VOTING_START = [
    "The debate is over. Cast your vote. Choose who to eliminate.",
    "Time to decide. One of you must go. Vote now.",
    "The talking stops. The voting begins. Make your choice count.",
]

# ══════════════════════════════════════════════
# Last Words Prompt
# ══════════════════════════════════════════════

LAST_WORDS_PROMPT = [
    "Any last words, {name}?",
    "{name}, the town gives you one final breath to speak...",
    "Before the end, {name} — do you have anything to say?",
]

# ══════════════════════════════════════════════
# Countdown Warnings
# ══════════════════════════════════════════════

COUNTDOWN_WARNINGS = {
    30: "⏰ 30 seconds remain. The clock ticks louder...",
    15: "⏰ 15 seconds! Hurry — time is running out!",
    10: "⏰ 10 seconds! Last chance!",
    5:  "⏰ 5... 4... 3... 2... 1...",
}

# ══════════════════════════════════════════════
# Role Reveal Flavor Text
# ══════════════════════════════════════════════

ROLE_REVEAL_FLAVOR = {
    "Mafia": "The shadows have chosen you. You are part of the Mafia.\n  Deceive. Eliminate. Dominate.",
    "Villager": "You are an ordinary citizen of this town.\n  But there is nothing ordinary about survival.",
    "Detective": "Your eye for truth is your weapon.\n  Each night, investigate one player to learn if they walk in darkness.",
    "Doctor": "Life and death rest in your hands.\n  Each night, choose one soul to protect from the Mafia's blade.",
}


# ══════════════════════════════════════════════
# Narrator Functions
# ══════════════════════════════════════════════

def narrate_night_fall() -> str:
    """Get a random night fall narrative."""
    return random.choice(NIGHT_FALL)


def narrate_night_kill(name: str, role: str) -> str:
    """Get a random night kill narrative with the victim's info."""
    template = random.choice(NIGHT_KILL)
    return template.format(name=name, role=role)


def narrate_no_kill() -> str:
    """Get a random 'no one died' narrative."""
    return random.choice(NO_KILL)


def narrate_vote_elimination(name: str, role: str) -> str:
    """Get a random vote elimination narrative."""
    template = random.choice(VOTE_ELIMINATION)
    return template.format(name=name, role=role)


def narrate_vote_tie() -> str:
    """Get a random vote tie narrative."""
    return random.choice(VOTE_TIE)


def narrate_no_votes() -> str:
    """Get a random 'no votes cast' narrative."""
    return random.choice(NO_VOTES)


def narrate_town_wins() -> str:
    """Get a random Town victory narrative."""
    return random.choice(TOWN_WINS)


def narrate_mafia_wins() -> str:
    """Get a random Mafia victory narrative."""
    return random.choice(MAFIA_WINS)


def narrate_discussion_start() -> str:
    """Get a random discussion phase opener."""
    return random.choice(DISCUSSION_START)


def narrate_voting_start() -> str:
    """Get a random voting phase opener."""
    return random.choice(VOTING_START)


def narrate_last_words(name: str) -> str:
    """Get a random last words prompt."""
    template = random.choice(LAST_WORDS_PROMPT)
    return template.format(name=name)


def get_countdown_warning(seconds: int) -> str:
    """Get a dramatic countdown warning for specific time thresholds."""
    return COUNTDOWN_WARNINGS.get(seconds, f"⏰ {seconds} seconds remaining!")


def get_role_flavor(role: str) -> str:
    """Get flavor text for a role reveal."""
    return ROLE_REVEAL_FLAVOR.get(role, "Your role has been assigned.")
