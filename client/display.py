"""
display.py — Terminal Display Engine for Terminal Mafia

Handles all visual rendering:
- Screen clearing and management
- Colored output with phase-specific themes
- ASCII art banner rendering
- Typewriter effect (fast, smooth)
- Glitch effect for dramatic moments
- Suspicion meter visualization
- Countdown display
"""

import os
import sys
import time
import random

# Try colorama for cross-platform color support
try:
    from colorama import Fore, Back, Style, init as colorama_init
    colorama_init()
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = RESET = ""
        LIGHTBLACK_EX = LIGHTRED_EX = LIGHTYELLOW_EX = LIGHTCYAN_EX = ""
        LIGHTGREEN_EX = LIGHTMAGENTA_EX = LIGHTBLUE_EX = LIGHTWHITE_EX = ""
    class Back:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = RESET = ""
        BLACK = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

from assets.ascii_art import (
    NIGHT_BANNER, DAWN_BANNER, DISCUSSION_BANNER, VOTING_BANNER,
    SKULL, GAVEL, TROPHY, GAME_OVER_BANNER, NO_ONE_DIED,
    DIVIDER_NIGHT, DIVIDER_DAY, DIVIDER_VOTE, DIVIDER_THIN, DIVIDER_DOUBLE,
    get_role_card, get_tombstone
)
from client.narrator import (
    narrate_night_fall, narrate_night_kill, narrate_no_kill,
    narrate_vote_elimination, narrate_vote_tie, narrate_no_votes,
    narrate_town_wins, narrate_mafia_wins,
    narrate_discussion_start, narrate_voting_start,
    get_role_flavor
)


# ══════════════════════════════════════════════
# Phase Color Themes
# ══════════════════════════════════════════════

PHASE_COLORS = {
    "NIGHT": Fore.BLUE,
    "DAWN": Fore.LIGHTYELLOW_EX,
    "DISCUSSION": Fore.CYAN,
    "VOTING": Fore.YELLOW,
    "GAME_OVER": Fore.MAGENTA,
    "LOBBY": Fore.GREEN,
}

ROLE_COLORS = {
    "Mafia": Fore.RED,
    "Villager": Fore.GREEN,
    "Detective": Fore.CYAN,
    "Doctor": Fore.LIGHTGREEN_EX,
    "Double Agent": Fore.MAGENTA,
}


# ══════════════════════════════════════════════
# Screen Management
# ══════════════════════════════════════════════

def clear_screen():
    """Clear the terminal screen (cross-platform)."""
    if sys.platform == "win32":
        os.system("cls")
    else:
        os.system("clear")


def terminal_bell():
    """Ring the terminal bell for phase change alerts."""
    sys.stdout.write("\a")
    sys.stdout.flush()


# ══════════════════════════════════════════════
# Text Effects
# ══════════════════════════════════════════════

def typewriter(text: str, delay: float = 0.012, color: str = ""):
    """
    Print text with a fast typewriter effect.
    
    Smooth and quick — adds drama without making players wait.
    delay=0.012 gives ~80 chars/second, which feels snappy.
    """
    reset = Style.RESET_ALL
    for char in text:
        sys.stdout.write(f"{color}{char}{reset}")
        sys.stdout.flush()
        if char in ".!?":
            time.sleep(delay * 3)  # Slight pause on punctuation
        elif char == "\n":
            time.sleep(delay * 2)
        else:
            time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def glitch_effect(duration: float = 0.3, width: int = 50):
    """
    Brief terminal 'corruption' effect — random characters flash
    for a fraction of a second, then clear. Creates an eerie feeling.
    """
    glitch_chars = "█▓▒░╗╔║╚╝╣╠╬╩╦═─│┤├┴┬┼▀▄▌▐"
    frames = int(duration / 0.05)
    
    for _ in range(frames):
        line = "  " + "".join(random.choice(glitch_chars) for _ in range(width))
        sys.stdout.write(f"\r{Fore.RED}{Style.DIM}{line}{Style.RESET_ALL}")
        sys.stdout.flush()
        time.sleep(0.05)
    
    # Clear the glitch line
    sys.stdout.write(f"\r{' ' * (width + 4)}\r")
    sys.stdout.flush()


