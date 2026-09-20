# 🏗️ Technical Architecture

Terminal Mafia is a multiplayer, terminal-based social deduction game built in Python. This document outlines the core architecture, design patterns, and technical decisions that power the game.

---

## 1. High-Level Architecture

The game uses a **Client-Server Architecture** communicating over **TCP Sockets**. 

- **Server:** Acts as the single source of truth. It manages the game state, orchestrates phases, handles secret role information, and prevents client-side cheating.
- **Client:** A lightweight terminal interface that connects to the server, renders the UI (ASCII art, colors), and captures user input.

```mermaid
graph TD
    S[Game Server (TCP)] <-->|JSON Protocol| C1[Client 1]
    S <-->|JSON Protocol| C2[Client 2]
    S <-->|JSON Protocol| C3[Client N]
```

---

## 2. Server Architecture

The server is broken down into several modular components to separate networking from game logic.

### `GameServer` (Networking & Lobby)
- **Role:** Handles accepting incoming TCP connections using Python's `socket` library.
- **Concurrency:** Spawns a dedicated background thread (`PlayerConnection`) for every connected client to read messages asynchronously without blocking the main thread.
- **Lobby Management:** Tracks connected players and broadcasts lobby status updates.

### `GameEngine` (Core Loop)
- **Role:** Orchestrates the complex state machine of the game (Night → Dawn → Discussion → Voting).
- **Execution:** Runs on its own background thread, continuously ticking and checking timers.
- **Responsibilities:** Evaluates when phases should transition based on time limits or player actions (e.g., all players have voted).

### `RoleManager` & `StateManager`
- **RoleManager:** Dynamically calculates the number of Mafia needed based on the total player count and randomly assigns roles (Villager, Mafia, Detective, Doctor).
- **StateManager:** Provides thread-safe data structures (`threading.Lock`) to store who is alive, who is dead, current votes, and night action targets. It constantly evaluates if a **Win Condition** has been met.

---

## 3. Client Architecture

The client focuses strictly on rendering an immersive terminal experience and forwarding user inputs.

### `GameClient` (Networking)
- **Role:** Maintains a persistent TCP connection to the server.
- **Concurrency:** Uses a background `Receiver Thread` to constantly listen for incoming JSON packets and push them to the UI, allowing the user to type commands simultaneously.

### `DisplayEngine` (UI/UX)
- **Role:** Handles cross-platform screen clearing and color manipulation using `colorama`.
- **Features:** 
  - Renders dynamic ASCII art headers for different phases.
  - Animates text using a typewriter effect.
  - Visualizes data, such as calculating chat frequency to display a visual **Suspicion Meter**.

### `Narrator` (Atmosphere)
- **Role:** A narrative engine containing randomized templates. Instead of hardcoded strings, the game dynamically generates dramatic text for deaths, saves, and role reveals to keep the game fresh.

---

## 4. Message Protocol (JSON)

All communication uses a strict JSON protocol delimited by newlines (`\n`), solving the TCP stream fragmentation problem.

**Format:**
```json
{
  "type": "MESSAGE_TYPE",
  "data": {
    "key": "value"
  }
}
```

- **Client → Server Examples:** `JOIN`, `CHAT`, `VOTE`, `NIGHT_ACTION`, `PONG`
- **Server → Client Examples:** `ROLE_ASSIGN`, `PHASE_CHANGE`, `CHAT_MSG`, `VOTE_RESULT`, `GAME_OVER`, `PING`

---

## 5. Build & Distribution

To ensure the game is accessible to non-developers, the Python source code is compiled into a standalone executable.

- **Tool:** `PyInstaller`
- **Output:** A single `TerminalMafia.exe` file.
- **Unified Launcher:** The compiled executable features a unified interactive menu allowing a user to either *Host a Server* or *Join a Game* from the same binary, drastically simplifying distribution.
