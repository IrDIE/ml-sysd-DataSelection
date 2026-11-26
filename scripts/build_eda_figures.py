#!/usr/bin/env python3
"""Build public-safe SVG figures from the sanitized EDA snapshot."""

from __future__ import annotations

import csv
import html
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "eda"
FIGURES = ROOT / "reports" / "figures"

BLUE = "#2563eb"
GREEN = "#0f9f6e"
ORANGE = "#e8791f"
SLATE = "#64748b"
GRID = "#d9e2ec"
TEXT = "#172033"
MUTED = "#526277"
BACKGROUND = "#ffffff"


def rows(name: str) -> list[dict[str, str]]:
    with (DATA / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def text_element(
    x: float,
    y: float,
    value: object,
    *,
    size: int = 13,
    anchor: str = "start",
    weight: int = 400,
    fill: str = TEXT,
) -> str:
    escaped = html.escape(str(value))
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Inter,Arial,sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{escaped}</text>'
    )


def base_svg(width: int, height: int, title: str, subtitle: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>',
        text_element(36, 38, title, size=21, weight=700),
        text_element(36, 62, subtitle, size=12, fill=MUTED),
    ]


def write_svg(name: str, parts: list[str]) -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    parts.append("</svg>")
    (FIGURES / name).write_text("\n".join(parts) + "\n")


def format_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.2f} млн"
    if value >= 1_000:
        return f"{value / 1_000:.0f} тыс."
    return str(value)


def build_funnel() -> None:
    stage_labels = {
        "raw_rows": "Исходные строки",
        "scenes": "Собранные сцены",
        "valid": "Прошли quality gate",
        "clustered": "Получили cluster",
        "candidates": "Кандидаты",
        "after_ride_cap": "После ride cap",
        "accepted": "Приняты",
        "index": "В selected index",
    }
    totals: dict[str, int] = defaultdict(int)
    order: dict[str, int] = {}
    for row in rows("funnel.csv"):
        totals[row["stage"]] += int(row["scenes"])
        order[row["stage"]] = int(row["stage_order"])

    ordered = sorted(totals, key=order.get)
    width, height = 920, 500
    left, top, chart_width, row_height = 220, 92, 600, 47
    maximum = max(totals.values())
    parts = base_svg(
        width,
        height,
        "Воронка подготовки данных",
        "Сумма по девяти обезличенным батчам; одна сцена может состоять из нескольких строк.",
    )
    for index, stage in enumerate(ordered):
        y = top + index * row_height
        bar_width = chart_width * totals[stage] / maximum
        color = BLUE if stage not in {"accepted", "index"} else GREEN
        parts.append(text_element(left - 14, y + 21, stage_labels[stage], anchor="end"))
        parts.append(
            f'<rect x="{left}" y="{y}" width="{bar_width:.1f}" height="29" '
            f'rx="4" fill="{color}" opacity="0.9"/>'
        )
        parts.append(
            text_element(left + bar_width + 10, y + 20, format_count(totals[stage]), weight=600)
        )
    write_svg("funnel.svg", parts)


def build_batch_rates() -> None:
    by_batch: dict[str, dict[str, int]] = defaultdict(dict)
    for row in rows("funnel.csv"):
        by_batch[row["batch_id"]][row["stage"]] = int(row["scenes"])

    batches = sorted(by_batch)
    cap_rates = [by_batch[key]["after_ride_cap"] / by_batch[key]["candidates"] for key in batches]
    selection_rates = [by_batch[key]["accepted"] / by_batch[key]["candidates"] for key in batches]

    width, height = 920, 490
    left, top, chart_width, chart_height = 82, 100, 790, 305
    maximum = 0.45
    parts = base_svg(
        width,
        height,
        "Доля сцен после ограничений и отбора",
        "Порядок B01–B09 соответствует порядку обработки; даты и источники скрыты.",
    )
    for step in range(6):
        value = step * 0.1
        y = top + chart_height * (1 - value / maximum)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_width}" y2="{y:.1f}" stroke="{GRID}"/>'
        )
        parts.append(
            text_element(left - 12, y + 4, f"{value:.0%}", anchor="end", size=11, fill=MUTED)
        )

    group_width = chart_width / len(batches)
    bar_width = group_width * 0.29
    for index, batch in enumerate(batches):
        center = left + group_width * (index + 0.5)
        for offset, rate, color in (
            (-bar_width, cap_rates[index], ORANGE),
            (0, selection_rates[index], BLUE),
        ):
            bar_height = chart_height * rate / maximum
            x = center + offset
            y = top + chart_height - bar_height
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
                f'height="{bar_height:.1f}" rx="2" fill="{color}"/>'
            )
        parts.append(text_element(center, top + chart_height + 24, batch, anchor="middle", size=11))
        parts.append(
            text_element(
                center + bar_width * 0.5,
                top + chart_height - chart_height * selection_rates[index] / maximum - 7,
                f"{selection_rates[index]:.1%}",
                anchor="middle",
                size=10,
                fill=BLUE,
            )
        )

    parts.append(f'<rect x="{left + 520}" y="78" width="13" height="13" fill="{ORANGE}"/>')
    parts.append(text_element(left + 540, 89, "после ride cap", size=11))
    parts.append(f'<rect x="{left + 650}" y="78" width="13" height="13" fill="{BLUE}"/>')
    parts.append(text_element(left + 670, 89, "приняты", size=11))
    write_svg("batch_rates.svg", parts)