# ══════════════════════════════════════════════
# Phase Banners
# ══════════════════════════════════════════════

def show_night_banner(round_num: int, duration: int = 0, is_mafia: bool = False):
    """Display the night phase banner with narrative text."""
    clear_screen()
    terminal_bell()
    
    print(f"{Fore.BLUE}{Style.BRIGHT}{NIGHT_BANNER}{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{Style.BRIGHT}Round {round_num}{Style.RESET_ALL}")
    
    if duration:
        print(f"  {Style.DIM}Time limit: {duration} seconds{Style.RESET_ALL}")
    
    print()
    typewriter(f"  {narrate_night_fall()}", delay=0.015, color=Fore.BLUE)
    print()
    
    if is_mafia:
        print(f"  {Fore.RED}{Style.BRIGHT}╔═══════════════════════════════════╗{Style.RESET_ALL}")
        print(f"  {Fore.RED}{Style.BRIGHT}║  🔪 You are MAFIA — choose your  ║{Style.RESET_ALL}")
        print(f"  {Fore.RED}{Style.BRIGHT}║     target wisely.  Use:          ║{Style.RESET_ALL}")
        print(f"  {Fore.RED}{Style.BRIGHT}║     /kill <name> or /kill <#>     ║{Style.RESET_ALL}")
        print(f"  {Fore.RED}{Style.BRIGHT}╚═══════════════════════════════════╝{Style.RESET_ALL}")
    else:
        print(f"  {Style.DIM}The town sleeps... You are safe in your bed.{Style.RESET_ALL}")
        print(f"  {Style.DIM}Wait for dawn.{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{DIVIDER_NIGHT}{Style.RESET_ALL}\n")


def show_dawn_banner(round_num: int):
    """Display the dawn phase banner."""
    clear_screen()
    terminal_bell()
    
    print(f"{Fore.LIGHTYELLOW_EX}{Style.BRIGHT}{DAWN_BANNER}{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTYELLOW_EX}{Style.BRIGHT}Round {round_num}{Style.RESET_ALL}")
    print()


def show_discussion_banner(round_num: int, duration: int = 0, alive_players: list = None):
    """Display the discussion phase banner."""
    clear_screen()
    terminal_bell()
    
    print(f"{Fore.CYAN}{Style.BRIGHT}{DISCUSSION_BANNER}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}Round {round_num}{Style.RESET_ALL}")
    
    if duration:
        print(f"  {Style.DIM}Time limit: {duration} seconds{Style.RESET_ALL}")
    
    print()
    typewriter(f"  {narrate_discussion_start()}", delay=0.012, color=Fore.CYAN)
    print()
    
    if alive_players:
        print(f"  {Style.BRIGHT}Alive players ({len(alive_players)}):{Style.RESET_ALL}")
        for i, name in enumerate(alive_players, 1):
            print(f"    {Fore.WHITE}{i}. {name}{Style.RESET_ALL}")
        print()
    
    print(f"{Fore.CYAN}{DIVIDER_DAY}{Style.RESET_ALL}\n")


def show_voting_banner(round_num: int, duration: int = 0, alive_players: list = None):
    """Display the voting phase banner."""
    clear_screen()
    terminal_bell()
    
    print(f"{Fore.YELLOW}{Style.BRIGHT}{VOTING_BANNER}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}{Style.BRIGHT}Round {round_num}{Style.RESET_ALL}")
    
    if duration:
        print(f"  {Style.DIM}Time limit: {duration} seconds{Style.RESET_ALL}")
    
    print()
    typewriter(f"  {narrate_voting_start()}", delay=0.012, color=Fore.YELLOW)
    print()
    
    print(f"  {Fore.YELLOW}{Style.BRIGHT}Use: /vote <name> or /vote <#>{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}{DIVIDER_VOTE}{Style.RESET_ALL}\n")


# ══════════════════════════════════════════════
# Event Displays
# ══════════════════════════════════════════════

