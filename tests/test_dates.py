from datetime import date

from conftest import CONFIG_PATH

from flight_tracker.config import load_config
from flight_tracker.dates import generate_date_pairs


def test_all_pairs_respect_window_and_core():
    cfg = load_config(CONFIG_PATH)
    pairs = generate_date_pairs(cfg.window)
    assert pairs, "should produce at least one valid pair"

    core_start = date(2026, 12, 30)
    core_end = date(2027, 1, 3)
    for depart, ret in pairs:
        # inside outer window
        assert depart >= cfg.window.window_start
        assert ret <= cfg.window.window_end
        # core block fully covered
        assert depart <= core_start
        assert ret >= core_end
        # length bounds
        nights = (ret - depart).days
        assert cfg.window.min_nights <= nights <= cfg.window.max_nights


def test_short_core_only_trip_is_excluded():
    # 30-Dec -> 03-Jan is only 4 nights, below the 6-night minimum.
    cfg = load_config(CONFIG_PATH)
    pairs = generate_date_pairs(cfg.window)
    assert (date(2026, 12, 30), date(2027, 1, 3)) not in pairs


def test_max_length_pair_present():
    cfg = load_config(CONFIG_PATH)
    pairs = generate_date_pairs(cfg.window)
    # 24-Dec -> 07-Jan is exactly 14 nights and covers the core block.
    assert (date(2026, 12, 24), date(2027, 1, 7)) in pairs
