"""
utils.py — Shared utility functions for Terminal Mafia
"""

import socket
import uuid


def get_local_ip() -> str:
    """
    Get the local LAN IP address of this machine.
    Used to display the IP that other players should connect to.
    
    Returns:
        Local IP as a string, e.g. '192.168.1.42'.
        Falls back to '127.0.0.1' if detection fails.
    """
    try:
        # Create a UDP socket and "connect" to an external address
        # This doesn't actually send data, just determines the local interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def generate_player_id() -> str:
    """Generate a short unique player ID."""
    return uuid.uuid4().hex[:8]


def sanitize_name(name: str, max_length: int = 16) -> str:
    """
    Sanitize a player name:
    - Strip whitespace
    - Limit length
    - Replace disallowed characters
    
    Args:
        name: Raw player name
        max_length: Max allowed characters
    
    Returns:
        Cleaned player name
    """
    name = name.strip()
    # Remove control characters and newlines
    name = "".join(c for c in name if c.isprintable() and c != "\n")
    # Truncate
    name = name[:max_length]
    # Fallback if empty
    if not name:
        name = f"Player_{generate_player_id()[:4]}"
    return name