def show_role_reveal(role: str, team: str, description: str, teammates: list = None):
    """Display a dramatic role card reveal with brief glitch effect."""
    glitch_effect(duration=0.2)
    
    role_color = ROLE_COLORS.get(role, Fore.WHITE)
    card = get_role_card(role)
    
    print(f"{role_color}{Style.BRIGHT}{card}{Style.RESET_ALL}")
    print()
    
    # Flavor text with typewriter
    flavor = get_role_flavor(role)
    typewriter(f"  {flavor}", delay=0.015, color=role_color)
    print()
    
    if teammates:
        print(f"  {Fore.RED}{Style.BRIGHT}Your Mafia allies:{Style.RESET_ALL}")
        for t in teammates:
            print(f"    {Fore.RED}🔪 {t}{Style.RESET_ALL}")
        print()
    
    print(f"  {Style.DIM}Team: {team} | Role: {role}{Style.RESET_ALL}")
    print(f"  {DIVIDER_DOUBLE}")
    print()


def show_night_kill(killed_name: str, killed_role: str):
    """Display a dramatic night kill reveal."""
    glitch_effect(duration=0.25)
    
    print(f"{Fore.RED}{Style.BRIGHT}{SKULL}{Style.RESET_ALL}")
    
    narrative = narrate_night_kill(killed_name, killed_role)
    typewriter(f"  ☠️  {narrative}", delay=0.015, color=Fore.RED)
    print()
    
    tombstone = get_tombstone(killed_name)
    print(f"{Fore.RED}{Style.DIM}{tombstone}{Style.RESET_ALL}")
    print()


def show_no_kill():
    """Display the 'no one died' reveal."""
    print(f"{Fore.GREEN}{Style.BRIGHT}{NO_ONE_DIED}{Style.RESET_ALL}")
    
    narrative = narrate_no_kill()
    typewriter(f"  🌅 {narrative}", delay=0.012, color=Fore.GREEN)
    print()


