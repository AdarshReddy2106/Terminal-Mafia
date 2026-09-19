"""
run_client.py — Entry point to join a Terminal Mafia game as a player.

Usage:
    python run_client.py --name "Alice"
    python run_client.py --host 192.168.1.42 --port 5555 --name "Bob"
"""

import argparse
import sys
import os
import time

# Fix Windows terminal encoding for emoji/unicode support
if sys.platform == "win32":
    os.system("")  # Enable ANSI escape sequences on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from common.constants import DEFAULT_PORT
from client.client import GameClient

# Try colorama for colored output
try:
    from colorama import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""


TITLE_ART = f"""
{Fore.RED}{Style.BRIGHT}
  ╔════════════════════════════════════════════════════════╗
  ║                                                        ║
  ║   ████████╗███████╗██████╗ ███╗   ███╗██╗███╗   ██╗   ║
  ║      ██╔══╝██╔════╝██╔══██╗████╗ ████║██║████╗  ██║   ║
  ║      ██║   █████╗  ██████╔╝██╔████╔██║██║██╔██╗ ██║   ║
  ║      ██║   ██╔══╝  ██╔══██╗██║╚██╔╝██║██║██║╚██╗██║   ║
  ║      ██║   ███████╗██║  ██║██║ ╚═╝ ██║██║██║ ╚████║   ║
  ║      ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝   ║
  ║                                                        ║
  ║{Fore.WHITE}          ███╗   ███╗ █████╗ ███████╗██╗ █████╗         {Fore.RED}║
  ║{Fore.WHITE}          ████╗ ████║██╔══██╗██╔════╝██║██╔══██╗        {Fore.RED}║
  ║{Fore.WHITE}          ██╔████╔██║███████║█████╗  ██║███████║        {Fore.RED}║
  ║{Fore.WHITE}          ██║╚██╔╝██║██╔══██║██╔══╝  ██║██╔══██║        {Fore.RED}║
  ║{Fore.WHITE}          ██║ ╚═╝ ██║██║  ██║██║     ██║██║  ██║        {Fore.RED}║
  ║{Fore.WHITE}          ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═╝        {Fore.RED}║
  ║                                                        ║
  ╚════════════════════════════════════════════════════════╝
{Style.RESET_ALL}
{Fore.YELLOW}{Style.BRIGHT}  A terminal-based social deduction game{Style.RESET_ALL}
"""


def main():
    parser = argparse.ArgumentParser(
        description="Terminal Mafia — Join a Game",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_client.py --name "Alice"                            Connect to localhost
  python run_client.py --host 192.168.1.42 --port 5555 --name "Bob"  Connect to LAN host
        """
    )
    parser.add_argument(
        "--host", type=str, default="localhost",
        help="Server IP address (default: localhost)"
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Server port (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--name", type=str, default=None,
        help="Your player name"
    )

    args = parser.parse_args()

    # Show title
    print(TITLE_ART)

    # Get player name if not provided via args
    player_name = args.name
    if not player_name:
        try:
            player_name = input(f"  {Fore.CYAN}Enter your name:{Style.RESET_ALL} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            sys.exit(0)

    if not player_name:
        player_name = "Player"

    # Connect
    print(f"\n  {Fore.YELLOW}Connecting to {args.host}:{args.port}...{Style.RESET_ALL}\n")

    client = GameClient(host=args.host, port=args.port, player_name=player_name)

    if not client.connect():
        print(f"\n  {Fore.RED}Failed to connect. Make sure the server is running.{Style.RESET_ALL}")
        sys.exit(1)

    # Wait a moment for welcome message
    time.sleep(0.5)

    # Main input loop
    print(f"\n  {Style.DIM}Commands: type a message to chat, /start to begin, /quit to leave{Style.RESET_ALL}")
    print(f"  {Style.DIM}{'─' * 50}{Style.RESET_ALL}\n")

    try:
        while client.connected:
            try:
                user_input = input()
            except EOFError:
                break

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle client-side commands
            if user_input.lower() in ("/quit", "/exit", "/leave"):
                print(f"\n  {Fore.YELLOW}Leaving the game...{Style.RESET_ALL}")
                break

            elif user_input.lower() == "/start":
                client.send_start_game()

            elif user_input.lower().startswith("/vote "):
                target = user_input[6:].strip()
                if target:
                    client.send_vote(target)
                else:
                    print(f"  {Fore.RED}Usage: /vote <player_name>{Style.RESET_ALL}")

            elif user_input.lower().startswith("/kill "):
                target = user_input[6:].strip()
                if target:
                    client.send_night_action(target)
                else:
                    print(f"  {Fore.RED}Usage: /kill <player_name>{Style.RESET_ALL}")

            elif user_input.lower() == "/players":
                if client.alive_players:
                    print(f"\n  {Style.BRIGHT}Alive players:{Style.RESET_ALL}")
                    for i, name in enumerate(client.alive_players, 1):
                        print(f"    {i}. {name}")
                    print()
                elif client.lobby_players:
                    print(f"\n  {Style.BRIGHT}Players in lobby:{Style.RESET_ALL}")
                    for i, name in enumerate(client.lobby_players, 1):
                        print(f"    {i}. {name}")
                    print()
                else:
                    print(f"  {Fore.YELLOW}No player list available yet.{Style.RESET_ALL}")

            elif user_input.lower() == "/role":
                if client.role:
                    role_color = Fore.RED if client.role == "Mafia" else Fore.GREEN
                    print(f"\n  Your role: {role_color}{Style.BRIGHT}{client.role}{Style.RESET_ALL} ({client.team})\n")
                else:
                    print(f"  {Style.DIM}No role assigned yet. Game hasn't started.{Style.RESET_ALL}")

            elif user_input.lower() == "/help":
                print(f"\n  {Style.BRIGHT}Commands:{Style.RESET_ALL}")
                print(f"    /start      — Start the game (need min players)")
                print(f"    /vote <name> — Vote to eliminate a player (day phase)")
                print(f"    /kill <name> — Choose a night target (Mafia only)")
                print(f"    /players    — Show alive players")
                print(f"    /role       — Show your current role")
                print(f"    /quit       — Leave the game")
                print(f"    /help       — Show this help")
                print(f"    (anything else) — Send as chat message\n")

            elif user_input.startswith("/"):
                print(f"  {Fore.RED}Unknown command: {user_input}. Type /help{Style.RESET_ALL}")

            else:
                # Send as chat message
                client.send_chat(user_input)

    except KeyboardInterrupt:
        print(f"\n\n  {Fore.YELLOW}Disconnecting...{Style.RESET_ALL}")

    finally:
        client.disconnect()
        print(f"  {Style.DIM}Thanks for playing Terminal Mafia!{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
