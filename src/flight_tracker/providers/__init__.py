"""Provider registry and aggregation.

Maps provider names (as used in config) to classes, builds the ones that are
enabled, and exposes :func:`build_providers`. The aggregator that actually fans
a query out across providers lives in ``tracker.py``.
"""

from __future__ import annotations

import logging

from ..config import ProviderConfig
from .amadeus import AmadeusProvider
from .base import FlightProvider
from .kiwi_tequila import KiwiTequilaProvider
from .sample import SampleProvider
from .serpapi_flights import SerpApiFlightsProvider
from .travelpayouts import TravelpayoutsProvider

log = logging.getLogger("flight_tracker.providers")

_REGISTRY: dict[str, type[FlightProvider]] = {
    "sample": SampleProvider,
    "amadeus": AmadeusProvider,
    "kiwi_tequila": KiwiTequilaProvider,
    "serpapi_google_flights": SerpApiFlightsProvider,
    "travelpayouts": TravelpayoutsProvider,
}


def build_providers(configs: list[ProviderConfig]) -> list[FlightProvider]:
    """Instantiate every enabled, *ready* provider. Enabled-but-not-ready
    providers (missing credentials) are logged and skipped so the run proceeds
    with whatever is available."""

    providers: list[FlightProvider] = []
    for cfg in configs:
        if not cfg.enabled:
            continue
        cls = _REGISTRY.get(cfg.name)
        if cls is None:
            log.warning("unknown provider '%s' in config; skipping", cfg.name)
            continue
        provider = cls(cfg.options)
        if not provider.ready():
            continue
        providers.append(provider)
    return providers


__all__ = ["build_providers", "FlightProvider"]
