"""Domain models for the flight tracker.

Everything the rest of the app reasons about is a small, immutable-ish
dataclass defined here: a search request, a raw flight offer coming from a
provider, and a fully scored trip option ready to be ranked and alerted on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


@dataclass(frozen=True)
class Airport:
    """A configured airport with the ground-transfer assumptions we use for
    scoring (how long / how expensive it is to get between this airport and
    either home in São Paulo or the final destination, Itacaré)."""

    code: str
    name: str
    preference: int  # 1 = most preferred, higher = worse
    hours_each_way: float  # ground transfer time, each direction
    ground_cost_roundtrip_brl: float  # extra ground cost vs the baseline airport


@dataclass
class SearchLeg:
    """A single directional search: origin -> destination on a given date."""

    origin: str
    destination: str
    depart_date: date


@dataclass
class SearchQuery:
    """A round-trip search for a specific route, date pair and party size."""

    origin: str
    destination: str
    depart_date: date
    return_date: date
    passengers: int
    currency: str = "BRL"

    @property
    def nights(self) -> int:
        return (self.return_date - self.depart_date).days

    def key(self) -> str:
        return (
            f"{self.origin}-{self.destination}:"
            f"{self.depart_date.isoformat()}_{self.return_date.isoformat()}"
            f"@{self.passengers}pax"
        )


@dataclass
class FlightOffer:
    """A raw priced round-trip offer returned by a provider.

    `price_total_brl` is already for the whole party (all passengers)."""

    origin: str
    destination: str
    depart_date: date
    return_date: date
    passengers: int
    price_total_brl: float
    airlines: tuple[str, ...]  # IATA carrier codes across all segments
    provider: str
    outbound_stops: int = 0
    return_stops: int = 0
    outbound_duration_min: Optional[int] = None
    return_duration_min: Optional[int] = None
    deep_link: Optional[str] = None
    raw_currency: Optional[str] = None
    raw_price: Optional[float] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def nights(self) -> int:
        return (self.return_date - self.depart_date).days

    @property
    def total_stops(self) -> int:
        return self.outbound_stops + self.return_stops


@dataclass
class ScoredOption:
    """A flight offer plus the derived 'effective cost' used for ranking.

    The effective cost is what the trip *really* costs us once ground
    transfer money and time (and soft airline preference) are folded in on
    top of the airfare. Lower is better."""

    offer: FlightOffer
    airfare_brl: float
    origin_ground_cost_brl: float
    dest_ground_cost_brl: float
    time_cost_brl: float
    airline_penalty_brl: float
    effective_cost_brl: float
    total_transfer_hours: float
    is_preferred_airline: bool
    score_breakdown: dict = field(default_factory=dict)

    @property
    def offer_key(self) -> str:
        o = self.offer
        return (
            f"{o.origin}-{o.destination}:"
            f"{o.depart_date.isoformat()}_{o.return_date.isoformat()}"
            f"@{o.passengers}pax/{'+'.join(o.airlines) or '??'}"
        )
