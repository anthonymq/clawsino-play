---
name: clawsino-play
description: Play and operate the Clawsino casino webapp (dice + slots) via its HTTP API or UI. Use when the user asks to place bets/spins, check balance/leaderboard, verify outcomes (provably fair fields), or automate Clawsino gameplay/testing on clawsino.anma-services.com.
---

# Clawsino Play

Use this skill to **play** (or smoke-test) Clawsino without a SPA.

## Quick rules of the game (current)

### Dice
- Endpoint: `POST /v1/dice/bet` (auth required)
- Inputs: `amount`, `mode` (`under|over`), `threshold`, optional `clientSeed`, optional `edgeBps`
- Output includes: `outcome.roll`, `outcome.win`, `outcome.payout`, `balance`

### Slots
- Endpoint: `POST /v1/slots/spin` (auth required)
- 3×3 window with 3 paylines: **top / middle / bottom**
- Line wins:
  - No line win if the line contains a **scatter**
  - Win if **3-of-a-kind** with wild substitution
  - Win if **2-of-a-kind on reels 1+2** (wild can substitute)
- Scatter pays are independent and only start at **3+ scatters** in the 3×3 grid

## How to authenticate

Clawsino uses `Authorization: Bearer <sessionToken>`.

### Option A (manual): session token from /login
Log in on `/login` (browser stores it in localStorage as `clawsino.sessionToken`).

### Option B (recommended): device code (bot onboarding)
Use the device flow so the bot can get its own session token without copy/pasting long secrets:

1) Bot calls `device-start` to get a short `userCode` (like `ABCD-EFGH`) + `deviceCode`.
2) Human (already logged in on Clawsino) opens `/device`, enters the `userCode`, and chooses a handle (prefilled, editable).
3) Bot polls until it receives a `sessionToken`.


## Recommended workflow

1) Confirm base URL (default): `https://clawsino.anma-services.com`
2) Confirm you have a valid bearer token
3) Call `/v1/me` to get `handle`, `balance`, `slotsFreeSpins`
4) Place a bet/spin
5) Re-check `/v1/me` and optionally `/v1/leaderboard`

## Use the bundled CLI (preferred)

Run the script:
- `python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "…" me`
- `python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "…" leaderboard --limit 10`
- `python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "…" dice --amount 100 --mode under --threshold 49.5`
- `python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "…" slots --amount 100`
- Device onboarding:
  - `python3 scripts/clawsino.py device-start --client-name openclaw --handle openclaw-bot`
  - (human approves at https://clawsino.anma-services.com/device)
  - `python3 scripts/clawsino.py device-poll --device-code "…"`

## Interpreting outcomes

- Dice win: `outcome.win == true`
- Slots win:
  - `outcome.lineWins` lists each line win with `line`, `symbols`, `multiplier`, `payout`
  - `outcome.scatterCount` triggers bonus when >= 3

## Notes

- Keep the session token private.
- If a call returns `401 invalid session`, refresh the token by re-logging in on `/login`.
