from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph


ROOT = Path(r"C:\MATDEM_MICROPLASTIC")
STAGE31E = ROOT / "stage31_evaluations/stage31e_replicated_nested_cpd2_gpu_20260826/gpu_evaluation_01/evaluation.json"
STAGE31F = ROOT / "stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/gpu_evaluation_02/evaluation.json"
VISUAL_AUDIT = ROOT / "stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/visual_audit_01/visual_audit.json"
TMP = ROOT / "tmp/pdfs"
OUT = ROOT / "output/pdf/dem_lbm_microplastic_one_page_summary_20260828.pdf"

NAVY = HexColor("#14324A")
BLUE = HexColor("#2D72B8")
TEAL = HexColor("#249A8D")
GREEN = HexColor("#2F8F5B")
ORANGE = HexColor("#E7854F")
RED = HexColor("#C8534D")
INK = HexColor("#17212B")
MUTED = HexColor("#5B6875")
LIGHT = HexColor("#F4F7FA")
BORDER = HexColor("#D8E0E7")
PALE_BLUE = HexColor("#E9F2FA")
PALE_GREEN = HexColor("#EAF6EF")
PALE_ORANGE = HexColor("#FFF2E8")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def paragraph(c: canvas.Canvas, text: str, x: float, y_top: float, width: float,
              font_size: float = 8.0, leading: float = 10.0,
              color=INK, bold: bool = False, max_height: float = 200) -> float:
    style = ParagraphStyle(
        "body", fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=font_size, leading=leading, textColor=color,
        alignment=TA_LEFT, spaceAfter=0, spaceBefore=0,
    )
    p = Paragraph(text, style)
    _, h = p.wrap(width, max_height)
    p.drawOn(c, x, y_top - h)
    return h


def card(c: canvas.Canvas, x: float, y: float, w: float, h: float,
         value: str, label: str, accent, fill=white) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(BORDER)
    c.roundRect(x, y, w, h, 6, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y, 5, h, 5, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(x + 13, y + h - 21, value)
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 7.4)
    c.drawString(x + 13, y + 9, label)