def show_vote_result(eliminated: str, eliminated_role: str,
                     vote_tally: dict, individual_votes: dict,
                     is_tie: bool):
    """Display voting results with narrative and visual tally."""
    print()
    print(f"{Fore.YELLOW}{DIVIDER_VOTE}{Style.RESET_ALL}")
    
    if eliminated:
        glitch_effect(duration=0.15)
        print(f"{Fore.RED}{Style.BRIGHT}{GAVEL}{Style.RESET_ALL}")
        
        narrative = narrate_vote_elimination(eliminated, eliminated_role)
        typewriter(f"  ⚖️  {narrative}", delay=0.015, color=Fore.RED)
    elif is_tie:
        narrative = narrate_vote_tie()
        typewriter(f"  ⚖️  {narrative}", delay=0.012, color=Fore.YELLOW)
    else:
        narrative = narrate_no_votes()
        typewriter(f"  ⚖️  {narrative}", delay=0.012, color=Style.DIM)
    
    print()
    
    # Visual vote tally
    if vote_tally:
        print(f"  {Style.BRIGHT}Vote Breakdown:{Style.RESET_ALL}")
        print(f"  {DIVIDER_THIN}")
        max_votes = max(vote_tally.values()) if vote_tally else 1
        for target, count in sorted(vote_tally.items(), key=lambda x: -x[1]):
            bar_len = int((count / max_votes) * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            color = Fore.RED if target == eliminated else Fore.WHITE
            print(f"    {color}{target:12s} {bar} {count} vote(s){Style.RESET_ALL}")
        print()
    
    if individual_votes:
        print(f"  {Style.DIM}Who voted whom:{Style.RESET_ALL}")
        for voter, target in individual_votes.items():
            print(f"    {Style.DIM}{voter} → {target}{Style.RESET_ALL}")
    
    print(f"  {DIVIDER_VOTE}")
    print()


def show_game_over(winner: str, reason: str, roles: dict,
                   rounds_played: int, elimination_log: list):
    """Display the full game over screen with role reveals."""
    clear_screen()
    terminal_bell()
    time.sleep(0.3)
    terminal_bell()
    
    winner_color = Fore.GREEN if winner == "Town" else Fore.RED
    
    print(f"{winner_color}{Style.BRIGHT}{GAME_OVER_BANNER}{Style.RESET_ALL}")
    print()
    
    print(f"{winner_color}{Style.BRIGHT}{TROPHY}{Style.RESET_ALL}")
    
    # Winner announcement
    print(f"  {winner_color}{Style.BRIGHT}🏆  {winner.upper()} WINS!  🏆{Style.RESET_ALL}")
    print()
    
    if winner == "Town":
        narrative = narrate_town_wins()
    else:
        narrative = narrate_mafia_wins()
    
    typewriter(f"  {narrative}", delay=0.015, color=winner_color)
    print()
    
    print(f"  {Style.DIM}{reason}{Style.RESET_ALL}")
    print(f"  {Style.DIM}Rounds played: {rounds_played}{Style.RESET_ALL}")
    print()
    
    # Full role reveal table
    print(f"  {Style.BRIGHT}═══ ROLE REVEAL ═══{Style.RESET_ALL}")
    print(f"  {DIVIDER_THIN}")
    
    for name, info in roles.items():
        role = info.get("role", "?")
        survived = info.get("survived", False)
        role_color = ROLE_COLORS.get(role, Fore.WHITE)
        status_icon = f"{Fore.GREEN}✓{Style.RESET_ALL}" if survived else f"{Fore.RED}✗{Style.RESET_ALL}"
        status_text = "survived" if survived else "eliminated"
        
        print(f"    {status_icon} {name:12s}  {role_color}{role:10s}{Style.RESET_ALL}  {Style.DIM}({status_text}){Style.RESET_ALL}")
    
    print(f"  {DIVIDER_THIN}")
    
    # Elimination timeline
    if elimination_log:
        print(f"\n  {Style.BRIGHT}═══ ELIMINATION TIMELINE ═══{Style.RESET_ALL}")
        print(f"  {DIVIDER_THIN}")
        for entry in elimination_log:
            phase = entry.get("phase", "?")
            phase_icon = "🌙" if phase == "night" else "☀️"
            r = entry.get("round", "?")
            name = entry.get("eliminated", "?")
            role = entry.get("role", "?")
            role_color = ROLE_COLORS.get(role, Fore.WHITE)
            print(f"    {phase_icon} Round {r}: {name} ({role_color}{role}{Style.RESET_ALL})")
        print(f"  {DIVIDER_THIN}")
    
    print()
    print(f"  {Style.DIM}Thanks for playing Terminal Mafia! 🎭{Style.RESET_ALL}")
    print(f"  {Style.DIM}Type /start to play again.{Style.RESET_ALL}")
    print()


# ══════════════════════════════════════════════
# Player List Displays
# ══════════════════════════════════════════════

def show_target_list(players: list, context: str):
    """Display a numbered target list for voting/night actions."""
    print()
    
    if context == "night_targets":
        print(f"  {Fore.RED}{Style.BRIGHT}┌─── CHOOSE YOUR TARGET ───┐{Style.RESET_ALL}")
        for i, p in enumerate(players, 1):
            name = p.get("name", "?")
            print(f"  {Fore.RED}│  {Style.BRIGHT}{i}.{Style.RESET_ALL} {Fore.RED}{name}{Style.RESET_ALL}")
        print(f"  {Fore.RED}{Style.BRIGHT}└──────────────────────────┘{Style.RESET_ALL}")
        print(f"  {Style.DIM}Use: /kill <name> or /kill <number>{Style.RESET_ALL}")
    
    elif context == "vote_targets":
        print(f"  {Fore.YELLOW}{Style.BRIGHT}┌─── VOTE TO ELIMINATE ────┐{Style.RESET_ALL}")
        for i, p in enumerate(players, 1):
            name = p.get("name", "?")
            print(f"  {Fore.YELLOW}│  {Style.BRIGHT}{i}.{Style.RESET_ALL} {Fore.YELLOW}{name}{Style.RESET_ALL}")
        print(f"  {Fore.YELLOW}{Style.BRIGHT}└──────────────────────────┘{Style.RESET_ALL}")
        print(f"  {Style.DIM}Use: /vote <name> or /vote <number>{Style.RESET_ALL}")
    
    elif context == "investigate_targets":
        print(f"  {Fore.CYAN}{Style.BRIGHT}┌─── INVESTIGATE TARGET ───┐{Style.RESET_ALL}")
        for i, p in enumerate(players, 1):
            name = p.get("name", "?")
            print(f"  {Fore.CYAN}│  {Style.BRIGHT}{i}.{Style.RESET_ALL} {Fore.CYAN}{name}{Style.RESET_ALL}")
        print(f"  {Fore.CYAN}{Style.BRIGHT}└──────────────────────────┘{Style.RESET_ALL}")
        print(f"  {Style.DIM}Use: /investigate <name> or /investigate <number>{Style.RESET_ALL}")
    
    elif context == "protect_targets":
        print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}┌───── PROTECT TARGET ─────┐{Style.RESET_ALL}")
        for i, p in enumerate(players, 1):
            name = p.get("name", "?")
            print(f"  {Fore.LIGHTGREEN_EX}│  {Style.BRIGHT}{i}.{Style.RESET_ALL} {Fore.LIGHTGREEN_EX}{name}{Style.RESET_ALL}")
        print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}└──────────────────────────┘{Style.RESET_ALL}")
        print(f"  {Style.DIM}Use: /protect <name> or /protect <number>{Style.RESET_ALL}")
    
    print()


