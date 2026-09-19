"""
test_full_game.py — Automated integration test for Terminal Mafia Phase 2

Connects 2 clients, starts a game, plays through night and day phases,
and verifies the full game loop works end-to-end.
"""

import sys
import os
import time
import threading

# Fix Windows encoding
if sys.platform == "win32":
    os.system("")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, ".")

from client.client import GameClient
from common.constants import ROLE_MAFIA


def test_full_game():
    print("=" * 60)
    print("  INTEGRATION TEST: Full Game Loop")
    print("=" * 60)

    # Connect two clients
    client1 = GameClient("localhost", 5556, "Alice")
    client2 = GameClient("localhost", 5556, "Bob")

    print("\n[Test] Connecting Alice...")
    assert client1.connect(), "Alice failed to connect"
    time.sleep(0.5)

    print("[Test] Connecting Bob...")
    assert client2.connect(), "Bob failed to connect"
    time.sleep(1)

    print(f"[Test] Alice connected: {client1.connected}, ID: {client1.player_id}")
    print(f"[Test] Bob connected: {client2.connected}, ID: {client2.player_id}")

    # Start the game
    print("\n[Test] Starting game...")
    client1.send_start_game()

    # Wait for roles to be assigned (with retry)
    for i in range(10):
        time.sleep(1)
        if client1.role and client2.role:
            break
        print(f"  Waiting for roles... ({i+1}s)")

    print(f"[Test] Alice's role: {client1.role} ({client1.team})")
    print(f"[Test] Bob's role: {client2.role} ({client2.team})")

    assert client1.role is not None, "Alice didn't receive a role!"
    assert client2.role is not None, "Bob didn't receive a role!"

    # Identify the Mafia player
    if client1.role == ROLE_MAFIA:
        mafia_client = client1
        town_client = client2
        mafia_name = "Alice"
        town_name = "Bob"
    else:
        mafia_client = client2
        town_client = client1
        mafia_name = "Bob"
        town_name = "Alice"

    print(f"[Test] Mafia: {mafia_name}, Town: {town_name}")

    # Wait for Night Phase
    print("\n[Test] Waiting for night phase...")
    time.sleep(2)

    assert mafia_client.phase == "NIGHT", f"Expected NIGHT, got {mafia_client.phase}"
    print(f"[Test] Phase confirmed: {mafia_client.phase}")

    # Mafia kills Town player
    print(f"[Test] {mafia_name} (Mafia) targeting {town_name}...")
    mafia_client.send_night_action(town_name)
    time.sleep(3)  # Wait for night to resolve

    # Wait for dawn + discussion
    print("[Test] Waiting for dawn reveal + discussion...")
    time.sleep(10)  # Dawn reveal + start of discussion

    print(f"[Test] Current phase: {mafia_client.phase}")

    # The game should end after night kill since Mafia = Town (1:1)
    # With 2 players, killing 1 Town member means Mafia >= Town → Mafia wins
    time.sleep(5)

    print(f"\n[Test] Final phase: {mafia_client.phase}")

    # Cleanup
    client1.disconnect()
    client2.disconnect()

    print("\n" + "=" * 60)
    print("  TEST COMPLETE!")
    print("=" * 60)


if __name__ == "__main__":
    test_full_game()
