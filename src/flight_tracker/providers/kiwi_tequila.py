"""Kiwi.com Tequila provider.

Free API key: request one at https://tequila.kiwi.com/portal/login (Tequila by
Kiwi.com, "Solutions" / partner program). Set:

    TEQUILA_API_KEY

Tequila indexes a very wide set of carriers and OTAs (including low-cost and
mixed-airline itineraries the GDS-based providers miss), and returns a
``deep_link`` you can book through. Prices are the total for the whole party.

Docs: https://tequila.kiwi.com/portal/docs/tequila_api/search_api
"""

from __future__ import annotations

import logging
from typing import Optional

import requests

from ..config import env
from ..models import FlightOffer, SearchQuery
from .base import FlightProvider
from .fx import to_brl

log = logging.getLogger("flight_tracker.provider.kiwi")

_ENDPOINT = "https://api.tequila.kiwi.com/v2/search"


class KiwiTequilaProvider(FlightProvider):
    name = "kiwi_tequila"

    def __init__(self, options: Optional[dict] = None):
        super().__init__(options)
        self.api_key = env(self.options.get("api_key_env", "TEQUILA_API_KEY"))
        self.limit = int(self.options.get("limit", 8))
        self.max_stopovers = int(self.options.get("max_stopovers", 2))

    def ready(self) -> bool:
        if not self.api_key:
            self._log_skip("TEQUILA_API_KEY not set")
            return False
        return True

    def search(self, query: SearchQuery) -> list[FlightOffer]:
        d_out = query.depart_date.strftime("%d/%m/%Y")
        d_ret = query.return_date.strftime("%d/%m/%Y")
        params = {
            "fly_from": query.origin,
            "fly_to": query.destination,
            "date_from": d_out,
            "date_to": d_out,
            "return_from": d_ret,
            "return_to": d_ret,
            "flight_type": "round",
            "adults": query.passengers,
            "curr": "BRL",
            "max_stopovers": self.max_stopovers,
            "limit": self.limit,
            "sort": "price",
            "vehicle_type": "aircraft",
        }
        try:
            resp = requests.get(
                _ENDPOINT,
                headers={"apikey": self.api_key},
                params=params,
                timeout=30,
            )
            if resp.status_code != 200:
                log.warning("kiwi search HTTP %s: %s", resp.status_code, resp.text[:200])
                return []
            data = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            log.warning("kiwi search error: %s", exc)
            return []

        offers: list[FlightOffer] = []
        for item in data:
            try:
                offers.append(self._parse(item, query))
            except Exception as exc:  # noqa: BLE001
                log.debug("kiwi parse skip: %s", exc)
        return offers

    def _parse(self, item: dict, query: SearchQuery) -> FlightOffer:
        # Kiwi "price" is total for the whole party in the requested currency.
        total = float(item["price"])
        total_brl = to_brl(total, "BRL")
        airlines = tuple(dict.fromkeys(item.get("airlines", [])))

        # Count stops per direction from the route legs (return==0/1 flag).
        out_stops = -1
        ret_stops = -1
        for leg in item.get("route", []):
            if leg.get("return", 0) == 0:
                out_stops += 1
            else:
                ret_stops += 1
        return FlightOffer(
            origin=query.origin,
            destination=query.destination,
            depart_date=query.depart_date,
            return_date=query.return_date,
            passengers=query.passengers,
            price_total_brl=round(total_brl, 2),
            airlines=airlines,
            provider=self.name,
            outbound_stops=max(out_stops, 0),
            return_stops=max(ret_stops, 0),
            deep_link=item.get("deep_link"),
            raw_currency="BRL",
            raw_price=total,
        )
