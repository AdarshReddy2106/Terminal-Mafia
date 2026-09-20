<div align="center">

# 🎭 Terminal Mafia

**A multiplayer, terminal-based social deduction game of deception, trust, and survival.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

</div>

---

Terminal Mafia is a local-hosted, terminal-exclusive multiplayer game built for the **IAC Hackathon**. Gather your friends on the same LAN/Wi-Fi network, launch the single executable file, and uncover the traitors among you!

## ✨ Features

- **🎯 Special Roles**: Play as a humble Villager, the deceiving Mafia, the investigating Detective, or the protecting Doctor.
- **🎨 Immersive Terminal UI**: Experience the game entirely through your command line, complete with dynamic ASCII art, colored text themes, and dramatic typewriter animations.
- **🕒 Timed Game Loop**: Navigate through the structured phases of Night (Secret Actions), Dawn (Reveals), Discussion (Timed Chat), and Voting.
- **📋 Task System**: Villagers and spectators receive tasks each Night. Complete them to push the Town closer to victory — finish all tasks and the Town wins outright! A live **task bar** tracks overall completion in real time.
- **👻 Spectator Mode**: Death is not the end. Eliminated players can still spectate the game, see everyone's true roles, read the private Mafia chat, **and continue completing their assigned tasks** to help the Town win.
- **📖 End-Game Match History**: At the end of every match, the game prints a full chronological timeline of Detective investigations, Doctor saves, and who voted for whom.
- **🔌 Unified Executable**: No complicated setup. A single `.exe` file gives you an interactive menu to either host a server or join a game.

---

## 📋 How the Task System Works

Tasks are a core mechanic that gives Villagers (and spectators) a second path to victory beyond voting out the Mafia.

| Detail | Description |
|---|---|
| **When are tasks assigned?** | Fresh tasks are allocated to each player at the start of every **Night** phase. |
| **Who can do tasks?** | All **Villagers** and **Spectators** (eliminated players) can complete their assigned tasks. |
| **What happens when I complete a task?** | The task is ~~struck through~~ in your list, and the global **task bar** updates to reflect the Town's overall progress. |
| **What if I don't finish a task?** | Incomplete tasks are **not** carried over. They are replaced with **brand-new tasks** in the next round, keeping the gameplay fresh and engaging every single round. |
| **How does the Town win via tasks?** | If **all allocated tasks across all players are completed**, the **Town wins immediately** — no vote required! |

> **💡 Tip:** Even as a spectator, your contributions matter! Keep completing tasks after elimination to give your team the edge.

---

## 🌙 Night Phase Mechanics

The Night phase is when secret actions take place. Here's what each role can do:

| Role | Night Action |
|---|---|
| **🔪 Mafia** | Choose a target to assassinate — but beware of the **15-second kill cooldown**. After the Night begins, the Mafia must wait 15 seconds before they can issue a `/kill` command. |
| **🔍 Detective** | Investigate a player to learn their true allegiance (Town or Mafia). |
| **🛡️ Doctor** | Shield a player to protect them from being killed that night. |
| **🏘️ Villagers** | Complete your assigned tasks to push the task bar toward a Town victory. |
| **👻 Spectators** | Continue completing tasks — you can still help the Town win from beyond the grave! |

---

## 🏆 Win Conditions

| Team | How They Win |
|---|---|
| **🏘️ Town** | Vote out all Mafia members **OR** complete all allocated tasks across every round. |
| **🔪 Mafia** | Outnumber the remaining Villagers so they can no longer be voted out. |

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

| Command | Description |
|---|---|
| `/vote <number>` | Cast your vote to eliminate someone during the Day phase. |
| `/kill <number>` | *(Mafia Only)* Choose a target to assassinate during the Night (15s cooldown applies). |
| `/investigate <number>` | *(Detective Only)* Learn a player's true allegiance during the Night. |
| `/protect <number>` | *(Doctor Only)* Shield a player from death during the Night. |
| `/players` | Check who is currently alive. |
| `/role` | View your assigned role and team. |
| `/help` | List all available commands. |

---

## 🛠️ For Developers

Interested in how it was built? Terminal Mafia uses a heavily multi-threaded TCP socket architecture with a strict JSON message protocol to ensure no client can cheat or intercept private data. 

Check out the [Technical Architecture Guide](TECHNICAL_ARCHITECTURE.md) for a deep dive into the Game Engine, Server structure, and Client Display engine!

---

<div align="center">
  <i>Built with ❤️ for the IAC Hackathon</i>
</div>