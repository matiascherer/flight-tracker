"""Rendering scored options into human-readable output.

Three surfaces:
* ``render_console`` — a table for the terminal / CI logs.
* ``render_email_html`` / ``render_email_text`` — the email body.
* ``render_whatsapp`` — a tight, emoji-light summary that fits CallMeBot.

All money is BRL. Each row shows the airfare *and* the effective cost so you can
see why an Ilhéus option can beat a cheaper-on-paper Salvador one.
"""

from __future__ import annotations

from datetime import date

from .config import Config
from .models import ScoredOption

_WEEKDAY_PT = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _fmt_date(d: date) -> str:
    return f"{_WEEKDAY_PT[d.weekday()]} {d.day:02d}/{d.month:02d}"


def _brl(v: float) -> str:
    return f"R$ {v:,.0f}".replace(",", ".")


def _airport_name(code: str, config: Config) -> str:
    a = config.origin_map().get(code) or config.destination_map().get(code)
    return a.name if a else code


def _one_line(opt: ScoredOption, config: Config) -> str:
    o = opt.offer
    carriers = "+".join(o.airlines) or "??"
    star = "★" if opt.is_preferred_airline else " "
    stops = "direto" if o.total_stops == 0 else f"{o.total_stops} escala(s)"
    return (
        f"{star} {_brl(opt.effective_cost_brl)} efet. "
        f"(passagem {_brl(opt.airfare_brl)}) | "
        f"{o.origin}→{o.destination} {carriers} {stops} | "
        f"{_fmt_date(o.depart_date)}→{_fmt_date(o.return_date)} "
        f"({o.nights}n) | {o.passengers}pax | {o.provider}"
    )


def render_console(ranked: list[ScoredOption], config: Config, top_n: int) -> str:
    lines = ["Melhores opções (ordenadas por custo efetivo):", ""]
    for i, opt in enumerate(ranked[:top_n], 1):
        lines.append(f"{i:2d}. {_one_line(opt, config)}")
    if not ranked:
        lines.append("(nenhuma oferta encontrada)")
    return "\n".join(lines)


def render_whatsapp(
    best_by_pax: dict[int, ScoredOption], config: Config, reasons: dict[int, str]
) -> str:
    parts = ["✈️ *Itacaré Ano Novo* — alerta de preço"]
    for pax in sorted(best_by_pax):
        opt = best_by_pax[pax]
        o = opt.offer
        carriers = "+".join(o.airlines) or "??"
        parts.append(
            f"\n👥 {pax} pax: {_brl(opt.airfare_brl)} passagem "
            f"({_brl(opt.effective_cost_brl)} efet.)\n"
            f"{o.origin}→{o.destination} {carriers} · "
            f"{_fmt_date(o.depart_date)}→{_fmt_date(o.return_date)} ({o.nights}n)"
        )
        if pax in reasons:
            parts.append(f"↳ {reasons[pax]}")
    return "\n".join(parts)


def render_email_text(
    ranked_by_pax: dict[int, list[ScoredOption]],
    config: Config,
    reasons: dict[int, str],
) -> str:
    out: list[str] = ["Rastreador de voos — Itacaré / Ano Novo 2026-2027", ""]
    if reasons:
        out.append("Motivo do alerta:")
        for pax, r in sorted(reasons.items()):
            out.append(f"  • {r}")
        out.append("")
    for pax in sorted(ranked_by_pax):
        out.append(f"=== {pax} passageiro(s) ===")
        out.append(render_console(ranked_by_pax[pax], config, config.alerts.top_n))
        out.append("")
    out.append(
        "Legenda: 'custo efetivo' = passagem + transporte em SP e na BA "
        "(tempo e custo de solo, incl. ferry/combustível de Salvador). "
        "★ = companhia preferida."
    )
    return "\n".join(out)


def render_email_html(
    ranked_by_pax: dict[int, list[ScoredOption]],
    config: Config,
    reasons: dict[int, str],
) -> str:
    def row(i: int, opt: ScoredOption) -> str:
        o = opt.offer
        carriers = "+".join(o.airlines) or "??"
        star = "★" if opt.is_preferred_airline else ""
        stops = "direto" if o.total_stops == 0 else f"{o.total_stops} escala(s)"
        link = (
            f'<a href="{o.deep_link}">reservar</a>'
            if o.deep_link and o.deep_link.startswith("http")
            else "&nbsp;"
        )
        return (
            f"<tr>"
            f"<td style='text-align:right;padding:4px 8px'>{i}</td>"
            f"<td style='padding:4px 8px'><b>{_brl(opt.effective_cost_brl)}</b></td>"
            f"<td style='padding:4px 8px'>{_brl(opt.airfare_brl)}</td>"
            f"<td style='padding:4px 8px'>{o.origin}→{o.destination}</td>"
            f"<td style='padding:4px 8px'>{carriers} {star}</td>"
            f"<td style='padding:4px 8px'>{stops}</td>"
            f"<td style='padding:4px 8px'>{_fmt_date(o.depart_date)}→"
            f"{_fmt_date(o.return_date)} ({o.nights}n)</td>"
            f"<td style='padding:4px 8px'>{o.provider}</td>"
            f"<td style='padding:4px 8px'>{link}</td>"
            f"</tr>"
        )

    blocks: list[str] = [
        "<div style='font-family:system-ui,Arial,sans-serif;color:#111'>",
        "<h2 style='margin:0 0 4px'>✈️ Itacaré — Ano Novo 2026/2027</h2>",
        "<p style='margin:0 0 12px;color:#555'>Rastreador de melhores ofertas</p>",
    ]
    if reasons:
        items = "".join(f"<li>{r}</li>" for r in reasons.values())
        blocks.append(
            f"<div style='background:#eef7ee;border:1px solid #cbe3cb;"
            f"padding:8px 12px;border-radius:6px;margin-bottom:12px'>"
            f"<b>Por que este alerta:</b><ul style='margin:6px 0'>{items}</ul></div>"
        )
    for pax in sorted(ranked_by_pax):
        header = (
            "<tr style='background:#f2f2f2;text-align:left'>"
            "<th style='padding:4px 8px'>#</th>"
            "<th style='padding:4px 8px'>Custo efetivo</th>"
            "<th style='padding:4px 8px'>Passagem</th>"
            "<th style='padding:4px 8px'>Rota</th>"
            "<th style='padding:4px 8px'>Cia</th>"
            "<th style='padding:4px 8px'>Escalas</th>"
            "<th style='padding:4px 8px'>Datas</th>"
            "<th style='padding:4px 8px'>Fonte</th>"
            "<th style='padding:4px 8px'></th></tr>"
        )
        rows = "".join(
            row(i, opt)
            for i, opt in enumerate(ranked_by_pax[pax][: config.alerts.top_n], 1)
        )
        blocks.append(f"<h3 style='margin:16px 0 4px'>{pax} passageiro(s)</h3>")
        blocks.append(
            "<table style='border-collapse:collapse;font-size:13px;"
            f"border:1px solid #ddd'>{header}{rows}</table>"
        )
    blocks.append(
        "<p style='color:#777;font-size:12px;margin-top:16px'>"
        "Custo efetivo = passagem + custo/tempo de transporte em SP e na BA "
        "(inclui a diferença de Salvador estar bem mais longe de Itacaré que "
        "Ilhéus). ★ = companhia preferida.</p></div>"
    )
    return "".join(blocks)