# ══════════════════════════════════════════════
# Suspicion Meter
# ══════════════════════════════════════════════

def show_suspicion_meter(mention_counts: dict):
    """
    Display a visual suspicion heat map based on name mentions in chat.
    
    Args:
        mention_counts: dict of player_name -> mention count
    """
    if not mention_counts:
        return
    
    max_mentions = max(mention_counts.values()) if mention_counts else 1
    if max_mentions == 0:
        return
    
    print()
    print(f"  {Fore.RED}{Style.BRIGHT}🔥 SUSPICION METER{Style.RESET_ALL}")
    print(f"  {DIVIDER_THIN}")
    
    # Sort by mentions descending
    sorted_players = sorted(mention_counts.items(), key=lambda x: -x[1])
    
    for name, count in sorted_players:
        if count == 0:
            level = "─"
            bar = "░" * 10
            label = ""
            color = Style.DIM
        else:
            ratio = count / max_mentions
            filled = max(1, int(ratio * 10))
            bar = "█" * filled + "░" * (10 - filled)
            
            if ratio >= 0.7:
                label = "HIGH"
                color = Fore.RED
            elif ratio >= 0.4:
                label = "MED"
                color = Fore.YELLOW
            else:
                label = "LOW"
                color = Fore.GREEN
        
        print(f"    {color}{name:12s} {bar} {label}{Style.RESET_ALL}")
    
    print(f"  {DIVIDER_THIN}")
    print()



# ══════════════════════════════════════════════
# Lobby Display
# ══════════════════════════════════════════════

def show_lobby(players: list, player_name: str, can_start: bool,
               player_count: int, min_players: int, max_players: int):
    """Display the lobby with player list and status."""
    print()
    print(f"  {Fore.GREEN}{Style.BRIGHT}┌────────────────────────────────┐{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}{Style.BRIGHT}│     🎭  GAME LOBBY  🎭         │{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}{Style.BRIGHT}│     {player_count}/{max_players} Players              │{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}{Style.BRIGHT}└────────────────────────────────┘{Style.RESET_ALL}")
    print()
    
    for i, name in enumerate(players, 1):
        if name == player_name:
            marker = f"{Fore.YELLOW}★{Style.RESET_ALL}"
        else:
            marker = " "
        print(f"    {marker} {Fore.WHITE}{i}. {Style.BRIGHT}{name}{Style.RESET_ALL}")
    
    print(f"\n  {'─' * 34}")
    
    if can_start:
        print(f"  {Fore.GREEN}{Style.BRIGHT}✅ Ready! Type /start to begin.{Style.RESET_ALL}")
    else:
        need = min_players - player_count
        print(f"  {Fore.YELLOW}⏳ Waiting for {need} more player(s)...{Style.RESET_ALL}")
    
    print()


# ══════════════════════════════════════════════
# Countdown Timer
# ══════════════════════════════════════════════

def show_countdown_warning(seconds: int):
    """Display a dramatic countdown warning."""
    if seconds <= 5:
        color = Fore.RED
    elif seconds <= 15:
        color = Fore.YELLOW
    else:
        color = Fore.CYAN
    
    print(f"  {color}{Style.BRIGHT}⏰ {seconds} seconds remaining!{Style.RESET_ALL}")


# ══════════════════════════════════════════════
# Detective Display
# ══════════════════════════════════════════════

