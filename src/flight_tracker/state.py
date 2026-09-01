"""Persisted state + alert-decision logic.

We remember, per passenger count, the best effective cost we've ever alerted
on. That lets the tracker fire an alert only when something *newsworthy*
happens instead of every run:

* first run ever (optional), or
* a new best that improves on the last alerted best by >= ``min_improvement``, or
* the airfare drops at/under the user's ``target_price`` for the first time.

The state file is small JSON and is committed back by the scheduled job so the
memory survives across runs.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .config import AlertConfig
from .models import ScoredOption

STATE_VERSION = 1


@dataclass
class AlertDecision:
    should_alert: bool
    reasons: dict[int, str]  # pax -> human-readable reason


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"version": STATE_VERSION, "by_pax": {}}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("by_pax", {})
        return data
    except Exception:
        return {"version": STATE_VERSION, "by_pax": {}}


def save_state(path: str, state: dict) -> None:
    state["version"] = STATE_VERSION
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def evaluate_alerts(
    best_by_pax: dict[int, ScoredOption],
    state: dict,
    alerts: AlertConfig,
) -> AlertDecision:
    """Decide whether the current bests warrant an alert, and update `state`
    in place with the new bests/alert markers."""

    reasons: dict[int, str] = {}
    by_pax = state.setdefault("by_pax", {})
    is_first_run = not by_pax

    for pax, best in best_by_pax.items():
        key = str(pax)
        prev = by_pax.get(key, {})
        prev_alert = prev.get("last_alert_effective_brl")
        prev_under_target = prev.get("under_target_alerted", False)

        eff = best.effective_cost_brl
        airfare = best.airfare_brl
        trigger: Optional[str] = None

        under_target = (
            alerts.target_price_brl is not None
            and airfare <= alerts.target_price_brl
        )

        if is_first_run and alerts.alert_on_first_run:
            trigger = f"primeira leitura — melhor opção para {pax} pax"
        elif under_target and not prev_under_target:
            trigger = (
                f"passagem para {pax} pax atingiu a meta "
                f"(R$ {airfare:,.0f} ≤ R$ {alerts.target_price_brl:,.0f})"
            )
        elif prev_alert is not None and eff <= prev_alert - alerts.min_improvement_brl:
            drop = prev_alert - eff
            trigger = (
                f"novo melhor para {pax} pax: custo efetivo caiu R$ {drop:,.0f} "
                f"(para R$ {eff:,.0f})"
            )
        elif prev_alert is None:
            # We have prior state but never alerted this pax count yet.
            trigger = f"primeira oferta rastreada para {pax} pax"

        # Always keep the running best; only bump the *alert* marker on trigger.
        new_entry = {
            "best_effective_brl": min(eff, prev.get("best_effective_brl", eff)),
            "best_offer_key": best.offer_key,
            "last_alert_effective_brl": (
                eff if trigger else prev_alert
            ),
            "under_target_alerted": prev_under_target or under_target,
        }
        by_pax[key] = new_entry

        if trigger:
            reasons[pax] = trigger

    return AlertDecision(should_alert=bool(reasons), reasons=reasons)
