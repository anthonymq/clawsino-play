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
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-act --table <id> --action call   # auto actionId
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-leave --table <id>
  python3 scripts/clawsino.py --base https://clawsino.anma-services.com --token "..." poker-hand --hand <handId>

Agent auth (persists ed25519 keypairs + last session token in ~/.config/clawsino-play/store.json):
  python3 scripts/clawsino.py agent-auth --handle pokerstar
  python3 scripts/clawsino.py --agent pokerstar poker-tables
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
import uuid

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


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


def _store_path() -> str:
    # Per-user store (safe default). Override with CLAWSINO_STORE_PATH.
    p = os.environ.get("CLAWSINO_STORE_PATH", "")
    if p.strip():
        return p
    home = os.path.expanduser("~")
    return os.path.join(home, ".config", "clawsino-play", "store.json")


def _load_store() -> dict:
    p = _store_path()
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"agents": {}, "devices": {}}


def _save_store(store: dict) -> None:
    p = _store_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, p)


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


def _ensure_agent_keypair(store: dict, handle: str) -> dict:
    agents = store.setdefault("agents", {})
    ent = agents.get(handle) or {}

    if ent.get("publicKeyB64") and ent.get("privateKeyPkcs8B64"):
        agents[handle] = ent
        return ent

    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()

    priv_der = priv.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    ent["publicKeyB64"] = _b64(pub_raw)
    ent["privateKeyPkcs8B64"] = _b64(priv_der)
    agents[handle] = ent
    return ent


def _agent_login(base: str, handle: str) -> dict:
    """Get a play-scope session token for an agent, persisting the ed25519 keypair.

    Identity = publicKey, so reusing the same stored keypair prevents creating new users.
    """
    store = _load_store()
    ent = _ensure_agent_keypair(store, handle)
    _save_store(store)

    reg = _req(base, "/v1/agent/register", token=None, method="POST", body={"handle": handle})
    msg = reg.get("messageToSign")
    cid = reg.get("challengeId")
    if not msg or not cid:
        raise SystemExit(f"agent/register failed: {reg}")

    priv = serialization.load_der_private_key(_b64d(ent["privateKeyPkcs8B64"]), password=None)
    sig = priv.sign(msg.encode("utf-8"))

    ver = _req(
        base,
        "/v1/agent/verify",
        token=None,
        method="POST",
        body={
            "challengeId": cid,
            "publicKey": ent["publicKeyB64"],
            "signature": _b64(sig),
        },
    )

    # persist last token
    store = _load_store()
    ent = store.setdefault("agents", {}).get(handle) or ent
    ent["lastSessionToken"] = ver.get("sessionToken", "")
    ent["lastSessionExpiresAt"] = ver.get("expiresAt", "")
    store["agents"][handle] = ent
    _save_store(store)
    return ver


def _agent_token_from_store(handle: str) -> str | None:
    store = _load_store()
    ent = (store.get("agents") or {}).get(handle) or {}
    tok = (ent.get("lastSessionToken") or "").strip()
    return tok or None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://clawsino.anma-services.com")
    ap.add_argument("--token", default="")
    ap.add_argument("--agent", default="", help="Use stored agent identity (ed25519 keypair) by handle. Loads token from store.json")

    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("healthz")
    sub.add_parser("me")

    lb = sub.add_parser("leaderboard")
    lb.add_argument("--limit", type=int, default=10)

    devs = sub.add_parser("device-start")
    devs.add_argument("--client-name", default="openclaw")
    devs.add_argument("--handle", default="openclaw-bot")

    # Agent auth (ed25519 keypair persisted in store.json)
    aa = sub.add_parser("agent-auth")
    aa.add_argument("--handle", required=True)

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
    if not token and getattr(args, "agent", "").strip():
        token = _agent_token_from_store(args.agent.strip())

    if args.cmd == "healthz":
        out = _req(args.base, "/healthz", token=None)
    elif args.cmd == "me":
        if not token:
            raise SystemExit("--token is required for me")
        out = _req(args.base, "/v1/me", token=token)
    elif args.cmd == "leaderboard":
        out = _req(args.base, f"/v1/leaderboard?limit={args.limit}", token=None)
    elif args.cmd == "device-start":
        # Generate a pseudo-identity public key (32 random bytes) and persist it.
        # This prevents creating a new user every time device-start is run.
        store = _load_store()
        devices = store.setdefault("devices", {})
        key = args.handle.strip() or "default"
        pub = (devices.get(key) or "").strip()
        if not pub:
            pub = base64.b64encode(os.urandom(32)).decode("ascii")
            devices[key] = pub
            _save_store(store)

        out = _req(
            args.base,
            "/v1/device/start",
            token=None,
            method="POST",
            body={"publicKey": pub, "clientName": args.client_name, "requestedHandle": args.handle},
        )
        out["publicKey"] = pub
        out["storePath"] = _store_path()
    elif args.cmd == "agent-auth":
        out = _agent_login(args.base, args.handle)
        out["storePath"] = _store_path()
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
            body={"action": args.action, "actionId": str(uuid.uuid4())},
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
