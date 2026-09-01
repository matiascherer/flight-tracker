"""Amadeus Self-Service provider (Flight Offers Search).

Free tier: create an app at https://developers.amadeus.com, grab the API key +
secret, and set:

    AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET

By default this hits the **test** environment (limited, cached inventory but
free and generous). Set ``environment: production`` in the provider options
(and use production keys) for live inventory once you have quota.

Docs: https://developers.amadeus.com/self-service/category/flights
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from ..config import env
from ..models import FlightOffer, SearchQuery
from .base import FlightProvider
from .fx import to_brl

log = logging.getLogger("flight_tracker.provider.amadeus")

_HOSTS = {
    "test": "https://test.api.amadeus.com",
    "production": "https://api.amadeus.com",
}


class AmadeusProvider(FlightProvider):
    name = "amadeus"

    def __init__(self, options: Optional[dict] = None):
        super().__init__(options)
        self.client_id = env(self.options.get("client_id_env", "AMADEUS_CLIENT_ID"))
        self.client_secret = env(
            self.options.get("client_secret_env", "AMADEUS_CLIENT_SECRET")
        )
        self.host = _HOSTS.get(self.options.get("environment", "test"), _HOSTS["test"])
        self.max_offers = int(self.options.get("max_offers", 8))
        self._token: Optional[str] = None
        self._token_exp = 0.0

    def ready(self) -> bool:
        if not (self.client_id and self.client_secret):
            self._log_skip("AMADEUS_CLIENT_ID / AMADEUS_CLIENT_SECRET not set")
            return False
        return True

    def _get_token(self) -> Optional[str]:
        if self._token and time.time() < self._token_exp - 30:
            return self._token
        try:
            resp = requests.post(
                f"{self.host}/v1/security/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=20,
            )
            resp.raise_for_status()
            payload = resp.json()
            self._token = payload["access_token"]
            self._token_exp = time.time() + float(payload.get("expires_in", 1799))
            return self._token
        except Exception as exc:  # noqa: BLE001 - providers must not crash the run
            log.warning("amadeus auth failed: %s", exc)
            return None

    def search(self, query: SearchQuery) -> list[FlightOffer]:
        token = self._get_token()
        if not token:
            return []
        params = {
            "originLocationCode": query.origin,
            "destinationLocationCode": query.destination,
            "departureDate": query.depart_date.isoformat(),
            "returnDate": query.return_date.isoformat(),
            "adults": query.passengers,
            "currencyCode": "BRL",
            "max": self.max_offers,
        }
        try:
            resp = requests.get(
                f"{self.host}/v2/shopping/flight-offers",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=30,
            )
            if resp.status_code != 200:
                log.warning(
                    "amadeus search %s->%s %s: HTTP %s",
                    query.origin,
                    query.destination,
                    query.depart_date,
                    resp.status_code,
                )
                return []
            data = resp.json().get("data", [])
        except Exception as exc:  # noqa: BLE001
            log.warning("amadeus search error: %s", exc)
            return []

        offers: list[FlightOffer] = []
        for item in data:
            try:
                offers.append(self._parse(item, query))
            except Exception as exc:  # noqa: BLE001
                log.debug("amadeus parse skip: %s", exc)
        return offers

    def _parse(self, item: dict, query: SearchQuery) -> FlightOffer:
        price = item["price"]
        currency = price.get("currency", "BRL")
        grand_total = float(price["grandTotal"])  # total for all travelers
        total_brl = to_brl(grand_total, currency)

        itineraries = item.get("itineraries", [])
        out_segs = itineraries[0]["segments"] if len(itineraries) > 0 else []
        ret_segs = itineraries[1]["segments"] if len(itineraries) > 1 else []

        carriers: list[str] = []
        for seg in [*out_segs, *ret_segs]:
            code = seg.get("carrierCode")
            if code:
                carriers.append(code)

        return FlightOffer(
            origin=query.origin,
            destination=query.destination,
            depart_date=query.depart_date,
            return_date=query.return_date,
            passengers=query.passengers,
            price_total_brl=round(total_brl, 2),
            airlines=tuple(dict.fromkeys(carriers)),  # dedupe, keep order
            provider=self.name,
            outbound_stops=max(len(out_segs) - 1, 0),
            return_stops=max(len(ret_segs) - 1, 0),
            deep_link=None,
            raw_currency=currency,
            raw_price=grand_total,
        )
