<div align="center">

# 🎭 Terminal Mafia

**A multiplayer, terminal-based social deduction game of deception, trust, and survival.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

Terminal Mafia is a local-hosted, terminal-exclusive multiplayer game built for the **IAC Hackathon**. Gather your friends on the same LAN/Wi-Fi network, launch the single executable file, and uncover the traitors among you!

## ✨ Features

- **🎯 Special Roles**: Play as a humble Villager, the deceiving Mafia, the investigating Detective, or the protecting Doctor.
- **🎨 Immersive Terminal UI**: Experience the game entirely through your command line, complete with dynamic ASCII art, colored text themes, and dramatic typewriter animations.
- **🕒 Timed Game Loop**: Navigate through the structured phases of Night (Secret Actions), Dawn (Reveals), Discussion (Timed Chat), and Voting.
- **📊 Suspicion Meter**: The terminal actively visualizes chat frequency, creating a heat map to see who is talking too much—or too little!
- **👻 Spectator Mode**: Death is not the end. Eliminated players can spectate the game, see everyone's true roles, and secretly read the private Mafia chat.
- **📖 End-Game Match History**: At the end of every match, the game prints a full chronological timeline of Detective investigations, Doctor saves, and who voted for whom.
- **🔌 Unified Executable**: No complicated setup. A single `.exe` file gives you an interactive menu to either host a server or join a game.

---

## ✅ Hackathon Requirements Checklist

### Core Requirements
- [x] Supports 4+ players with hidden, role-based information (each player only sees what their role permits)
- [x] A structured game loop: role assignment → phases (e.g., night/day, discuss/vote) → elimination → win condition
- [x] Fully playable via terminal input/output: text-based only, no GUI frameworks
- [x] Reasonably graceful handling of a player disconnecting or submitting invalid input mid-game
- [x] A clear, unambiguous win condition for each side (e.g., Mafia eliminated / Mafia outnumbers Villagers)

### Stretch Goals (Optional, Bonus Credit)
- [ ] AI-controlled bot players to fill out a lobby when fewer humans are available *(Note: AI bots were successfully built but later removed to keep the game human-only)*
- [x] Spectator mode for eliminated players
- [x] Additional special roles (e.g., Detective, Doctor, Double Agent) beyond the basic two sides *(Detective and Doctor are fully implemented)*
- [x] Match history / replay of role reveals and voting patterns at game end

---

## 🚀 How to Play

You do not need to install Python to play! 

### 1. Download the Executable
Grab the `TerminalMafia.exe` file from the `dist/` directory and share it with your friends. Everyone should be on the same Local Area Network (Wi-Fi or Hotspot).

### 2. Host the Game (1 Player)
One player acts as the server host. 
- Double click `TerminalMafia.exe`.
- Select **Option 1: Host a new game**.
- The server will start and display a **Server IP** (e.g., `192.168.1.5`).

### 3. Join the Game (All Players)
All players (including the host, on a separate window) connect to the server.
- Double click `TerminalMafia.exe`.
- Select **Option 2: Join an existing game**.
- When prompted, type in the **Server IP** shown on the host's screen.
- Type in your name and you're in the lobby!

Once enough players have joined (Minimum: 4), anyone can type `/start` in the chat to begin the chaos.

---

## 💻 In-Game Commands

During the game, typing anything in the console acts as a normal chat message. However, there are special commands you can use depending on the phase:

- `/vote <number>` — Cast your vote to eliminate someone during the Day phase.
- `/kill <number>` — (Mafia Only) Choose a target to assassinate during the Night.
- `/investigate <number>` — (Detective Only) Learn a player's true allegiance during the Night.
- `/protect <number>` — (Doctor Only) Protect a player from death during the Night.
- `/players` — Check who is currently alive.
- `/role` — View your assigned role and team.
- `/suspicion` — View the suspicion meter heat map.
- `/help` — List all available commands.

---

## 🛠️ For Developers

Interested in how it was built? Terminal Mafia uses a heavily multi-threaded TCP socket architecture with a strict JSON message protocol to ensure no client can cheat or intercept private data. 

Check out the [Technical Architecture Guide](TECHNICAL_ARCHITECTURE.md) for a deep dive into the Game Engine, Server structure, and Client Display engine!

---

<div align="center">
  <i>Built with ❤️ for the IAC Hackathon</i>
</div>
