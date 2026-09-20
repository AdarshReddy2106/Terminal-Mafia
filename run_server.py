"""
run_server.py — Entry point to start the Terminal Mafia game server.

Usage:
    python run_server.py
    python run_server.py --port 5555
    python run_server.py --port 5555 --min-players 4 --max-players 8
"""

import argparse
import sys
import os


# Fix Windows terminal encoding for emoji/unicode support
if sys.platform == "win32":
    os.system("")  # Enable ANSI escape sequences on Windows
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from common.constants import DEFAULT_PORT, MIN_PLAYERS, MAX_PLAYERS
from server.server import GameServer


def main():
    parser = argparse.ArgumentParser(
        description="Terminal Mafia — Game Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_server.py                         Start with defaults (port 5555, 4-10 players)
  python run_server.py --port 7777             Use port 7777
  python run_server.py --min-players 3         Allow game start with 3 players
        """
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--min-players", type=int, default=MIN_PLAYERS,
        help=f"Minimum players to start game (default: {MIN_PLAYERS})"
    )
    parser.add_argument(
        "--max-players", type=int, default=MAX_PLAYERS,
        help=f"Maximum players allowed (default: {MAX_PLAYERS})"
    )

    args = parser.parse_args()

    # Validate
    if args.min_players < 2:
        print("Error: Minimum players must be at least 2.")
        sys.exit(1)
    if args.max_players < args.min_players:
        print("Error: Max players must be >= min players.")
        sys.exit(1)

    server = GameServer(
        port=args.port,
        min_players=args.min_players,
        max_players=args.max_players
    )

    try:
        server.start()


        # Keep main thread alive — server threads are daemon threads
        print("[Server] Press Ctrl+C to stop the server.\n")
        while server.running:
            try:
                # Read server console input for admin commands
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


if __name__ == "__main__":
    main()
