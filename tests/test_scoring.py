from datetime import date

from conftest import CONFIG_PATH

from flight_tracker.config import load_config
from flight_tracker.models import FlightOffer
from flight_tracker.scoring import score_offer


def _offer(origin, dest, price, airlines, stops=0, pax=2):
    return FlightOffer(
        origin=origin,
        destination=dest,
        depart_date=date(2026, 12, 28),
        return_date=date(2027, 1, 4),
        passengers=pax,
        price_total_brl=price,
        airlines=airlines,
        provider="test",
        outbound_stops=stops,
        return_stops=stops,
    )


def test_salvador_penalised_vs_ilheus():
    cfg = load_config(CONFIG_PATH)
    # Salvador ticket is 300 cheaper, but its ground cost/time should make the
    # effective cost worse than Ilhéus for a similar fare.
    ilheus = score_offer(_offer("CGH", "IOS", 2000, ("LA",)), cfg)
    salvador = score_offer(_offer("CGH", "SSA", 1700, ("LA",)), cfg)
    assert salvador.effective_cost_brl > ilheus.effective_cost_brl


def test_preferred_airline_no_penalty():
    cfg = load_config(CONFIG_PATH)
    latam = score_offer(_offer("CGH", "IOS", 2000, ("LA",)), cfg)
    gol = score_offer(_offer("CGH", "IOS", 2000, ("G3",)), cfg)
    assert latam.is_preferred_airline is True
    assert gol.is_preferred_airline is False
    assert gol.effective_cost_brl > latam.effective_cost_brl


def test_congonhas_beats_viracopos_same_fare():
    cfg = load_config(CONFIG_PATH)
    cgh = score_offer(_offer("CGH", "IOS", 2000, ("LA",)), cfg)
    vcp = score_offer(_offer("VCP", "IOS", 2000, ("LA",)), cfg)
    assert cgh.effective_cost_brl < vcp.effective_cost_brl


def test_effective_cost_components_add_up():
    cfg = load_config(CONFIG_PATH)
    s = score_offer(_offer("GRU", "SSA", 1800, ("G3",), stops=1), cfg)
    expected = (
        s.airfare_brl
        + s.origin_ground_cost_brl
        + s.dest_ground_cost_brl
        + s.time_cost_brl
        + s.airline_penalty_brl
        + s.score_breakdown["stop_penalty_brl"]
    )
    assert abs(s.effective_cost_brl - round(expected, 2)) < 0.01