def build_cluster_balance() -> None:
    aggregate: dict[str, dict[str, object]] = {}
    for row in rows("distributions.csv"):
        if row["dimension"] != "cluster":
            continue
        item = aggregate.setdefault(
            row["key"],
            {"population": 0, "accepted": 0, "kind": row["cluster_kind"]},
        )
        item["population"] = int(item["population"]) + int(row["population"])
        item["accepted"] = int(item["accepted"]) + int(row["accepted"])

    ordered = sorted(aggregate, key=lambda key: int(aggregate[key]["population"]), reverse=True)
    total_population = sum(int(item["population"]) for item in aggregate.values())
    total_accepted = sum(int(item["accepted"]) for item in aggregate.values())
    population = [int(aggregate[key]["population"]) / total_population for key in ordered]
    accepted = [int(aggregate[key]["accepted"]) / total_accepted for key in ordered]

    width, height = 1060, 520
    left, top, chart_width, chart_height = 70, 105, 940, 315
    maximum = max(population + accepted) * 1.1
    parts = base_svg(
        width,
        height,
        "Баланс trajectory clusters до и после отбора",
        "Кластеры обезличены и отсортированы по размеру исходной популяции.",
    )
    for step in range(5):
        value = maximum * step / 4
        y = top + chart_height * (1 - value / maximum)
        parts.append(
            f'<line x1="{left}" y1="{y:.1f}" x2="{left + chart_width}" y2="{y:.1f}" stroke="{GRID}"/>'
        )
        parts.append(
            text_element(left - 9, y + 4, f"{value:.0%}", anchor="end", size=10, fill=MUTED)
        )

    group_width = chart_width / len(ordered)
    bar_width = group_width * 0.34
    for index, key in enumerate(ordered):
        center = left + group_width * (index + 0.5)
        for offset, share, color in (
            (-bar_width, population[index], SLATE),
            (0, accepted[index], BLUE),
        ):
            bar_height = chart_height * share / maximum
            parts.append(
                f'<rect x="{center + offset:.1f}" y="{top + chart_height - bar_height:.1f}" '
                f'width="{bar_width:.1f}" height="{bar_height:.1f}" fill="{color}"/>'
            )
        parts.append(text_element(center, top + chart_height + 22, key, anchor="middle", size=9))

    parts.append(f'<rect x="{left + 660}" y="80" width="13" height="13" fill="{SLATE}"/>')
    parts.append(text_element(left + 680, 91, "до отбора", size=11))
    parts.append(f'<rect x="{left + 755}" y="80" width="13" height="13" fill="{BLUE}"/>')
    parts.append(text_element(left + 775, 91, "selected index", size=11))
    write_svg("cluster_balance.svg", parts)


def build_context_rates() -> None:
    aggregate: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for row in rows("distributions.csv"):
        if row["dimension"] == "context":
            aggregate[row["key"]][0] += int(row["population"])
            aggregate[row["key"]][1] += int(row["accepted"])

    values = sorted(
        (
            (key, accepted / population, population)
            for key, (population, accepted) in aggregate.items()
        ),
        key=lambda item: item[1],
    )
    width, height = 920, 580
    left, top, chart_width, row_height = 225, 95, 610, 43
    parts = base_svg(
        width,
        height,
        "Acceptance rate по semantic context",
        "Редкие приоритетные контексты намеренно получают более высокий шанс включения.",
    )
    for index, (key, rate, population) in enumerate(values):
        y = top + index * row_height
        parts.append(text_element(left - 12, y + 20, key, anchor="end", size=12))
        parts.append(
            f'<rect x="{left}" y="{y}" width="{chart_width}" height="27" rx="4" fill="#edf2f7"/>'
        )
        parts.append(
            f'<rect x="{left}" y="{y}" width="{chart_width * rate:.1f}" height="27" '
            f'rx="4" fill="{GREEN}"/>'
        )
        parts.append(text_element(left + chart_width + 10, y + 19, f"{rate:.1%}", weight=600))
        parts.append(
            text_element(left + 8, y + 19, f"n={format_count(population)}", size=10, fill=TEXT)
        )
    write_svg("context_rates.svg", parts)


def main() -> None:
    build_funnel()
    build_batch_rates()
    build_cluster_balance()
    build_context_rates()
    print(f"wrote figures to {FIGURES}")


if __name__ == "__main__":
    main()
