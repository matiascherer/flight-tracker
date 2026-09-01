"""Turn a raw flight offer into an 'effective cost' we can rank.

The brief asks to minimise *money spent* while also minimising *transport time*
in São Paulo and Bahia, and to remember that Salvador is much farther from
Itacaré than Ilhéus (extra car rental / ferry / fuel). We fold all of that into
a single comparable number, the effective cost in BRL:

    effective = airfare
              + origin ground cost      (money: airport <-> home in SP)
              + destination ground cost (money: airport <-> Itacaré, incl. the
                                         Salvador ferry/fuel/extra-rental gap)
              + time cost               (transfer hours priced at value/hour)
              + airline penalty         (soft nudge toward LATAM)
              + stop penalty            (soft nudge toward fewer connections)

Airfare dominates by design; the ground/time terms are what break ties and
correctly make an Ilhéus offer beat a Salvador offer that is only slightly
cheaper on the ticket.
"""

from __future__ import annotations

from .config import Config
from .models import FlightOffer, ScoredOption


def score_offer(offer: FlightOffer, config: Config) -> ScoredOption:
    origins = config.origin_map()
    dests = config.destination_map()

    origin = origins.get(offer.origin)
    dest = dests.get(offer.destination)

    # Unknown airports (shouldn't happen for our own searches) get neutral,
    # slightly pessimistic assumptions so they don't win by accident.
    origin_hours = origin.hours_each_way if origin else 2.0
    origin_ground = origin.ground_cost_roundtrip_brl if origin else 100.0
    dest_hours = dest.hours_each_way if dest else 3.0
    dest_ground = dest.ground_cost_roundtrip_brl if dest else 300.0

    # Ground transfer happens twice per airport across the round trip.
    total_transfer_hours = (origin_hours + dest_hours) * 2.0
    time_cost = total_transfer_hours * config.scoring.value_per_hour_brl

    preferred = _is_preferred(offer.airlines, config.scoring.preferred_airlines)
    airline_penalty = 0.0 if preferred else config.scoring.airline_penalty_brl

    stop_penalty = offer.total_stops * config.scoring.stop_penalty_brl

    airfare = offer.price_total_brl
    effective = (
        airfare
        + origin_ground
        + dest_ground
        + time_cost
        + airline_penalty
        + stop_penalty
    )

    breakdown = {
        "airfare_brl": round(airfare, 2),
        "origin_ground_cost_brl": round(origin_ground, 2),
        "dest_ground_cost_brl": round(dest_ground, 2),
        "time_cost_brl": round(time_cost, 2),
        "airline_penalty_brl": round(airline_penalty, 2),
        "stop_penalty_brl": round(stop_penalty, 2),
        "total_transfer_hours": round(total_transfer_hours, 2),
    }

    return ScoredOption(
        offer=offer,
        airfare_brl=airfare,
        origin_ground_cost_brl=origin_ground,
        dest_ground_cost_brl=dest_ground,
        time_cost_brl=time_cost,
        airline_penalty_brl=airline_penalty,
        effective_cost_brl=round(effective, 2),
        total_transfer_hours=total_transfer_hours,
        is_preferred_airline=preferred,
        score_breakdown=breakdown,
    )


def _is_preferred(airlines: tuple[str, ...], preferred: list[str]) -> bool:
    if not preferred:
        return True
    pref = {p.upper() for p in preferred}
    # Preferred if *every* operating carrier on the itinerary is in the list.
    codes = {a.upper() for a in airlines if a}
    if not codes:
        return False
    return codes.issubset(pref)


def score_and_rank(
    offers: list[FlightOffer], config: Config
) -> list[ScoredOption]:
    scored = [score_offer(o, config) for o in offers]
    scored.sort(key=lambda s: s.effective_cost_brl)
    return scored
