"""Professional PDF diagnostic report generation (ReportLab Platypus)."""
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config import Config
from utils.logging_utils import get_logger
from utils.system_utils import format_bytes, format_uptime

logger = get_logger(__name__)


def _p(text):
    return Paragraph(text, ParagraphStyle(
        "body", fontSize=9, leading=13, textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=4,
    ))


def _h(text):
    return Paragraph(text, ParagraphStyle(
        "heading", fontSize=12, leading=15, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#16213e"), spaceBefore=12, spaceAfter=6,
    ))


def _table(rows, widths=None, header=True):
    t = Table(rows, colWidths=widths, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if not header:
        style.pop(0)
        style.pop(0)
    t.setStyle(TableStyle(style))
    return t


def generate_report(report_data, filename=None):
    """Generate the PDF and return the file path."""
    os.makedirs(Config.REPORT_DIR, exist_ok=True)
    if not filename:
        filename = f"system_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    path = os.path.join(Config.REPORT_DIR, filename)

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        rightMargin=0.75 * inch, leftMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    story = []

    # ---- Title ----
    story.append(Paragraph("SMART SYSTEM DOCTOR PRO", ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=20, alignment=TA_CENTER,
        textColor=colors.HexColor("#16213e"), spaceAfter=2,
    )))
    story.append(Paragraph("System Diagnostic Report", ParagraphStyle(
        "subtitle", fontSize=11, alignment=TA_CENTER,
        textColor=colors.HexColor("#555555"), spaceAfter=4,
    )))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ParagraphStyle("meta", fontSize=8, alignment=TA_CENTER,
                       textColor=colors.HexColor("#888888")),
    ))
    story.append(Spacer(1, 0.15 * inch))

    # ---- 1. Executive Summary ----
    story.append(_h("1. Executive Summary"))
    health = report_data.get("health") or {}
    security = report_data.get("security") or {}
    summary_lines = [
        f"Health score: {health.get('score', '-')}/100 "
        f"({health.get('status', 'Unknown')}).",
        f"Security posture: {security.get('score', '-')}/100 "
        f"({security.get('status', 'Unknown')}).",
        f"{report_data.get('suspicious_count', 0)} suspicious process finding(s) "
        f"and {len(report_data.get('ports', []))} listening port(s) observed.",
    ]
    for line in summary_lines:
        story.append(_p(f"- {line}"))

    # ---- 2. System Information ----
    story.append(_h("2. System Information"))
    os_info = report_data.get("os") or {}
    uptime = report_data.get("uptime") or {}
    story.append(_table([
        ["Attribute", "Value"],
        ["Operating system", f"{os_info.get('system', 'Unknown')} {os_info.get('release', '')}"],
        ["Platform", f"{os_info.get('machine', '')} ({os_info.get('version', '')})"],
        ["Hostname", os_info.get("hostname", "-")],
        ["Uptime", uptime.get("uptime_human", "-")],
        ["Boot time", uptime.get("boot_time_iso", "-")],
        ["CPU cores", f"{report_data.get('cpu_info', {}).get('count', '-')} "
                      f"(physical: {report_data.get('cpu_info', {}).get('physical_count', '-')})"],
        ["Processes", report_data.get("process_count", "-")],
    ]))

    # ---- 3. Performance Metrics ----
    story.append(_h("3. Performance Metrics"))
    mem = report_data.get("memory") or {}
    disk = report_data.get("disk") or {}
    story.append(_table([
        ["Metric", "Value"],
        ["CPU usage", f"{report_data.get('cpu', 0):.1f}%"],
        ["RAM usage", f"{report_data.get('ram', 0):.1f}% "
                      f"({mem.get('used_human', '')} of {mem.get('total_human', '')})"],
        ["Disk usage", f"{report_data.get('disk_percent', 0):.1f}% "
                       f"({disk.get('free_human', '')} free)"],
        ["Network received", report_data.get("network", {}).get("bytes_recv_human", "-")],
        ["Network sent", report_data.get("network", {}).get("bytes_sent_human", "-")],
    ]))

    # ---- 4. Health Analysis ----
    story.append(_h("4. Health Analysis"))
    if health.get("factors"):
        rows = [["Factor", "Impact", "Reason"]]
        for f in health["factors"]:
            rows.append([f["factor"], f"{f['impact']:+d}", f["reason"]])
        story.append(_table(rows))
    else:
        story.append(_p("No health factors available."))

    # ---- 5. Security Analysis ----
    story.append(_h("5. Security Analysis"))
    story.append(_p(
        "The security analysis is heuristic. Findings indicate behaviour worth "
        "reviewing and are NOT proof of malware."
    ))
    if security.get("reasons"):
        for r in security["reasons"]:
            story.append(_p(f"- {r}"))

    # ---- 6. Suspicious Processes ----
    story.append(_h("6. Suspicious Processes"))
    findings = report_data.get("findings") or []
    if findings:
        rows = [["PID", "Process", "Severity", "Score", "Strength"]]
        for f in findings[:15]:
            rows.append([
                f.get("pid", "-"), f.get("name", "-"), f.get("severity", "-"),
                f.get("score", "-"), f"{f.get('heuristic_strength', 0):.2f}",
            ])
        story.append(_table(rows))
        for f in findings[:8]:
            reasons = "; ".join(f.get("reasons", []))
            story.append(_p(f"<b>Why {f.get('name', 'process')} (PID {f.get('pid')}) "
                            f"was flagged:</b> {reasons}"))
            if f.get("recommendation"):
                story.append(_p(f"<b>Recommended action:</b> {f['recommendation']}"))
    else:
        story.append(_p("No suspicious processes flagged by heuristics."))

    # ---- 7. Network / Port Analysis ----
    story.append(_h("7. Network / Port Analysis"))
    ports = report_data.get("ports") or []
    if ports:
        rows = [["Port", "Proto", "Address", "PID", "Process", "Service", "Risk"]]
        for p in ports[:20]:
            rows.append([
                p.get("port", "-"), p.get("protocol", "-"), p.get("local_address", "-"),
                p.get("pid", "-"), p.get("process_name", "-"),
                p.get("service", "-"), p.get("risk_level", "-"),
            ])
        story.append(_table(rows, widths=[0.5 * inch, 0.5 * inch, 1.3 * inch,
                                          0.5 * inch, 1.2 * inch, 1.0 * inch,
                                          0.8 * inch]))
    else:
        story.append(_p("No listening ports observed."))

    # ---- 8. Historical Trends ----
    story.append(_h("8. Historical Trends"))
    history = report_data.get("history") or []
    if history:
        avg_cpu = sum(r.get("cpu") or 0 for r in history) / len(history)
        avg_ram = sum(r.get("ram") or 0 for r in history) / len(history)
        avg_health = sum(r.get("health") or 0 for r in history) / len(history)
        story.append(_table([
            ["Statistic", "Value"],
            ["Samples used", len(history)],
            ["Average CPU", f"{avg_cpu:.1f}%"],
            ["Average RAM", f"{avg_ram:.1f}%"],
            ["Average health", f"{avg_health:.1f}"],
        ]))
    else:
        story.append(_p("Insufficient historical data."))

    # ---- 9. Predictions ----
    story.append(_h("9. Trend-Based Predictions"))
    story.append(_p(
        "Predictions use linear-regression extrapolation over recent history. "
        "They are indicative, not guaranteed."
    ))
    predictions = report_data.get("predictions") or {}
    if predictions.get("available"):
        rows = [["Resource", "Current", "Trend", "Forecast", "Reliability", "Risk"]]
        for resource in ("cpu", "ram", "disk"):
            data = predictions.get(resource)
            if not data:
                continue
            rows.append([
                resource.upper(), f"{data.get('current', 0):.1f}%",
                data.get("trend", "-"),
                f"{data.get('range_low', 0)}-{data.get('range_high', 0)}%",
                f"{data.get('reliability', 0) * 100:.0f}%",
                data.get("risk", "-"),
            ])
        story.append(_table(rows))
        low_reliability = [data for resource in ("cpu", "ram", "disk")
                           if (data := predictions.get(resource))
                           and data.get("reliability_note")]
        for data in low_reliability:
            story.append(_p(f"<b>Note:</b> {data['reliability_note']}"))
    else:
        story.append(_p("Not enough historical data for a forecast yet."))

    # ---- 10. Recommendations ----
    story.append(_h("10. Recommendations"))
    recommendations = report_data.get("recommendations") or []
    for rec in recommendations:
        story.append(_p(
            f"<b>[{rec.get('severity', 'Info')}] {rec.get('title', '')}</b> "
            f"{rec.get('description', '')} Action: {rec.get('action', '')}"
        ))

    # ---- 11. Limitations ----
    story.append(_h("11. Limitations"))
    for line in [
        "The security engine uses heuristic rules and can produce false "
        "positives; it is not a substitute for enterprise antivirus or EDR software.",
        "Predictive analysis is trend-based forecasting of historical data and "
        "is not a guarantee of future system state.",
        "Metrics are sampled locally; results reflect the state of this machine "
        "at the time of generation.",
    ]:
        story.append(_p(f"- {line}"))

    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        "Generated by Smart System Doctor Pro v4.0",
        ParagraphStyle("footer", fontSize=8, alignment=TA_CENTER,
                       textColor=colors.HexColor("#888888")),
    ))

    try:
        doc.build(story)
        logger.info("Report generated: %s", path)
        return path
    except Exception:
        logger.error("Failed to build PDF report", exc_info=True)
        raise
