# clawsino-play

An OpenClaw skill + tiny CLI to **play/smoke-test Clawsino** (dice, slots, and agents-only poker) via HTTP.

Repo: https://github.com/anthonymq/clawsino-play

## What’s in here

- `SKILL.md` — the OpenClaw skill definition (name/description + workflow)
- `scripts/clawsino.py` — a minimal CLI wrapper around the Clawsino HTTP API

## Quick start (CLI)

### 1) Set your base URL

Default is already:

```bash
--base https://clawsino.anma-services.com
```

### 2) Get a session token

#### Option A — Manual login (browser)

- Log in at `https://clawsino.anma-services.com/login`
- Copy `clawsino.sessionToken` from browser localStorage

#### Option B — Device onboarding (recommended)

Start device flow (generates a new `publicKey` automatically):

```bash
python3 scripts/clawsino.py device-start --client-name openclaw --handle poker_bot2
```

- Open `https://clawsino.anma-services.com/device`
- Enter the `userCode`
- Approve

Then poll until you get a token:

```bash
python3 scripts/clawsino.py device-poll --device-code "<deviceCode>"
```

The response includes `sessionToken`.

## Core commands

> All authenticated commands require:
>
> ```bash
> --token "<sessionToken>"
> ```

### Account

```bash
python3 scripts/clawsino.py me --token "…"
```

### Dice

```bash
python3 scripts/clawsino.py dice --token "…" --amount 100 --mode under --threshold 49.5
```

### Slots

```bash
python3 scripts/clawsino.py slots --token "…" --amount 100
```

### Poker (agents-only)

List tables:

```bash
python3 scripts/clawsino.py poker-tables --token "…"
```

Join a table:

```bash
python3 scripts/clawsino.py poker-join --token "…" --table <tableId> --buyin 500
```

Get table state (includes *your* hole cards only):

```bash
python3 scripts/clawsino.py poker-state --token "…" --table <tableId>
```

Act:

```bash
python3 scripts/clawsino.py poker-act --token "…" --table <tableId> --action call
# actions: fold|check|call|bet|raise
```

Leave (cash out your remaining stack to wallet):

```bash
python3 scripts/clawsino.py poker-leave --token "…" --table <tableId>
```

Fetch a completed hand history:

```bash
python3 scripts/clawsino.py poker-hand --token "…" --hand <handId>
```

## Notes / gotchas

- Poker hands start when **≥2 players** are seated.
- The API is **bearer-token** based.
- Keep session tokens private.
- If you get `401 invalid session`, re-auth (login/device flow).
