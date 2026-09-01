"""Orchestration: search -> merge -> score -> decide -> alert.

This is the heart of the tracker. One ``run()`` call:

1. expands the flexible window into concrete date pairs,
2. builds one :class:`SearchQuery` per (route x date-pair x party-size),
3. fans each query out across every ready provider, isolating failures,
4. de-duplicates identical itineraries (keeping the cheapest source),
5. scores + ranks everything by effective cost,
6. compares the new bests against persisted state, and
7. sends email + WhatsApp alerts when something newsworthy shows up.

It's deliberately synchronous and simple — a personal tracker running a few
hundred cheap requests every few hours doesn't need async machinery.
"""

from __future__ import annotations

import itertools
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .config import Config
from .dates import generate_date_pairs
from .models import FlightOffer, ScoredOption, SearchQuery
from .notifiers import build_notifiers
from .providers import build_providers
from .report import (
    render_console,
    render_email_html,
    render_email_text,
    render_whatsapp,
)
from .scoring import score_and_rank
from .state import evaluate_alerts, load_state, save_state

log = logging.getLogger("flight_tracker.tracker")


@dataclass
class RunResult:
    queries: int = 0
    offers: int = 0
    providers_used: list[str] = field(default_factory=list)
    ranked_by_pax: dict[int, list[ScoredOption]] = field(default_factory=dict)
    best_by_pax: dict[int, ScoredOption] = field(default_factory=dict)
    alerted: bool = False
    alert_reasons: dict[int, str] = field(default_factory=dict)
    notified_channels: list[str] = field(default_factory=list)


def build_queries(config: Config) -> list[SearchQuery]:
    date_pairs = generate_date_pairs(config.window)
    if config.max_date_pairs:
        date_pairs = date_pairs[: config.max_date_pairs]

    routes = [
        (o.code, d.code) for o in config.origins for d in config.destinations
    ]
    queries: list[SearchQuery] = []
    for pax in config.all_passenger_counts:
        for (origin, dest), (depart, ret) in itertools.product(routes, date_pairs):
            queries.append(
                SearchQuery(
                    origin=origin,
                    destination=dest,
                    depart_date=depart,
                    return_date=ret,
                    passengers=pax,
                )
            )
    return queries


def _dedupe(offers: list[FlightOffer]) -> list[FlightOffer]:
    """Collapse identical itineraries from different sources to the cheapest."""
    best: dict[tuple, FlightOffer] = {}
    for o in offers:
        key = (
            o.origin,
            o.destination,
            o.depart_date,
            o.return_date,
            o.passengers,
            o.airlines,
            o.total_stops,
        )
        cur = best.get(key)
        if cur is None or o.price_total_brl < cur.price_total_brl:
            best[key] = o
    return list(best.values())


def run(config: Config, dry_run: bool = False) -> RunResult:
    result = RunResult()

    providers = build_providers(config.providers)
    result.providers_used = [p.name for p in providers]
    if not providers:
        log.warning("no providers ready — nothing to search")
        return result

    queries = build_queries(config)
    result.queries = len(queries)
    log.info(
        "running %d queries across providers: %s",
        len(queries),
        ", ".join(result.providers_used),
    )

    all_offers: list[FlightOffer] = []
    for q in queries:
        for provider in providers:
            try:
                offers = provider.search(q)
            except Exception as exc:  # noqa: BLE001 - never let one query kill the run
                log.warning("provider %s crashed on %s: %s", provider.name, q.key(), exc)
                offers = []
            all_offers.extend(offers)
            if config.request_delay_seconds:
                time.sleep(config.request_delay_seconds)

    all_offers = _dedupe(all_offers)
    result.offers = len(all_offers)
    log.info("collected %d unique offers", len(all_offers))

    # Group by party size, score + rank each group.
    for pax in config.all_passenger_counts:
        group = [o for o in all_offers if o.passengers == pax]
        if not group:
            continue
        ranked = score_and_rank(group, config)
        result.ranked_by_pax[pax] = ranked
        result.best_by_pax[pax] = ranked[0]

    if not result.best_by_pax:
        log.warning("no offers found for any party size")
        return result

    # Alert decision against persisted state.
    state = load_state(config.state_path)
    decision = evaluate_alerts(result.best_by_pax, state, config.alerts)
    result.alerted = decision.should_alert
    result.alert_reasons = decision.reasons

    if decision.should_alert and not dry_run:
        result.notified_channels = _notify(config, result, decision.reasons)

    if not dry_run:
        save_state(config.state_path, state)

    return result


def _notify(
    config: Config, result: RunResult, reasons: dict[int, str]
) -> list[str]:
    notifiers = build_notifiers(config.notifiers)
    if not notifiers:
        log.info("alert triggered but no notifier is ready")
        return []

    subject = _subject(result)
    text = render_email_text(result.ranked_by_pax, config, reasons)
    html = render_email_html(result.ranked_by_pax, config, reasons)
    whatsapp = render_whatsapp(result.best_by_pax, config, reasons)

    sent: list[str] = []
    for n in notifiers:
        body = whatsapp if n.name.startswith("whatsapp") else text
        html_body = None if n.name.startswith("whatsapp") else html
        if n.send(subject, body, html_body):
            sent.append(n.name)
    return sent


def _subject(result: RunResult) -> str:
    # Lead with the cheapest airfare across party sizes for a punchy subject.
    cheapest = min(
        (opt.airfare_brl for opt in result.best_by_pax.values()), default=0.0
    )
    return f"✈️ Itacaré Ano Novo — melhor passagem R$ {cheapest:,.0f}".replace(",", ".")


def render_summary(result: RunResult, config: Config) -> str:
    lines = [
        f"Providers: {', '.join(result.providers_used) or '(nenhum)'}",
        f"Queries: {result.queries} | Ofertas únicas: {result.offers}",
        "",
    ]
    for pax in sorted(result.ranked_by_pax):
        lines.append(f"--- {pax} passageiro(s) ---")
        lines.append(render_console(result.ranked_by_pax[pax], config, config.alerts.top_n))
        lines.append("")
    if result.alerted:
        lines.append(f"ALERTA enviado via: {', '.join(result.notified_channels) or '(nenhum canal pronto)'}")
        for pax, r in sorted(result.alert_reasons.items()):
            lines.append(f"  • {r}")
    else:
        lines.append("Sem alerta neste ciclo (nada novo o suficiente).")
    return "\n".join(lines)
