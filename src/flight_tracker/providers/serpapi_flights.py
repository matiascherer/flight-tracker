"""Google Flights via SerpApi.

SerpApi exposes Google Flights results (arguably the broadest single view of
airfare) through a clean JSON API. Free tier: 100 searches/month at
https://serpapi.com. Set:

    SERPAPI_API_KEY

Google Flights returns airline *names*, not IATA codes, so we normalise the
common Brazilian carriers (LATAM->LA, GOL->G3, Azul->AD) for the preference
logic; unknown names fall back to a best-effort short code.

Docs: https://serpapi.com/google-flights-api
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from ..config import env
from ..models import FlightOffer, SearchQuery
from .base import FlightProvider
from .fx import to_brl

log = logging.getLogger("flight_tracker.provider.serpapi")

_ENDPOINT = "https://serpapi.com/search.json"

_NAME_TO_IATA = {
    "LATAM": "LA",
    "GOL": "G3",
    "AZUL": "AD",
    "AVIANCA": "AV",
    "COPA": "CM",
    "TAP": "TP",
    "AMERICAN": "AA",
}


def _airline_code(name: str) -> str:
    if not name:
        return "??"
    upper = name.upper()
    for key, code in _NAME_TO_IATA.items():
        if key in upper:
            return code
    return upper[:2]


class SerpApiFlightsProvider(FlightProvider):
    name = "serpapi_google_flights"

    def __init__(self, options: Optional[dict] = None):
        super().__init__(options)
        self.api_key = env(self.options.get("api_key_env", "SERPAPI_API_KEY"))

    def ready(self) -> bool:
        if not self.api_key:
            self._log_skip("SERPAPI_API_KEY not set")
            return False
        return True

    def search(self, query: SearchQuery) -> list[FlightOffer]:
        params = {
            "engine": "google_flights",
            "departure_id": query.origin,
            "arrival_id": query.destination,
            "outbound_date": query.depart_date.isoformat(),
            "return_date": query.return_date.isoformat(),
            "currency": "BRL",
            "adults": query.passengers,
            "type": "1",  # round trip
            "hl": "pt-br",
            "gl": "br",
            "api_key": self.api_key,
        }
        try:
            resp = requests.get(_ENDPOINT, params=params, timeout=40)
            if resp.status_code != 200:
                log.warning("serpapi HTTP %s: %s", resp.status_code, resp.text[:200])
                return []
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("serpapi search error: %s", exc)
            return []

        results = (payload.get("best_flights") or []) + (
            payload.get("other_flights") or []
        )
        offers: list[FlightOffer] = []
        for item in results:
            try:
                offers.append(self._parse(item, query))
            except Exception as exc:  # noqa: BLE001
                log.debug("serpapi parse skip: %s", exc)
        return offers

    def _parse(self, item: dict, query: SearchQuery) -> FlightOffer:
        # SerpApi google_flights "price" is the total round-trip price for the
        # requested number of adults, in the requested currency.
        total = float(item["price"])
        total_brl = to_brl(total, "BRL")

        segments = item.get("flights", [])
        carriers = tuple(
            dict.fromkeys(_airline_code(seg.get("airline", "")) for seg in segments)
        )
        # SerpApi groups the round trip; stops aren't split by direction, so use
        # the reported layovers count as a whole-trip proxy split evenly.
        layovers = len(item.get("layovers", []) or [])
        return FlightOffer(
            origin=query.origin,
            destination=query.destination,
            depart_date=query.depart_date,
            return_date=query.return_date,
            passengers=query.passengers,
            price_total_brl=round(total_brl, 2),
            airlines=carriers,
            provider=self.name,
            outbound_stops=layovers,  # conservative; treated as trip-level hint
            return_stops=0,
            outbound_duration_min=item.get("total_duration"),
            deep_link=item.get("booking_token"),
            raw_currency="BRL",
            raw_price=total,
        )
