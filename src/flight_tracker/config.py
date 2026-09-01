"""Configuration loading.

Config lives in a YAML file (see ``config.example.yaml``). Secrets never live
in YAML — anything sensitive is read from environment variables, and the YAML
only references the env var *name*. This keeps the committed config safe to
push and makes the GitHub Action work purely off repository secrets.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import yaml

from .models import Airport


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


@dataclass
class WindowConfig:
    window_start: date
    window_end: date
    core_start: date  # trip MUST already be underway by this date
    core_end: date  # trip MUST NOT end before this date
    min_nights: int
    max_nights: int


@dataclass
class ScoringConfig:
    value_per_hour_brl: float
    preferred_airlines: list[str]
    airline_penalty_brl: float
    stop_penalty_brl: float
    currency: str = "BRL"


@dataclass
class AlertConfig:
    target_price_brl: Optional[float]  # alert on anything at/under this airfare
    min_improvement_brl: float  # only re-alert if best improves by >= this
    top_n: int  # how many options to include in a report
    alert_on_first_run: bool = True


@dataclass
class ProviderConfig:
    name: str
    enabled: bool
    options: dict = field(default_factory=dict)


@dataclass
class NotifierConfig:
    name: str
    enabled: bool
    options: dict = field(default_factory=dict)


@dataclass
class Config:
    passengers_primary: int
    passengers_also: list[int]
    window: WindowConfig
    origins: list[Airport]
    destinations: list[Airport]
    scoring: ScoringConfig
    alerts: AlertConfig
    providers: list[ProviderConfig]
    notifiers: list[NotifierConfig]
    state_path: str
    max_date_pairs: Optional[int] = None  # cap search space (None = all)
    request_delay_seconds: float = 0.5

    @property
    def all_passenger_counts(self) -> list[int]:
        seen: list[int] = []
        for p in [self.passengers_primary, *self.passengers_also]:
            if p not in seen:
                seen.append(p)
        return seen

    def origin_map(self) -> dict[str, Airport]:
        return {a.code: a for a in self.origins}

    def destination_map(self) -> dict[str, Airport]:
        return {a.code: a for a in self.destinations}


def _airport(d: dict) -> Airport:
    return Airport(
        code=d["code"].strip().upper(),
        name=d.get("name", d["code"]),
        preference=int(d.get("preference", 99)),
        hours_each_way=float(d.get("hours_each_way", 1.0)),
        ground_cost_roundtrip_brl=float(d.get("ground_cost_roundtrip_brl", 0.0)),
    )


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    trip = data["trip"]
    passengers = trip.get("passengers", {})

    window = WindowConfig(
        window_start=_as_date(trip["window_start"]),
        window_end=_as_date(trip["window_end"]),
        core_start=_as_date(trip["core_start"]),
        core_end=_as_date(trip["core_end"]),
        min_nights=int(trip["min_nights"]),
        max_nights=int(trip["max_nights"]),
    )

    origins = sorted(
        (_airport(a) for a in data["origins"]), key=lambda a: a.preference
    )
    destinations = sorted(
        (_airport(a) for a in data["destinations"]), key=lambda a: a.preference
    )

    sc = data.get("scoring", {})
    scoring = ScoringConfig(
        value_per_hour_brl=float(sc.get("value_per_hour_brl", 25.0)),
        preferred_airlines=[c.upper() for c in sc.get("preferred_airlines", [])],
        airline_penalty_brl=float(sc.get("airline_penalty_brl", 0.0)),
        stop_penalty_brl=float(sc.get("stop_penalty_brl", 0.0)),
        currency=sc.get("currency", "BRL"),
    )

    al = data.get("alerts", {})
    alerts = AlertConfig(
        target_price_brl=(
            float(al["target_price_brl"])
            if al.get("target_price_brl") is not None
            else None
        ),
        min_improvement_brl=float(al.get("min_improvement_brl", 50.0)),
        top_n=int(al.get("top_n", 5)),
        alert_on_first_run=bool(al.get("alert_on_first_run", True)),
    )

    providers = [
        ProviderConfig(
            name=p["name"],
            enabled=bool(p.get("enabled", True)),
            options=p.get("options", {}) or {},
        )
        for p in data.get("providers", [])
    ]

    notifiers = [
        NotifierConfig(
            name=n["name"],
            enabled=bool(n.get("enabled", True)),
            options=n.get("options", {}) or {},
        )
        for n in data.get("notifiers", [])
    ]

    return Config(
        passengers_primary=int(passengers.get("primary", 2)),
        passengers_also=[int(x) for x in passengers.get("also", [])],
        window=window,
        origins=origins,
        destinations=destinations,
        scoring=scoring,
        alerts=alerts,
        providers=providers,
        notifiers=notifiers,
        state_path=data.get("state_path", "state/best_seen.json"),
        max_date_pairs=(
            int(data["max_date_pairs"]) if data.get("max_date_pairs") else None
        ),
        request_delay_seconds=float(data.get("request_delay_seconds", 0.5)),
    )


def env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read an environment variable, treating empty strings as unset."""
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default
    return val.strip()
