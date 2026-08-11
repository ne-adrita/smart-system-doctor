# Smart System Doctor Pro

A local OS system monitoring, diagnostic, performance analysis, and **heuristic cybersecurity health-checking** application. It continuously analyzes system resources, processes, listening services, network activity, and historical performance data to identify potential problems and provide actionable recommendations — all running locally on your own machine.

> **Security engine disclaimer:** The security analysis is *heuristic* (behavior- and signature-hint-based) and **is not** a malware scanner, antivirus, or a replacement for enterprise antivirus/EDR software. Findings indicate behaviour worth reviewing and may include **false positives**.

> **Prediction disclaimer:** Predictive analysis is **trend-based forecasting** of recorded history and **should not be interpreted as a guaranteed prediction** of future system state.

---

## Overview

Smart System Doctor Pro answers six questions at a glance:

1. Is my computer healthy?
2. What is using the most CPU?
3. What is using the most RAM?
4. Is anything suspicious?
5. What should I do?
6. Is the system getting better or worse?

It provides a professional dark dashboard, live charts, transparent health/security scoring, safe process management, open-port analysis, trend forecasts, historical statistics, and a structured PDF diagnostic report.

---

## Features

- **System monitoring** — CPU, RAM, swap, disk, disk I/O, network, process count, uptime, boot time, OS details.
- **Process monitoring** — sortable list (CPU/RAM/PID/name), on-demand process details (PID, exe, username, parent, threads, connections, open files).
- **Safe process termination** — protected-process list, graceful-terminate-first flow, explicit confirmation, force-kill only as a second-level action.
- **System Health Score** — transparent rule-based 0–100 score with per-factor impact and reasons.
- **Heuristic Security Analysis** — suspicion scoring with severity, confidence, reasons, and evidence for every flagged process.
- **Open Port Analysis** — distinguishes loopback-only listeners from externally exposed services, with known-service labelling.
- **Trend-Based Predictive Analysis** — linear-regression forecasts of CPU, RAM and disk from SQLite history.
- **Recommendation engine** — rule-based, actionable suggestions with severity levels.
- **Historical logging** — SQLite persistence with configurable intervals, indexes, WAL, and retention pruning.
- **Charts** — CPU, RAM, health and security over Live / 1 Hour / 6 Hours / 24 Hours.
- **PDF diagnostic report** — structured multi-section professional report.
- **Application garbage collection** — honest Python GC (does **not** claim to free OS RAM).

---

## Architecture

```
Flask API
    ↓
Service Layer
    ↓
System / Process / Security / Analytics
    ↓
Database (SQLite)
```

- `app.py` — thin Flask layer: REST endpoints, JSON envelope, background-worker scheduling.
- `services/` — all business logic (system, process, security, health, prediction, recommendations, reports).
- `models/schemas.py` — shared response shapes.
- `utils/` — logging, process helpers, formatting helpers.
- `database.py` — SQLite schema, queries, pruning.
- `config.py` — environment-based configuration.

Expensive work (security scans, port scans, history writes) runs in a **background worker** on separate intervals, so fast metrics stay responsive.

## Technologies

- Python 3.10+ (tested on 3.14)
- Flask
- psutil
- SQLite (standard library `sqlite3`)
- Chart.js (vendored locally, no CDN dependency)
- ReportLab

## Project Structure

```text
smart-system-doctor/
│
├── app.py                  # Flask application + background worker
├── config.py               # environment-based configuration
├── database.py             # SQLite schema, queries, pruning
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
│
├── services/
│   ├── system_monitor.py       # centralized psutil system metrics
│   ├── process_monitor.py      # cheap process lists + on-demand details
│   ├── security_analyzer.py    # heuristic suspicion scoring + port analysis
│   ├── health_analyzer.py      # transparent health scoring
│   ├── prediction_service.py   # trend-based (linear regression) forecasts
│   ├── recommendation_service.py
│   └── report_service.py       # PDF generation (ReportLab)
│
├── models/
│   └── schemas.py
│
├── utils/
│   ├── process_utils.py        # validation, protection, safe termination
│   ├── system_utils.py         # formatting helpers
│   └── logging_utils.py        # rotating file logger
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/style.css
│   └── js/
│       ├── script.js
│       └── vendor/chart.umd.js
│
└── tests/
    ├── test_health.py
    ├── test_security.py
    ├── test_prediction.py
    └── test_api.py
```

---

## Installation

```bash
git clone <repository-url>
cd smart-system-doctor
```

## Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

## Dependencies

```bash
pip install -r requirements.txt
```

Optionally copy the example configuration:

```bash
cp .env.example .env
```

## Running the Application

```bash
python app.py
```

Open <http://127.0.0.1:5001> in your browser.

Default settings bind to **127.0.0.1 only** and **debug mode is off**. To override:

```bash
FLASK_HOST=0.0.0.0 FLASK_PORT=9000 python app.py   # explicit override only
```

All configuration can be set in a `.env` file (see `.env.example`).

---

## API Endpoints

