import sys
import os
import time

# Fix Windows terminal encoding for emoji/unicode support
if sys.platform == "win32":
    os.system("")  # Enable ANSI escape sequences on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from colorama import Fore, Style
except ImportError:
    class Fore:
        RED = GREEN = YELLOW = CYAN = MAGENTA = WHITE = BLUE = RESET = ""
    class Style:
        BRIGHT = DIM = RESET_ALL = ""

from assets.ascii_art import TITLE
from client.display import clear_screen
from common.constants import DEFAULT_PORT, MIN_PLAYERS, MAX_PLAYERS
from server.server import GameServer
from client.client import GameClient

def run_server_interactive():
    clear_screen()
    print(f"{Fore.GREEN}{Style.BRIGHT}--- HOST A GAME ---{Style.RESET_ALL}\n")
    
    port = DEFAULT_PORT

    min_players = MIN_PLAYERS
    try:
        min_input = input(f"Enter minimum players (press Enter for {MIN_PLAYERS}): ").strip()
        if min_input:
            min_players = int(min_input)
    except ValueError:
        pass
        
    max_players = MAX_PLAYERS
    try:
        max_input = input(f"Enter maximum players (press Enter for {MAX_PLAYERS}): ").strip()
        if max_input:
            max_players = int(max_input)
    except ValueError:
        pass

    server = GameServer(port=port, min_players=min_players, max_players=max_players)

    try:
        server.start()
        print(f"\n{Fore.GREEN}[Server] Server running. Press Ctrl+C to stop the server.{Style.RESET_ALL}\n")
        while server.running:
            try:
                cmd = input()
                cmd = cmd.strip().lower()
                if cmd in ("/quit", "/stop", "/exit"):
                    break
                elif cmd == "/players":
                    names = server.get_player_names()
                    print(f"[Server] Connected players ({len(names)}): {', '.join(names) if names else 'none'}")
                elif cmd == "/help":
                    print("[Server] Commands: /players, /quit, /stop, /exit, /help")
                elif cmd:
                    print(f"[Server] Unknown command: {cmd}. Type /help for commands.")
            except EOFError:
                break
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()

