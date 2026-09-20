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

from assets.ascii_art import TITLE
from client.display import clear_screen


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
        "--host", type=str, default=None,
        help="Server IP address"
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Server port"
    )
    parser.add_argument(
        "--name", type=str, default=None,
        help="Your player name"
    )

    args = parser.parse_args()

    # Show title
    clear_screen()
    print(f"{Fore.RED}{Style.BRIGHT}{TITLE}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}{Style.BRIGHT}  A terminal-based social deduction game{Style.RESET_ALL}")
    print()

    # Get server host
    host = args.host
    if not host:
        try:
            host_input = input(f"  {Fore.CYAN}Enter server IP (press Enter for localhost):{Style.RESET_ALL} ").strip()
            host = host_input if host_input else "localhost"
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            sys.exit(0)

    # Get server port
    port = args.port
    if not port:
        try:
            port_input = input(f"  {Fore.CYAN}Enter server port (press Enter for {DEFAULT_PORT}):{Style.RESET_ALL} ").strip()
            port = int(port_input) if port_input else DEFAULT_PORT
        except ValueError:
            print(f"  {Fore.RED}Invalid port, using default {DEFAULT_PORT}{Style.RESET_ALL}")
            port = DEFAULT_PORT
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            sys.exit(0)


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
    print(f"\n  {Fore.YELLOW}Connecting to {host}:{port}...{Style.RESET_ALL}\n")

    client = GameClient(host=host, port=port, player_name=player_name)

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
                prompt = client.get_input_prompt()
                user_input = input(prompt)
            except EOFError:
                break

            user_input = user_input.strip()
            if not user_input:
                continue



            # Handle client-side commands
            if user_input.lower() in ("/quit", "/exit", "/leave"):
                print(f"\n  {Fore.YELLOW}Leaving the game...{Style.RESET_ALL}")
                break

            # If spectator, block everything except info commands and task submissions
            is_info_command = user_input.lower() in ("/players", "/role", "/suspicion", "/help")
            is_task_command = user_input.lower().startswith("/task")
            if client.is_spectator and not (is_info_command or is_task_command) and not user_input.startswith("/quit"):
                print(f"  {Fore.LIGHTBLACK_EX}You are a spectator. You can only observe and do tasks.{Style.RESET_ALL}")
                continue

            if user_input.lower() == "/start":
                client.send_start_game()

            elif user_input.lower().startswith("/vote "):
                target = user_input[6:].strip()
                if target:
                    client.send_vote(target)
                else:
                    print(f"  {Fore.RED}Usage: /vote <player_name> or /vote <number>{Style.RESET_ALL}")

            elif user_input.lower().startswith("/kill "):
                target = user_input[6:].strip()
                if target:
                    client.send_night_action(target, action="kill")
                else:
                    print(f"  {Fore.RED}Usage: /kill <player_name> or /kill <number>{Style.RESET_ALL}")

            elif user_input.lower().startswith("/investigate "):
                target = user_input[13:].strip()
                if target:
                    client.send_night_action(target, action="investigate")
                else:
                    print(f"  {Fore.RED}Usage: /investigate <player_name> or /investigate <number>{Style.RESET_ALL}")

            elif user_input.lower().startswith("/protect "):
                target = user_input[9:].strip()
                if target:
                    client.send_night_action(target, action="protect")
            elif user_input.lower().startswith("/task "):
                answer = user_input[6:].strip()
                if answer:
                    # Let the server figure out which task the answer is for.
                    # Send empty string as task_id, the server will check all pending tasks.
                    client.send_task_submit("", answer)
                else:
                    print(f"  {Fore.RED}Usage: /task <answer>{Style.RESET_ALL}")

            elif user_input.lower() == "/players":
                if client.alive_players:
                    print(f"\n  {Style.BRIGHT}Alive players:{Style.RESET_ALL}")
                    for i, name in enumerate(client.alive_players, 1):
                        marker = f"{Fore.YELLOW}★{Style.RESET_ALL}" if name == client.player_name else " "
                        print(f"    {marker} {i}. {name}")
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

            elif user_input.lower() == "/suspicion":
                # Show local suspicion meter
                counts = client.get_suspicion_counts()
                if counts:
                    from client.display import show_suspicion_meter
                    show_suspicion_meter(counts)
                else:
                    print(f"  {Style.DIM}No chat data yet. Discuss first!{Style.RESET_ALL}")

            elif user_input.lower() == "/help":
                print(f"\n  {Style.BRIGHT}Commands:{Style.RESET_ALL}")
                print(f"    /start         — Start the game (need min players)")
                print(f"    /vote <name/#> — Vote to eliminate (day phase)")
                print(f"    /kill <name/#> — Choose night target (Mafia only)")
                print(f"    /investigate <name/#> — Investigate player (Detective only)")
                print(f"    /protect <name/#> — Protect player (Doctor only)")
                print(f"    /task <answer> — Submit answer for a night task")
                print(f"    /players       — Show alive players")
                print(f"    /role          — Show your current role")
                print(f"    /suspicion     — Show suspicion meter")
                print(f"    /quit          — Leave the game")
                print(f"    /help          — Show this help")
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
        print(f"  {Style.DIM}Thanks for playing Terminal Mafia! 🎭{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
