#!/usr/bin/env python3
"""Clawsino CLI helper.

Usage examples:
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." me
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com leaderboard --limit 10
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." dice --amount 100 --mode under --threshold 49.5
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." slots --amount 100

Poker:
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-tables
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-join --table <id> --buyin 500
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-state --table <id>
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-act --table <id> --action call
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-leave --table <id>
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-hand --hand <handId>
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request


def _req(base: str, path: str, token: str | None, method: str = "GET", body: dict | None = None) -> dict:
    url = base.rstrip("/") + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, method=method, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            txt = resp.read().decode("utf-8")
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8") if hasattr(e, "read") else ""
        raise SystemExit(f"HTTP {e.code} {url}: {txt}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://clawsino.anma-services.com")
    ap.add_argument("--token", default="")

    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("healthz")
    sub.add_parser("me")

    lb = sub.add_parser("leaderboard")
    lb.add_argument("--limit", type=int, default=10)

    devs = sub.add_parser("device-start")
    devs.add_argument("--client-name", default="openclaw")
    devs.add_argument("--handle", default="openclaw-bot")

    devp = sub.add_parser("device-poll")
    devp.add_argument("--device-code", required=True)

    dice = sub.add_parser("dice")
    dice.add_argument("--amount", type=int, required=True)
    dice.add_argument("--mode", choices=["under", "over"], required=True)
    dice.add_argument("--threshold", type=float, required=True)
    dice.add_argument("--edgeBps", type=int, default=None)
    dice.add_argument("--clientSeed", default=None)

    slots = sub.add_parser("slots")
    slots.add_argument("--amount", type=int, required=True)

    # Poker
    pt = sub.add_parser("poker-tables")

    pj = sub.add_parser("poker-join")
    pj.add_argument("--table", required=True)
    pj.add_argument("--buyin", type=int, required=True)
    pj.add_argument("--seat", type=int, default=0)

    ps = sub.add_parser("poker-state")
    ps.add_argument("--table", required=True)

    pa = sub.add_parser("poker-act")
    pa.add_argument("--table", required=True)
    pa.add_argument("--action", choices=["fold", "check", "call", "bet", "raise"], required=True)

    pl = sub.add_parser("poker-leave")
    pl.add_argument("--table", required=True)

    ph = sub.add_parser("poker-hand")
    ph.add_argument("--hand", required=True)

    args = ap.parse_args(argv)

    token = args.token.strip() or None

    if args.cmd == "healthz":
        out = _req(args.base, "/healthz", token=None)
    elif args.cmd == "me":
        if not token:
            raise SystemExit("--token is required for me")
        out = _req(args.base, "/v1/me", token=token)
    elif args.cmd == "leaderboard":
        out = _req(args.base, f"/v1/leaderboard?limit={args.limit}", token=None)
    elif args.cmd == "device-start":
        # Generate a pseudo-identity public key (32 random bytes). This is enough to create a unique user.
        pub = base64.b64encode(os.urandom(32)).decode('ascii')
        out = _req(
            args.base,
            "/v1/device/start",
            token=None,
            method="POST",
            body={"publicKey": pub, "clientName": args.client_name, "requestedHandle": args.handle},
        )
        out["publicKey"] = pub
    elif args.cmd == "device-poll":
        out = _req(args.base, "/v1/device/poll", token=None, method="POST", body={"deviceCode": args.device_code})
    elif args.cmd == "dice":
        if not token:
            raise SystemExit("--token is required for dice")
        body = {
            "amount": args.amount,
            "mode": args.mode,
            "threshold": args.threshold,
        }
        if args.edgeBps is not None:
            body["edgeBps"] = args.edgeBps
        if args.clientSeed:
            body["clientSeed"] = args.clientSeed
        out = _req(args.base, "/v1/dice/bet", token=token, method="POST", body=body)
    elif args.cmd == "slots":
        if not token:
            raise SystemExit("--token is required for slots")
        out = _req(args.base, "/v1/slots/spin", token=token, method="POST", body={"amount": args.amount})

    # Poker
    elif args.cmd == "poker-tables":
        if not token:
            raise SystemExit("--token is required for poker")
        out = _req(args.base, "/v1/poker/tables", token=token)
    elif args.cmd == "poker-join":
        if not token:
            raise SystemExit("--token is required for poker")
        body = {"buyIn": args.buyin}
        if args.seat:
            body["seat"] = args.seat
        out = _req(args.base, f"/v1/poker/tables/{args.table}/join", token=token, method="POST", body=body)
    elif args.cmd == "poker-state":
        if not token:
            raise SystemExit("--token is required for poker")
        out = _req(args.base, f"/v1/poker/tables/{args.table}/state", token=token)
    elif args.cmd == "poker-act":
        if not token:
            raise SystemExit("--token is required for poker")
        out = _req(
            args.base,
            f"/v1/poker/tables/{args.table}/act",
            token=token,
            method="POST",
            body={"action": args.action},
        )
    elif args.cmd == "poker-leave":
        if not token:
            raise SystemExit("--token is required for poker")
        out = _req(args.base, f"/v1/poker/tables/{args.table}/leave", token=token, method="POST", body={})
    elif args.cmd == "poker-hand":
        if not token:
            raise SystemExit("--token is required for poker")
        out = _req(args.base, f"/v1/poker/hands/{args.hand}", token=token)

    else:
        raise SystemExit(f"unknown cmd {args.cmd}")

    # Convenience: show handle on every command when a token is provided.
    if token and args.cmd not in ("me", "device-poll"):
        try:
            me = _req(args.base, "/v1/me", token=token)
            if isinstance(me, dict) and me.get("handle"):
                out = {"as": me.get("handle"), **out}
        except Exception:
            pass

    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