All endpoints return a consistent envelope:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "timestamp": "..."
}
```

On failure:

```json
{
  "success": false,
  "data": null,
  "error": { "code": "PROCESS_NOT_FOUND", "message": "The process no longer exists." },
  "timestamp": "..."
}
```

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/system` | Fast CPU/RAM + cached disk, network, uptime, OS |
| GET | `/api/health` | Health score with factors and reasons |
| GET | `/api/security` | Security score, findings, ports, scan time |
| GET | `/api/processes` | Process list (`sort_by`, `order`, `limit`, `filter`) |
| GET | `/api/processes/<pid>` | Detailed process information |
| POST | `/api/processes/<pid>/terminate` | Graceful termination (protected check) |
| POST | `/api/processes/<pid>/kill` | Force kill (second-level action) |
| GET | `/api/ports` | Open TCP listeners with exposure + risk |
| GET | `/api/history` | Historical metrics (`hours`, `limit`) |
| GET | `/api/statistics` | Aggregate statistics |
| GET | `/api/predictions` | Trend-based forecasts |
| GET | `/api/recommendations` | Rule-based recommendations |
| GET | `/api/events` | Recent persisted security events / recommendations |
| POST | `/api/reports/pdf` | Generate and download the PDF report |
| POST | `/api/maintenance/gc` | Run application garbage collection |

Legacy aliases (`/history`, `/statistics`, `/system-info`, `/process/<pid>`) are kept for compatibility.

---

## Health Scoring

Transparent rule-based scoring. Every factor returns its impact and reason:

```json
{
  "score": 72,
  "status": "Fair",
  "factors": [
    { "factor": "RAM", "impact": -15, "reason": "RAM usage is at 82.0% (above 80%)" }
  ]
}
```

| Band | Status |
|------|--------|
| 90–100 | Excellent |
| 75–89 | Good |
| 60–74 | Fair |
| 40–59 | Poor |
| 0–39 | Critical |

Penalties (configurable): CPU ≥ 80% → −30, ≥ 60% → −12; RAM same; disk ≥ 85% → −20, ≥ 70% → −10; process count > 500 → −10.

---

## Security Analysis

**Heuristic Suspicious Process and Security Analysis.** The engine combines multiple weak signals into a suspicion score:

| Signal | Weight |
|--------|--------|
| Suspicious filename keyword | +15 |
| Suspicious executable path (temp/user-writable dirs) | +20 |
| Unexpected outbound network activity | +20 |
| High CPU (≥ 70%) | +10 |
| High memory (≥ 50%) | +10 |
| Unusual parent process | +15 |
| Privileged process anomaly | +10 |

Classification: **0–19 Low**, **20–39 Moderate**, **40–59 High**, **60+ Critical**.

Every finding explains *why* it was flagged and carries a confidence value (capped at 0.9) and raw evidence:

```json
{
  "pid": 1234,
  "name": "example",
  "severity": "Moderate",
  "confidence": 0.48,
  "reasons": ["Executable located in a temporary or user-writable directory: /tmp/foo"],
  "evidence": { "name": "example", "exe": "/tmp/foo", "cpu": 2.1 }
}
```

The engine acknowledges false positives and never claims certainty. **It is not a malware scanner.**

### Open Port Analysis

Uses OS-level TCP listener information (falls back to a loopback connect test if the OS denies introspection). Loopback listeners (`127.0.0.1`) are low-risk; services listening on all interfaces (`0.0.0.0`/`::`) carry a higher risk. Known services (SSH, HTTP, MySQL, PostgreSQL, …) are labelled via a configurable database and are **not** automatically treated as malicious.

---

## Predictive Analysis

Trend-based forecasting from SQLite history:

```
Historical measurements → data cleaning → linear regression → trend → short-term forecast
```

```json
{
  "cpu": {
    "current": 72.0,
    "trend": "increasing",
    "forecast": 80.5,
    "range_low": 76.2,
    "range_high": 84.8,
    "risk": "Moderate",
    "model": "linear regression (least squares) over recent history"
  }
}
```

The forecast is a statistical extrapolation with a plausible band from residual spread — indicative, not guaranteed.

---

## Database

SQLite with tables: `system_metrics`, `process_snapshots`, `security_events`, `port_events`, `recommendations`. Indexes on timestamps, WAL mode, and automatic pruning after `HISTORY_RETENTION_DAYS` keep growth bounded. Logging runs on `HISTORY_INTERVAL` (default 10 s), not on every dashboard poll.

---

## Screenshots

*(Add screenshots here)*

---

## Testing

```bash
python -m pytest tests/ -q
```

Covers health scoring, security heuristics, predictions/regression, and API endpoints (including invalid and protected PIDs).

---

## Limitations

- The security engine is **heuristic** and can produce **false positives**; it is not a substitute for enterprise antivirus/EDR software.
- Predictive analysis is **trend-based forecasting** and not a guarantee of future behaviour.
- Port analysis depends on OS permissions; on platforms that restrict connection introspection, it falls back to a loopback-only check of well-known ports.
- Process inspection can be restricted by OS privileges (some system processes refuse `AccessDenied` on metadata).
- This is a local diagnostic tool; it is not designed for distributed or production network deployment.

---

## Future Improvements

- Optional pluggable threat-intelligence feed for known hashes/IOCs.
- Per-process history and CPU/RAM profiles over time.
- Alert notifications (desktop/email) on threshold breaches.
- Configurable user-defined suspicion rules.
- Export to CSV/JSON for external tooling.
- Network traffic-rate monitoring (per-interface deltas).