def show_investigation_result(target: str, result: str, is_mafia: bool):
    """Display the Detective's investigation result."""
    print()
    if is_mafia:
        color = Fore.RED
        icon = "🔴"
        verdict = "MAFIA"
    else:
        color = Fore.GREEN
        icon = "🟢"
        verdict = "TOWN"
    
    print(f"  {Fore.CYAN}{Style.BRIGHT}┌────── 🔍 INVESTIGATION RESULT ──────┐{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}│  Target: {Fore.WHITE}{target}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}│  Finding: {color}{icon} {verdict}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}│{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}└─────────────────────────────────────┘{Style.RESET_ALL}")
    print(f"  {Style.DIM}Use this knowledge wisely, Detective.{Style.RESET_ALL}")
    print()


def show_doctor_save():
    """Display that the Doctor saved someone."""
    print()
    print(f"  {Fore.GREEN}{Style.BRIGHT}💉 ═══ MIRACULOUS SAVE! ═══ 💉{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}The Doctor's protection held strong!{Style.RESET_ALL}")
    print(f"  {Fore.GREEN}The Mafia's target survived the night.{Style.RESET_ALL}")
    print()


# ══════════════════════════════════════════════
# Spectator Mode Display
# ══════════════════════════════════════════════

def show_spectator_banner():
    """Display the spectator mode entry banner."""
    print()
    print(f"  {Fore.LIGHTBLACK_EX}{Style.BRIGHT}")
    print(f"  ╔════════════════════════════════════════╗")
    print(f"  ║                                        ║")
    print(f"  ║     👻  S P E C T A T O R  👻         ║")
    print(f"  ║         M O D E                        ║")
    print(f"  ║                                        ║")
    print(f"  ║   You can see everything.              ║")
    print(f"  ║   You can say nothing.                 ║")
    print(f"  ║                                        ║")
    print(f"  ╚════════════════════════════════════════╝")
    print(f"  {Style.RESET_ALL}")


def show_spectator_roles(roles: dict):
    """Display all roles to a spectator."""
    print(f"  {Fore.LIGHTBLACK_EX}{Style.BRIGHT}═══ ALL ROLES REVEALED ═══{Style.RESET_ALL}")
    print(f"  {DIVIDER_THIN}")
    
    for name, info in roles.items():
        role = info.get("role", "?")
        team = info.get("team", "?")
        survived = info.get("survived", True)
        role_color = ROLE_COLORS.get(role, Fore.WHITE)
        status = f"{Fore.GREEN}alive{Style.RESET_ALL}" if survived else f"{Fore.RED}dead{Style.RESET_ALL}"
        
        print(f"    {role_color}{name:12s}  {role:12s}{Style.RESET_ALL}  ({status})")
    
    print(f"  {DIVIDER_THIN}")
    print(f"  {Style.DIM}You can see Mafia chat and vote details.{Style.RESET_ALL}")
    print()


# ══════════════════════════════════════════════
# Night Banner — Detective
# ══════════════════════════════════════════════

def show_night_detective(round_num: int, duration: int = 0):
    """Night banner for the Detective."""
    clear_screen()
    terminal_bell()
    
    print(f"{Fore.BLUE}{Style.BRIGHT}{NIGHT_BANNER}{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{Style.BRIGHT}Round {round_num}{Style.RESET_ALL}")
    
    if duration:
        print(f"  {Style.DIM}Time limit: {duration} seconds{Style.RESET_ALL}")
    
    print()
    typewriter(f"  {narrate_night_fall()}", delay=0.015, color=Fore.BLUE)
    print()
    
    print(f"  {Fore.CYAN}{Style.BRIGHT}╔═══════════════════════════════════╗{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}║  🔍 You are the DETECTIVE.       ║{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}║     Choose a player to            ║{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}║     investigate. Use:             ║{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}║     /investigate <name> or <#>    ║{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}{Style.BRIGHT}╚═══════════════════════════════════╝{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{DIVIDER_NIGHT}{Style.RESET_ALL}\n")


# ══════════════════════════════════════════════
# Night Banner — Doctor
# ══════════════════════════════════════════════

