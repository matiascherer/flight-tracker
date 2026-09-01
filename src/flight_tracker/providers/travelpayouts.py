"""Travelpayouts / Aviasales cached-price provider.

Free API token: sign up at https://www.travelpayouts.com (Aviasales data API).
Set:

    TRAVELPAYOUTS_TOKEN

This endpoint serves Aviasales' **cached** cheapest prices for a date pair.
It's not live inventory, so treat it as a cheap, fast early-warning signal
(great for spotting when a route's floor drops) rather than a bookable quote.
Prices come back per passenger, so we multiply by the party size.

Docs: https://support.travelpayouts.com/hc/en-us/articles/203956163
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from ..config import env
from ..models import FlightOffer, SearchQuery
from .base import FlightProvider
from .fx import to_brl

log = logging.getLogger("flight_tracker.provider.travelpayouts")

_ENDPOINT = "https://api.travelpayouts.com/aviasales/v3/prices_for_dates"


class TravelpayoutsProvider(FlightProvider):
    name = "travelpayouts"

    def __init__(self, options: Optional[dict] = None):
        super().__init__(options)
        self.token = env(self.options.get("token_env", "TRAVELPAYOUTS_TOKEN"))
        self.limit = int(self.options.get("limit", 10))

    def ready(self) -> bool:
        if not self.token:
            self._log_skip("TRAVELPAYOUTS_TOKEN not set")
            return False
        return True

    def search(self, query: SearchQuery) -> list[FlightOffer]:
        params = {
            "origin": query.origin,
            "destination": query.destination,
            "departure_at": query.depart_date.isoformat(),
            "return_at": query.return_date.isoformat(),
            "currency": "brl",
            "one_way": "false",
            "direct": "false",
            "limit": self.limit,
            "sorting": "price",
            "token": self.token,
        }
        try:
            resp = requests.get(_ENDPOINT, params=params, timeout=30)
            if resp.status_code != 200:
                log.warning(
                    "travelpayouts HTTP %s: %s", resp.status_code, resp.text[:200]
                )
                return []
            payload = resp.json()
        except Exception as exc:  # noqa: BLE001
            log.warning("travelpayouts search error: %s", exc)
            return []

        if not payload.get("success", True):
            log.warning("travelpayouts error: %s", payload.get("error"))
            return []

        offers: list[FlightOffer] = []
        for item in payload.get("data", []):
            try:
                offers.append(self._parse(item, query))
            except Exception as exc:  # noqa: BLE001
                log.debug("travelpayouts parse skip: %s", exc)
        return offers

    def _parse(self, item: dict, query: SearchQuery) -> FlightOffer:
        # Aviasales cached price is per passenger.
        per_person = float(item["price"])
        total = per_person * query.passengers
        total_brl = to_brl(total, "BRL")
        airline = item.get("airline")
        transfers = int(item.get("transfers", 0) or 0)
        return_transfers = int(item.get("return_transfers", 0) or 0)
        return FlightOffer(
            origin=query.origin,
            destination=query.destination,
            depart_date=query.depart_date,
            return_date=query.return_date,
            passengers=query.passengers,
            price_total_brl=round(total_brl, 2),
            airlines=(airline,) if airline else tuple(),
            provider=self.name,
            outbound_stops=transfers,
            return_stops=return_transfers,
            deep_link=(
                f"https://www.aviasales.com{item['link']}"
                if item.get("link")
                else None
            ),
            raw_currency="BRL",
            raw_price=total,
        )
