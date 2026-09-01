import copy
from datetime import date

from conftest import CONFIG_PATH

from flight_tracker.config import load_config
from flight_tracker.models import FlightOffer, ScoredOption
from flight_tracker.providers.sample import SampleProvider
from flight_tracker.state import evaluate_alerts
from flight_tracker.tracker import _dedupe, build_queries, run


def test_build_queries_covers_routes_dates_pax():
    cfg = load_config(CONFIG_PATH)
    queries = build_queries(cfg)
    # 3 origins x 2 destinations x N date pairs x 2 party sizes
    routes = len(cfg.origins) * len(cfg.destinations)
    from flight_tracker.dates import generate_date_pairs

    pairs = len(generate_date_pairs(cfg.window))
    assert len(queries) == routes * pairs * len(cfg.all_passenger_counts)


def test_dedupe_keeps_cheapest():
    a = FlightOffer("CGH", "IOS", date(2026, 12, 28), date(2027, 1, 4), 2,
                    2200, ("LA",), "amadeus")
    b = FlightOffer("CGH", "IOS", date(2026, 12, 28), date(2027, 1, 4), 2,
                    2100, ("LA",), "kiwi_tequila")
    out = _dedupe([a, b])
    assert len(out) == 1
    assert out[0].price_total_brl == 2100


def test_sample_provider_deterministic():
    cfg = load_config(CONFIG_PATH)
    q = build_queries(cfg)[0]
    p = SampleProvider()
    first = p.search(q)
    second = p.search(q)
    assert first and [o.price_total_brl for o in first] == [
        o.price_total_brl for o in second
    ]


def test_end_to_end_dry_run_sample_only():
    cfg = load_config(CONFIG_PATH)
    # keep the test fast/offline: sample provider only, no network calls
    cfg.providers = [p for p in cfg.providers if p.name == "sample"]
    cfg.request_delay_seconds = 0.0
    cfg.max_date_pairs = 2
    result = run(cfg, dry_run=True)
    assert result.offers > 0
    assert cfg.passengers_primary in result.best_by_pax
    # ranked ascending by effective cost
    for ranked in result.ranked_by_pax.values():
        costs = [s.effective_cost_brl for s in ranked]
        assert costs == sorted(costs)


def test_alert_first_run_then_quiet():
    cfg = load_config(CONFIG_PATH)
    o = FlightOffer("CGH", "IOS", date(2026, 12, 28), date(2027, 1, 4), 2,
                    5000, ("LA",), "sample")
    scored = ScoredOption(
        offer=o, airfare_brl=5000, origin_ground_cost_brl=0, dest_ground_cost_brl=0,
        time_cost_brl=0, airline_penalty_brl=0, effective_cost_brl=5000,
        total_transfer_hours=4, is_preferred_airline=True,
    )
    state = {"version": 1, "by_pax": {}}
    d1 = evaluate_alerts({2: scored}, state, cfg.alerts)
    assert d1.should_alert  # first run alerts

    # same best again -> no alert
    d2 = evaluate_alerts({2: scored}, copy.deepcopy(state), cfg.alerts)
    assert not d2.should_alert


def test_alert_on_improvement():
    cfg = load_config(CONFIG_PATH)
    state = {"version": 1, "by_pax": {"2": {
        "best_effective_brl": 5000, "last_alert_effective_brl": 5000,
        "under_target_alerted": False,
    }}}
    better = ScoredOption(
        offer=FlightOffer("CGH", "IOS", date(2026, 12, 28), date(2027, 1, 4), 2,
                          4000, ("LA",), "sample"),
        airfare_brl=4000, origin_ground_cost_brl=0, dest_ground_cost_brl=0,
        time_cost_brl=0, airline_penalty_brl=0, effective_cost_brl=4000,
        total_transfer_hours=4, is_preferred_airline=True,
    )
    d = evaluate_alerts({2: better}, state, cfg.alerts)
    assert d.should_alert
