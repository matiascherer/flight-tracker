"""Tiny currency helper.

Some providers return prices in USD/EUR. We convert to BRL using a configurable
rate (defaults come from env vars so they can be refreshed without code
changes). This is intentionally simple — for a personal deal tracker an
approximate rate is fine, and the rate only affects cross-currency comparison.
"""

from __future__ import annotations

import os

# Rough fallbacks; override with env FX_USD_BRL / FX_EUR_BRL for accuracy.
_DEFAULTS = {
    "BRL": 1.0,
    "USD": float(os.environ.get("FX_USD_BRL", "5.40") or 5.40),
    "EUR": float(os.environ.get("FX_EUR_BRL", "5.90") or 5.90),
}


def to_brl(amount: float, currency: str) -> float:
    rate = _DEFAULTS.get((currency or "BRL").upper())
    if rate is None:
        # Unknown currency: assume it's already ~BRL rather than inventing a rate.
        return amount
    return amount * rate
