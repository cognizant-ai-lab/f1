# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv venv
source venv/bin/activate && export PYTHONPATH=`pwd`   # Mac/Linux
pip install -r requirements.txt
```

For the React frontend:
```bash
cd race_engineer_hub && npm install
```

## Running

| What | Command | Port |
|------|---------|------|
| Agent network + nsflow UI | `python -m run` | 8080 (server), 4173 (nsflow) |
| Telemetry WebSocket bridge | `python -m telemetry_server` | UDP 20777 in, WS 8765 out |
| Race Engineer Hub (React UI) | `cd race_engineer_hub && npm run dev` | 8081 |
| Replay captured telemetry | `python -m telemetry_server --replay data/<file>.f1bin --speed 10x` | |
| Capture live telemetry to .f1bin | `python -m telemetry_server --capture` | |
| Download test data | `./scripts/download_test_data.sh` | |

## Verification

```bash
# Python syntax check (from repo root)
python3 -m py_compile telemetry_server/telemetry_server.py

# TypeScript type check (from race_engineer_hub/)
cd race_engineer_hub && npx tsc --noEmit
```

Python commands require the venv activated and `PYTHONPATH` set to the repo root.

## Architecture

Three main systems communicate at runtime:

1. **Neuro SAN agent network** (`registries/`, `run.py`) — HOCON-defined multi-agent orchestration. Agents are declared in `registries/*.hocon` and registered in `registries/manifest.hocon`. LLM config in `registries/llm_config.hocon` (default: OpenAI gpt-5.2, requires `OPENAI_API_KEY` in `.env`).

2. **Telemetry server** (`telemetry_server/`) — Async Python WebSocket bridge organised into subpackages:
   - `telemetry_server.py` — `TelemetryServer` composition root + `main()` entry point
   - `alerts/` — `AeroAlertProcessor`, `TyreAlertProcessor`, `PuAlertProcessor` (threshold evaluation and alert log accumulation), plus shared constants (`alert_constants.py`) and helpers (`alert_utils.py`)
   - `dispatch/` — `BaseAgentDispatcher` (debounced batch queue/flush), specialist dispatchers (`DamageDispatcher`, `TyresDispatcher`, `PuDispatcher`), `RaceEngineerDispatcher` (routes follow-ups back to specialists), and `AgentDispatchManager` (facade for all four)
   - `server/` — `MessageBuilder` (assembles JSON), `WebSocketServer` (client tracking + broadcast + driver radio), `TelemetryInput` (UDP listener + `.f1bin` replay)
   - `agents/` — Neuro SAN agent wrappers (`DamageAgent`, `TyresAgent`, `PowerUnitAgent`, `RaceEngineerAgent`)
   - `telemetry_state_adapter.py` — translates decoded packet state into flat camelCase dicts for WebSocket JSON

3. **Race Engineer Hub** (`race_engineer_hub/`) — Vite + React 18 + TypeScript + Tailwind + shadcn/ui dashboard. Each hook (`src/hooks/`) opens its own WebSocket connection to the telemetry server and accumulates state.

### Data flow

```
F1 game → UDP:20777 → TelemetryInput → parse packets → AlertProcessors → generate alerts
                                      → AgentDispatchManager → specialist agents (async)
                                      → WebSocketServer → broadcast JSON over WS:8765
                                      ↓
                         race_engineer_hub (React) ← WS hooks
                                      ↓
                         Driver Radio input → WS → RaceEngineerDispatcher → race engineer agent
```

### Agent hierarchy

- **Race Engineer Agent** — coordinator that reads specialist reports, filters "Copy" acknowledgments, routes follow-ups to specialists, and communicates to the driver
- **Damage Agent** — analyzes aero/brake alerts (wing damage, DRS faults, brake temps)
- **Tyres Agent** — analyzes tyre alerts (surface temp, wear, damage, blistering)
- **Power Unit Agent** — analyzes PU alerts (engine temp, fuel, ERS, gearbox)

Each specialist agent (`telemetry_server/agents/*_agent.py`) uses `AgentSessionFactory` + `StreamingInputProcessor` from neuro-san. Alerts are batched via `BaseAgentDispatcher` with a debounce timer (1-2s) before dispatch. Responses are forwarded to the race engineer agent.

### Telemetry parsing

`common.f1_decoder.PacketDecoder` decodes all 16 F1 25 UDP packet types into nested Python dicts (keyed by `m_packetId`). `TelemetryStateAdapter` (`telemetry_server/telemetry_state_adapter.py`) translates the decoded state into the flat camelCase dicts consumed by the WebSocket JSON messages and alert system. Packet ID 6 (Car Telemetry) is the trigger packet — when received, the server builds and broadcasts the full JSON message. Live capture and replay use `.f1bin` binary format via `common.f1_capture`.

### Frontend patterns

- WebSocket hooks auto-reconnect every 2s on close. Each hook deduplicates responses via `useRef` tracking the last value.
- Combined alert panels (`TyreAlertPanel`, `PuAlertPanel`, `AeroAlertPanel`) merge alert items and engineer responses chronologically using a merge-sort by timestamp.
- Session reset is detected when `sessionTime` drops below the previous value, clearing all accumulated alerts and agent responses.
- Panels are expandable via double-click on the header (fixed overlay pattern).
- Path alias: `@/*` → `./src/*`.

## Code style

- Clean Code Standards: follow Robert C. Martin’s (Uncle Bob) *Clean Code* and *The Clean Coder* recommendations
- Keep things simple, to the point, readable, maintainable and individually testable.
- Line length: 119 characters, both for .py and .md files.

### Python

- Use Python 3.12+ syntax.
- Use object oriented programming: use classes, one class per file and the file should have the same name as the class.
- Use type hints on all parameters and return values, and annotate variable assignments when the type
  isn't obvious from the right-hand side. Use `mypy` for type checking after modifications.
- Imports: ES-style single-line imports, sorted by isort (`force-single-line = true`).
- Use `snake_case` for functions, methods, variables, parameters and attributes, `PascalCase` for classes, and
  `UPPER_CASE` for constants. Comment the reason if an external API forces `camelCase`.
- Linting: ruff (format + isort + pycodestyle + pyflakes) then pylint. Config in `pyproject.toml`.
- Everything lives in a class. No standalone helpers, including in tests. `main()` is a static method, and no
  nested `def`s without a comment stating why. Data-only classes carry no policy methods. One class per file,
  named after it.
- Use `async_invoke` in a `CodedTool`, since `invoke()` blocks the event loop, and wrap blocking I/O in
  `asyncio.to_thread()`.
- Dictionary access uses `.get()`, never `dict[key]`.
- Catch specific exceptions that can be handled at that level; never a generalized `Exception`.
- Never fail silently. Report a missing or unreadable file, malformed input or an unknown choice with the full
  exception, and log enough to act on.
- Prefer logging over `print`, with lazy `%` formatting (`logger.info("Loaded %s", name)`) rather than f-strings.
  Keep messages easy to interpret.
- Use accessors, not internals. Do not read another class's attributes and do not `isinstance` against a concrete
  class; check the interface, or add an interface method that answers the question.
- Comment the non-obvious: which `_method`s are overrides, threading and lifecycle behavior, design decisions, and
  a breadcrumb to related code or documentation. Order lifecycle methods logically, `start()` before `stop()`.
- Docstrings required on classes and functions/methods.
- Use long-form flags (`--force`, not `-f`)
- Cover new behavior with a test: a unit test for a coded tool, an integration fixture for a network.

### Javascript

- TypeScript strict mode. ESLint configured in `race_engineer_hub/eslint.config.js`.
- Ensure all component props are properly typed with interfaces. Run tsc --noEmit after changes.

### Neuro SAN

- HOCON agent configs include a `metadata` section with `description`, `tags`, and `sample_queries`.

## Environment variables

- `OPENAI_API_KEY` — required for LLM calls
- `AGENT_MANIFEST_FILE` — defaults to `registries/manifest.hocon`
