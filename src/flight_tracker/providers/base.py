"""Provider interface.

A provider knows how to turn a :class:`SearchQuery` (one route, one date pair,
one party size) into zero or more :class:`FlightOffer` objects. Each provider is
self-contained and independently enable-able; the aggregator queries every
configured+ready provider and merges the results.

Design rules for a provider:

* ``ready()`` returns False when required credentials are missing — the
  aggregator then skips it silently instead of crashing. This is what lets the
  whole app run today with only the sample provider active.
* ``search()`` must never raise for an ordinary "no results / network hiccup"
  situation; it should log and return ``[]``. The aggregator isolates provider
  failures so one bad API key can't take the run down.
* Prices are normalised to BRL total for the whole party before returning.
"""

from __future__ import annotations

import logging
from typing import Optional

from ..models import FlightOffer, SearchQuery

log = logging.getLogger("flight_tracker.provider")


class FlightProvider:
    name: str = "base"

    def __init__(self, options: Optional[dict] = None):
        self.options = options or {}

    def ready(self) -> bool:
        """Return True when this provider has everything it needs to run."""
        return True

    def search(self, query: SearchQuery) -> list[FlightOffer]:
        raise NotImplementedError

    # --- helpers shared by concrete providers -------------------------------

    def _log_skip(self, reason: str) -> None:
        log.info("provider %s not ready: %s", self.name, reason)
