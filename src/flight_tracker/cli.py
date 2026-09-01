"""Command-line entry point.

Usage:
    python -m flight_tracker run           # search, alert if newsworthy, save state
    python -m flight_tracker run --dry-run # search + print, never alert/save
    python -m flight_tracker dates         # print the valid date pairs
    python -m flight_tracker test-notify   # send a test alert through all channels

Config path defaults to ./config.yaml (override with --config or env
FLIGHT_TRACKER_CONFIG). A .env file in the working dir is auto-loaded if present.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from .config import load_config
from .dates import generate_date_pairs
from .notifiers import build_notifiers
from .tracker import render_summary, run


def _load_dotenv() -> None:
    """Minimal .env loader (avoids a hard dependency on python-dotenv)."""
    path = os.environ.get("DOTENV_PATH", ".env")
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def _config_path(args) -> str:
    return (
        args.config
        or os.environ.get("FLIGHT_TRACKER_CONFIG")
        or "config.yaml"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="flight_tracker")
    parser.add_argument("command", choices=["run", "dates", "test-notify"])
    parser.add_argument("--config", help="path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="don't alert or save state")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _load_dotenv()
    config = load_config(_config_path(args))

    if args.command == "dates":
        pairs = generate_date_pairs(config.window)
        print(f"{len(pairs)} combinações de datas válidas:\n")
        for depart, ret in pairs:
            nights = (ret - depart).days
            print(f"  {depart.isoformat()} -> {ret.isoformat()}  ({nights} noites)")
        return 0

    if args.command == "test-notify":
        notifiers = build_notifiers(config.notifiers)
        if not notifiers:
            print("Nenhum notificador pronto (verifique credenciais).")
            return 1
        subject = "✈️ Teste — rastreador Itacaré"
        body = "Se você recebeu isto, o canal de alertas está funcionando. ✅"
        ok = []
        for n in notifiers:
            if n.send(subject, body, f"<p>{body}</p>"):
                ok.append(n.name)
        print(f"Enviado por: {', '.join(ok) or '(nenhum)'}")
        return 0 if ok else 1

    # run
    result = run(config, dry_run=args.dry_run)
    print(render_summary(result, config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