def show_night_doctor(round_num: int, duration: int = 0):
    """Night banner for the Doctor."""
    clear_screen()
    terminal_bell()
    
    print(f"{Fore.BLUE}{Style.BRIGHT}{NIGHT_BANNER}{Style.RESET_ALL}")
    print(f"  {Fore.BLUE}{Style.BRIGHT}Round {round_num}{Style.RESET_ALL}")
    
    if duration:
        print(f"  {Style.DIM}Time limit: {duration} seconds{Style.RESET_ALL}")
    
    print()
    typewriter(f"  {narrate_night_fall()}", delay=0.015, color=Fore.BLUE)
    print()
    
    print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}╔═══════════════════════════════════╗{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}║  💉 You are the DOCTOR.          ║{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}║     Choose a player to            ║{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}║     protect. Use:                 ║{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}║     /protect <name> or <#>        ║{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTGREEN_EX}{Style.BRIGHT}╚═══════════════════════════════════╝{Style.RESET_ALL}")
    
    print(f"\n{Fore.BLUE}{DIVIDER_NIGHT}{Style.RESET_ALL}\n")


# ══════════════════════════════════════════════
# Task Display
# ══════════════════════════════════════════════

def show_task_list(tasks: list):
    """Display the list of tasks for the player."""
    if not tasks:
        return
    print(f"\n  {Fore.CYAN}{Style.BRIGHT}═══ 📋 YOUR TASKS ═══{Style.RESET_ALL}")
    for t in tasks:
        diff_color = Fore.GREEN if t['difficulty'] == 'easy' else Fore.YELLOW if t['difficulty'] == 'medium' else Fore.RED
        if t.get('completed', False):
            # Strikethrough for completed tasks
            print(f"  {Style.DIM}\033[9m[{t['difficulty'].upper()}] {t['display']} (COMPLETED)\033[0m{Style.RESET_ALL}")
        else:
            print(f"  {diff_color}[{t['difficulty'].upper()}]{Style.RESET_ALL} {Fore.CYAN}{t['display']}{Style.RESET_ALL} {Style.DIM}{t.get('hint', '')}{Style.RESET_ALL}")
    print(f"  {Style.DIM}Use: /task <answer> to complete.{Style.RESET_ALL}\n")

def show_task_progress(total: int, completed: int, percentage: int):
    """Display the global task bar."""
    if total == 0:
        return
    bar_len = 30
    filled = int((percentage / 100) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    
    color = Fore.GREEN if percentage == 100 else Fore.CYAN
    print(f"\n  {color}{Style.BRIGHT}TOWN TASK PROGRESS:{Style.RESET_ALL}")
    print(f"  {color}[{bar}] {percentage}% ({completed}/{total}){Style.RESET_ALL}\n")

def show_task_result(correct: bool, message: str):
    """Display the result of a task submission."""
    color = Fore.GREEN if correct else Fore.RED
    print(f"\n  {color}{Style.BRIGHT}{message}{Style.RESET_ALL}\n")





# ══════════════════════════════════════════════
# Enhanced Game Over (with special role history)
# ══════════════════════════════════════════════

def show_match_history(detective_results: list, doctor_saves: list):
    """Display special role action history at game end."""
    if detective_results:
        print(f"\n  {Style.BRIGHT}═══ 🔍 DETECTIVE LOG ═══{Style.RESET_ALL}")
        print(f"  {DIVIDER_THIN}")
        for entry in detective_results:
            r = entry.get("round", "?")
            target = entry.get("target", "?")
            result = entry.get("result", "?")
            icon = "🔴" if result == "Mafia" else "🟢"
            color = Fore.RED if result == "Mafia" else Fore.GREEN
            print(f"    Round {r}: Investigated {target} → {color}{icon} {result}{Style.RESET_ALL}")
        print(f"  {DIVIDER_THIN}")
    
    if doctor_saves:
        print(f"\n  {Style.BRIGHT}═══ 💉 DOCTOR SAVES ═══{Style.RESET_ALL}")
        print(f"  {DIVIDER_THIN}")
        for entry in doctor_saves:
            r = entry.get("round", "?")
            saved = entry.get("saved", "?")
            print(f"    Round {r}: {Fore.GREEN}Saved {saved} from death!{Style.RESET_ALL}")
        print(f"  {DIVIDER_THIN}")

