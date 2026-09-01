"""Sample (offline) provider.

Generates realistic, *deterministic* synthetic offers so the whole pipeline —
search, scoring, ranking, alerting, reporting — runs end-to-end before any real
API credentials exist. Prices are seeded from the route/date so they're stable
across runs (which lets state/alerting logic be tested) but vary plausibly:
peak New-Year dates cost more, Congonhas/Ilhéus cost a bit more than the
alternatives, LATAM is priced at a small premium, etc.

This provider is always "ready" and should be kept enabled as a fallback, but
in real monitoring its offers are clearly marked ``provider="sample"`` so you
can tell demo data from live data.
"""

from __future__ import annotations

import hashlib

from ..models import FlightOffer, SearchQuery
from .base import FlightProvider

# Base one-way fare per person, by route leg, in BRL. Deliberately rough.
_BASE_FARE = {
    ("CGH", "IOS"): 720,
    ("GRU", "IOS"): 690,
    ("VCP", "IOS"): 640,
    ("CGH", "SSA"): 560,
    ("GRU", "SSA"): 520,
    ("VCP", "SSA"): 490,
}

# Carriers plausibly flying each SP<->BA pair.
_CARRIERS = {
    "IOS": ["LA", "AD"],          # Ilhéus: LATAM, Azul
    "SSA": ["LA", "G3", "AD"],    # Salvador: LATAM, GOL, Azul
}


def _seed(*parts: str) -> int:
    h = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return int(h[:8], 16)


class SampleProvider(FlightProvider):
    name = "sample"

    def ready(self) -> bool:
        return True

    def search(self, query: SearchQuery) -> list[FlightOffer]:
        base = _BASE_FARE.get((query.origin, query.destination))
        if base is None:
            return []

        offers: list[FlightOffer] = []
        carriers = _CARRIERS.get(query.destination, ["LA"])

        for carrier in carriers:
            seed = _seed(query.key(), carrier)
            # Deterministic pseudo-variation in the +/- 18% range.
            variation = ((seed % 37) - 18) / 100.0
            # New-Year peak surcharge: depart 29-31 Dec / return 1-3 Jan.
            peak = 0.0
            if query.depart_date.month == 12 and query.depart_date.day >= 29:
                peak += 0.15
            if query.return_date.month == 1 and query.return_date.day <= 3:
                peak += 0.10
            # LATAM small premium; low-cost carriers slightly cheaper.
            carrier_adj = 0.06 if carrier == "LA" else -0.04

            one_way = base * (1 + variation + peak + carrier_adj)
            round_trip_pp = one_way * 2
            total = round(round_trip_pp * query.passengers, 2)

            stops = 0 if (seed % 3) else 1  # ~1 in 3 has a connection
            offers.append(
                FlightOffer(
                    origin=query.origin,
                    destination=query.destination,
                    depart_date=query.depart_date,
                    return_date=query.return_date,
                    passengers=query.passengers,
                    price_total_brl=total,
                    airlines=(carrier,),
                    provider=self.name,
                    outbound_stops=stops,
                    return_stops=stops,
                    outbound_duration_min=110 + stops * 90,
                    return_duration_min=110 + stops * 90,
                    deep_link=None,
                    raw_currency="BRL",
                    raw_price=total,
                )
            )
        return offers
