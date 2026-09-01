"""Generation of valid travel-date pairs from the flexible trip window.

The rules encoded here come straight from the trip brief:

* The trip must live entirely inside the outer window
  (``window_start`` .. ``window_end``).
* Trip length must be between ``min_nights`` and ``max_nights`` (inclusive).
* The core New-Year block (``core_start`` .. ``core_end``, i.e. 30-Dec .. 03-Jan)
  is non-negotiable: we must have departed *by* ``core_start`` and return
  *no earlier than* ``core_end``, so the whole block is spent at the
  destination.
"""

from __future__ import annotations

from datetime import date, timedelta

from .config import WindowConfig


def _daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def generate_date_pairs(window: WindowConfig) -> list[tuple[date, date]]:
    """Return every valid ``(depart_date, return_date)`` pair, ordered so the
    combinations closest to the mandatory core block come first."""

    pairs: list[tuple[date, date]] = []

    # Departure can be any day from the window opening up to the core start
    # (we must be there by core_start).
    for depart in _daterange(window.window_start, window.core_start):
        # Return can be any day from the core end up to the window close
        # (we must not leave before core_end).
        for ret in _daterange(window.core_end, window.window_end):
            nights = (ret - depart).days
            if nights < window.min_nights or nights > window.max_nights:
                continue
            pairs.append((depart, ret))

    # Sort by how "tight" the trip is around the core block: shorter trips
    # first (cheaper / easier), then chronological. This is only an ordering
    # convenience — scoring is what actually ranks offers.
    pairs.sort(key=lambda p: ((p[1] - p[0]).days, p[0], p[1]))
    return pairs