def run_client_interactive():
    clear_screen()
    print(f"{Fore.CYAN}{Style.BRIGHT}--- JOIN A GAME ---{Style.RESET_ALL}\n")
    
    try:
        host_input = input(f"Enter server IP (press Enter for localhost): ").strip()
        host = host_input if host_input else "localhost"
        
        port = DEFAULT_PORT
        
        player_name = input(f"Enter your name: ").strip()
        if not player_name:
            player_name = "Player"
            
    except (EOFError, KeyboardInterrupt):
        return


    print(f"\n{Fore.YELLOW}Connecting to {host}:{port}...{Style.RESET_ALL}\n")

    client = GameClient(host=host, port=port, player_name=player_name)

    if not client.connect():
        print(f"\n{Fore.RED}Failed to connect. Make sure the server is running.{Style.RESET_ALL}")
        input("Press Enter to exit...")
        return

    time.sleep(0.5)
    print(f"\n{Style.DIM}Commands: type a message to chat, /start to begin, /quit to leave{Style.RESET_ALL}")
    print(f"{Style.DIM}{'─' * 50}{Style.RESET_ALL}\n")

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

            if user_input.lower() in ("/quit", "/exit", "/leave"):
                print(f"\n{Fore.YELLOW}Leaving the game...{Style.RESET_ALL}")
                break

            is_info_command = user_input.lower() in ("/players", "/role", "/suspicion", "/help")
            is_task_command = user_input.lower().startswith("/task")
            if client.is_spectator and not (is_info_command or is_task_command) and not user_input.startswith("/quit"):
                print(f"{Fore.LIGHTBLACK_EX}You are a spectator. You can only observe and do tasks.{Style.RESET_ALL}")
                continue

            if user_input.lower() == "/start":
                client.send_start_game()
            elif user_input.lower().startswith("/vote "):
                target = user_input[6:].strip()
                if target:
                    client.send_vote(target)
                else:
                    print(f"{Fore.RED}Usage: /vote <player_name> or /vote <number>{Style.RESET_ALL}")
            elif user_input.lower().startswith("/kill "):
                target = user_input[6:].strip()
                if target:
                    client.send_night_action(target, action="kill")
                else:
                    print(f"{Fore.RED}Usage: /kill <player_name> or /kill <number>{Style.RESET_ALL}")
            elif user_input.lower().startswith("/investigate "):
                target = user_input[13:].strip()
                if target:
                    client.send_night_action(target, action="investigate")
                else:
                    print(f"{Fore.RED}Usage: /investigate <player_name> or /investigate <number>{Style.RESET_ALL}")
            elif user_input.lower().startswith("/protect "):
                target = user_input[9:].strip()
                if target:
                    client.send_night_action(target, action="protect")
            elif user_input.lower().startswith("/task "):
                answer = user_input[6:].strip()
                if answer:
                    client.send_task_submit("", answer)
                else:
                    print(f"{Fore.RED}Usage: /task <answer>{Style.RESET_ALL}")
            elif user_input.lower() == "/players":
                if client.alive_players:
                    print(f"\n{Style.BRIGHT}Alive players:{Style.RESET_ALL}")
                    for i, name in enumerate(client.alive_players, 1):
                        marker = f"{Fore.YELLOW}★{Style.RESET_ALL}" if name == client.player_name else " "
                        print(f"  {marker} {i}. {name}")
                    print()
                elif client.lobby_players:
                    print(f"\n{Style.BRIGHT}Players in lobby:{Style.RESET_ALL}")
                    for i, name in enumerate(client.lobby_players, 1):
                        print(f"  {i}. {name}")
                    print()
                else:
                    print(f"{Fore.YELLOW}No player list available yet.{Style.RESET_ALL}")
            elif user_input.lower() == "/role":
                if client.role:
                    role_color = Fore.RED if client.role == "Mafia" else Fore.GREEN
                    print(f"\nYour role: {role_color}{Style.BRIGHT}{client.role}{Style.RESET_ALL} ({client.team})\n")
                else:
                    print(f"{Style.DIM}No role assigned yet. Game hasn't started.{Style.RESET_ALL}")
            elif user_input.lower() == "/suspicion":
                counts = client.get_suspicion_counts()
                if counts:
                    from client.display import show_suspicion_meter
                    show_suspicion_meter(counts)
                else:
                    print(f"{Style.DIM}No chat data yet. Discuss first!{Style.RESET_ALL}")
            elif user_input.lower() == "/help":
                print(f"\n{Style.BRIGHT}Commands:{Style.RESET_ALL}")
                print(f"  /start         — Start the game (need min players)")
                print(f"  /vote <name/#> — Vote to eliminate (day phase)")
                print(f"  /kill <name/#> — Choose night target (Mafia only)")
                print(f"  /investigate <name/#> — Investigate player (Detective only)")
                print(f"  /protect <name/#> — Protect player (Doctor only)")
                print(f"  /task <answer> — Submit answer for a night task")
                print(f"  /players       — Show alive players")
                print(f"  /role          — Show your current role")
                print(f"  /suspicion     — Show suspicion meter")
                print(f"  /quit          — Leave the game")
                print(f"  /help          — Show this help")
                print(f"  (anything else) — Send as chat message\n")
            elif user_input.startswith("/"):
                print(f"{Fore.RED}Unknown command: {user_input}. Type /help{Style.RESET_ALL}")
            else:
                client.send_chat(user_input)
    except KeyboardInterrupt:
        print(f"\n\n{Fore.YELLOW}Disconnecting...{Style.RESET_ALL}")
    finally:
        client.disconnect()
        print(f"{Style.DIM}Thanks for playing Terminal Mafia! 🎭{Style.RESET_ALL}\n")

def main():
    clear_screen()
    print(f"{Fore.RED}{Style.BRIGHT}{TITLE}{Style.RESET_ALL}")
    print(f"  {Fore.YELLOW}{Style.BRIGHT}  A terminal-based social deduction game{Style.RESET_ALL}")
    print(f"\nWhat would you like to do?")
    print(f"  {Fore.GREEN}1. Host a new game (Server){Style.RESET_ALL}")
    print(f"  {Fore.CYAN}2. Join an existing game (Client){Style.RESET_ALL}")
    print(f"  {Fore.WHITE}3. Quit{Style.RESET_ALL}")
    
    try:
        while True:
            choice = input(f"\nSelect an option (1-3): ").strip()
            if choice == "1":
                run_server_interactive()
                break
            elif choice == "2":
                run_client_interactive()
                break
            elif choice == "3":
                break
            else:
                print("Invalid choice.")
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")

if __name__ == "__main__":
    main()