def make_chart(stage31e: dict, stage31f: dict, path: Path) -> None:
    summaries = stage31e["analysis"]["count_summaries"]
    counts = [1, 2, 4]
    means = [summaries[str(k)]["mean_reduction_percent"] for k in counts]
    raw = [[100 * (1.0 - r) for r in summaries[str(k)]["raw_ratios"]] for k in counts]
    contrasts = stage31f["contrasts"]

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.2})
    fig, axes = plt.subplots(1, 2, figsize=(8.25, 3.25), gridspec_kw={"width_ratios": [1.18, 0.82]})
    fig.patch.set_facecolor("white")

    ax = axes[0]
    xs = np.arange(3)
    bars = ax.bar(xs, means, width=0.58, color=["#82B1D8", "#4D8FC6", "#276EA8"], edgecolor="none")
    jitter = np.array([-0.16, -0.095, -0.03, 0.03, 0.095, 0.16])
    for i, values in enumerate(raw):
        ax.scatter(i + jitter, values, s=18, color="#173F5F", alpha=.75, edgecolor="white", linewidth=.35, zorder=3)
    for bar, value in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width() / 2, value + .055, f"{value:.3f}%", ha="center", va="bottom", fontsize=8, weight="bold")
    ax.set_xticks(xs, ["1 fibre", "2 fibres", "4 fibres"])
    ax.set_ylabel("Conductance reduction (%)")
    ax.set_title("A. Replicated CPD2 count response", loc="left", fontsize=9.5, weight="bold")
    ax.set_ylim(0, 1.9)
    ax.grid(axis="y", alpha=.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.text(.01, -.25, "Bars = mean; dots = six matched packing/block ratios per count", transform=ax.transAxes, fontsize=7.2, color="#596673")

    ax = axes[1]
    names = ["Packing s1", "Packing s2"]
    c2 = [100 * contrasts[k]["cpd2_B_minus_A"] for k in ("n216_s1", "n216_s2")]
    c4 = [100 * contrasts[k]["cpd4_B_minus_A"] for k in ("n216_s1", "n216_s2")]
    x = np.arange(2)
    width = .34
    ax.bar(x - width / 2, c2, width, color="#9AA3AB", label="CPD2")
    ax.bar(x + width / 2, c4, width, color="#8B58B8", label="CPD4")
    ax.axhline(0, color="#313B44", lw=.8)
    ax.set_xticks(x, names)
    ax.set_ylabel("Four-fibre B - A contrast (%)")
    ax.set_title("B. Placement effect changes by packing", loc="left", fontsize=9.5, weight="bold")
    ax.set_ylim(-.72, 1.03)
    ax.grid(axis="y", alpha=.22)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")
    ax.text(.01, -.25, "Opposite signs persist after CPD2 -> CPD4 refinement", transform=ax.transAxes, fontsize=7.2, color="#596673")

    fig.tight_layout(pad=.9, w_pad=2.1)
    fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> int:
    stage31e = load(STAGE31E)
    stage31f = load(STAGE31F)
    visual = load(VISUAL_AUDIT)
    if not (stage31e.get("passed") and stage31f.get("passed") and visual.get("passed")):
        raise RuntimeError("source evidence is not fully passed")

    TMP.mkdir(parents=True, exist_ok=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    chart_path = TMP / "dem_lbm_one_page_chart_20260828.png"
    make_chart(stage31e, stage31f, chart_path)

    page_w, page_h = landscape(A4)
    c = canvas.Canvas(str(OUT), pagesize=(page_w, page_h))
    c.setTitle("DEM-LBM microplastic in sand - one-page summary")
    c.setAuthor("Codex with verified MATDEM_MICROPLASTIC evidence")
    c.setFillColor(LIGHT)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    # Header
    c.setFillColor(NAVY)
    c.rect(0, page_h - 84, page_w, 84, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(28, page_h - 36, "DEM-LBM MICROPLASTIC IN SAND")
    c.setFont("Helvetica", 10)
    c.drawString(28, page_h - 57, "One-page research checkpoint | fixed-solid hydraulics | 28 August 2026")
    badge_w = 133
    c.setFillColor(GREEN)
    c.roundRect(page_w - badge_w - 28, page_h - 57, badge_w, 28, 14, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(page_w - badge_w / 2 - 28, page_h - 46, "STAGE31F VERIFIED")

    # Stat cards
    margin = 28
    gap = 10
    stats_y = page_h - 145
    card_h = 48
    card_w = (page_w - 2 * margin - 3 * gap) / 4
    card(c, margin, stats_y, card_w, card_h, "21 / 21", "replicated CPD2 cases passed", BLUE, PALE_BLUE)
    card(c, margin + card_w + gap, stats_y, card_w, card_h, "7 / 7", "selected CPD4 cases passed", TEAL, PALE_GREEN)
    card(c, margin + 2 * (card_w + gap), stats_y, card_w, card_h, "0.000488", "maximum |CPD4 - CPD2| in k/k0", ORANGE, PALE_ORANGE)
    card(c, margin + 3 * (card_w + gap), stats_y, card_w, card_h, "ALL PASS", "hashes, convergence, health, balance", GREEN, PALE_GREEN)

    # Main graphic panel
    left_x = margin
    main_y = 205
    left_w = 515
    main_h = 226
    c.setFillColor(white)
    c.setStrokeColor(BORDER)
    c.roundRect(left_x, main_y, left_w, main_h, 7, fill=1, stroke=1)
    c.drawImage(str(chart_path), left_x + 8, main_y + 7, width=left_w - 16, height=main_h - 14, preserveAspectRatio=True, anchor="c", mask="auto")

    # Evidence ladder
    right_x = left_x + left_w + 12
    right_w = page_w - right_x - margin
    c.setFillColor(white)
    c.setStrokeColor(BORDER)
    c.roundRect(right_x, main_y, right_w, main_h, 7, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(right_x + 14, main_y + main_h - 23, "Evidence ladder completed")
    steps = [
        ("1", "Mechanics-qualified geometry", "216-grain periodic LBS specimens; F37 fibres equilibrated and frozen."),
        ("2", "Clean-sand hydraulic baseline", "CPD2/CPD4 convergence and literature sanity comparison completed."),
        ("3", "Mechanism screening", "Concentration, orientation, topology, placement and packing varied without imposed monotonicity."),
        ("4", "Selected CPD4 confirmations", "Two- and four-fibre mechanisms retained obstruction and contrast signs."),
        ("5", "Replication and final refinement", "Three packings at CPD2; selected s1/s2 cases independently verified at CPD4."),
    ]
    y = main_y + main_h - 48
    for idx, title, desc in steps:
        c.setFillColor(GREEN)
        c.circle(right_x + 20, y + 2, 8, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(right_x + 20, y - .5, idx)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 8.2)
        c.drawString(right_x + 34, y + 1, title)
        paragraph(c, desc, right_x + 34, y - 5, right_w - 47, 6.7, 8.1, MUTED)
        y -= 39

    # Bottom conclusions
    bottom_y = 49
    bottom_h = 140
    c.setFillColor(NAVY)
    c.roundRect(margin, bottom_y, page_w - 2 * margin, bottom_h, 7, fill=1, stroke=0)
    col_gap = 22
    col_w = (page_w - 2 * margin - 3 * col_gap) / 3
    headings = [
        ("WHAT THE DATA SUPPORT", TEAL),
        ("MECHANICAL INTERPRETATION", ORANGE),
        ("CLAIM BOUNDARY / NEXT GATE", RED),
    ]
    texts = [
        "<b>Every selected fibre case was obstructive.</b><br/>Mean CPD2 conductance reduction rose from 0.286% (1 fibre) to 0.531% (2) and 0.974% (4). Selected CPD4 ratios preserved all signs.",
        "<b>Count matters, but arrangement is not secondary.</b><br/>The four-fibre B-A placement contrast is positive in packing s1 and negative in s2, showing a packing-dependent pore-path interaction.",
        "<b>Supported:</b> static, fixed-solid relative conductance within the tested 216-grain periodic LBS domain.<br/><b>Not yet supported:</b> absolute lab validation, migration, clogging, deformation, transient flow or two-way coupling.",
    ]
    for i, ((heading, accent), text) in enumerate(zip(headings, texts)):
        x = margin + 14 + i * (col_w + col_gap)
        c.setFillColor(accent)
        c.rect(x, bottom_y + bottom_h - 25, 24, 3, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x, bottom_y + bottom_h - 39, heading)
        paragraph(c, text, x, bottom_y + bottom_h - 48, col_w - 4, 7.35, 9.3, white)

    # Footer
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 6.2)
    footer = "Evidence bound to Stage31e independent evaluation and Stage31f gpu_evaluation_02 + visual_audit_01. Failed verifier audit gpu_evaluation_01 is preserved as diagnostic evidence."
    c.drawString(margin, 26, footer)
    c.setFont("Helvetica-Bold", 6.2)
    label = "ONE PAGE | VERIFIED CHECKPOINT"
    c.drawRightString(page_w - margin, 26, label)

    c.showPage()
    c.save()
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
