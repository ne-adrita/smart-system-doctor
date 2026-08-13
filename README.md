# Smart System Doctor Pro

**Smart System Doctor Pro** is a local OS diagnostic and system-health monitoring application designed to analyze CPU, memory, disk, processes, network activity, and historical system behavior. It combines rule-based system health scoring, heuristic security analysis, process monitoring, port analysis, recommendations, and short-term trend-based predictive analysis to help users identify performance and potential security issues — all running locally on your own machine.

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
- **Heuristic Security Analysis** — two-stage scan covering *all* processes: a cheap prefilter selects suspicious candidates, then transparent suspicion scoring with severity, heuristic strength, reasons, evidence, and a recommended action.
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
    ├── test_api.py
    ├── test_database.py
    ├── test_health.py
    ├── test_prediction.py
    ├── test_process_control.py
    ├── test_process_monitor.py
    ├── test_pruning.py
    └── test_security.py
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

**Parameter validation:** query parameters are validated and bounded — `limit` on `/api/processes` is 1–1000, `limit` on `/api/history` is 1–1000, and `hours` is 1–168. Out-of-range or non-integer values return `400 INVALID_PARAMETER` instead of an unbounded query.

---

## Health Scoring

Transparent rule-based scoring. Every factor returns its impact and reason:

```json
{
  "score": 72,
  "status": "Fair",
  "factors": [
    { "factor": "RAM", "impact": -15, "reason": "RAM usage is at 82.0% (above the 60% threshold - reduced by 15 points)" }
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

Penalties are **gradual**, not step-like: usage is compared against a low threshold and the penalty grows continuously (capped), so a reading of 79.9% and 80.1% do not produce wildly different scores. Defaults: CPU/RAM penalty above 60% up to 40 points, disk above 70% up to 30 points, and process count above 500 up to 10 points (all configurable via `HEALTH_*` environment variables).

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

The scan is a two-stage pipeline so that no suspicious process is missed:

1. **Cheap prefilter over every running process** — flags candidates by suspicious filename keyword, suspicious executable path, very high CPU/RAM, an orphaned parent, or established outbound connections. This is deliberately cheap (no per-process introspection).
2. **Detailed scoring for the candidate subset** — gathers executable, username and connection evidence only for candidates, then combines the weighted signals above.

Every finding explains *why* it was flagged and carries a **heuristic strength** value (0–0.9) — the normalized strength of the heuristic evidence, **not** a probability of malware — plus raw evidence and a recommended action:

```json
{
  "pid": 1234,
  "name": "example",
  "severity": "Moderate",
  "heuristic_strength": 0.48,
  "reasons": ["Executable located in a temporary or user-writable directory: /tmp/foo"],
  "evidence": { "name": "example", "exe": "/tmp/foo", "cpu": 2.1 },
  "recommendation": "Inspect process 'example' (PID 1234). Confirm the executable location is legitimate."
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
    "reliability": 0.87,
    "reliability_note": null,
    "risk": "Moderate",
    "model": "linear regression (least squares) over recent history"
  }
}
```

The forecast is a statistical extrapolation with a plausible band from residual spread — indicative, not guaranteed. Each forecast also reports its **reliability** (the R² of the linear fit): when recent data is highly variable and fits a straight line poorly, the reliability drops below 0.3, a note is shown, and the forecast should not be treated as trustworthy.

---

## Database

SQLite with tables: `system_metrics`, `process_snapshots`, `security_events`, `port_events`, `recommendations`. Indexes on timestamps, WAL mode, and automatic pruning after `HISTORY_RETENTION_DAYS` keep growth bounded. Logging runs on `HISTORY_INTERVAL` (default 10 s), not on every dashboard poll.

---

## Real-Time Monitoring

The dashboard is **genuinely dynamic**: it updates live without requiring a full browser page reload. It uses REST API polling (not WebSockets) driven by a central refresh manager in `static/js/script.js`, with differentiated refresh intervals matched to the cost and importance of each operation:

| Section            | Refresh interval |
| ------------------ | ---------------- |
| System metrics     | ~2 s             |
| Health             | ~3 s             |
| Processes          | ~5 s             |
| History            | ~10 s            |
| Security           | ~20 s            |
| Ports              | ~20 s            |
| Recommendations    | ~20 s            |
| Predictions        | ~30 s            |

Implementation notes:

- Each section polls on its own timer with **overlap protection** (a tick is skipped if the previous request for that section is still in flight).
- When the browser tab is hidden, expensive polling stops; it **resumes and refreshes immediately** when the user returns.
- A connection indicator shows **LIVE**, **RECONNECTING…**, or **OFFLINE** based on actual API responses.
- Every section shows a **Last updated** timestamp, and data is flagged as **possibly stale** if the backend stops responding.
- Live charts are built from **one coherent snapshot per update cycle** — a single point is pushed per system poll, so timestamps stay synchronized across all chart series.
- Fast metrics, process monitoring, health, security, ports, history, predictions, and recommendations all update in place — no page reload required.

---

## Testing

```bash
python -m pytest tests/ -q
```

Covers health scoring, security heuristics, predictions/regression, process monitoring and control (fields, sorting, memory, real CPU, details, termination), API endpoints (including parameter validation, invalid and protected PIDs), and database behaviour (table creation, insert/retrieve, retention, pruning).

---

## Limitations

1. Security analysis is heuristic and is **not** a replacement for antivirus or EDR software.
2. Suspicious-process detection may produce **false positives**.
3. Predictive analysis uses short-term statistical trends and does **not** guarantee future system behavior.
4. Some process and network information depends on operating-system permissions.
5. The application is designed primarily as a **local diagnostic tool**.

---

## Major Improvements and Fixes

This section documents the significant changes made during development, from the original prototype to the final submission-ready version.

### Original Problems → Final Improvements

1. **Monolithic backend.** Too much monitoring and business logic was concentrated in `app.py`. → Introduced a service-based architecture: `system_monitor`, `process_monitor`, `security_analyzer`, `health_analyzer`, `prediction_service`, `recommendation_service`, `report_service`.

2. **Heavy `/data` endpoint.** Monitoring, security scanning, port scanning, database logging and diagnostics were performed together on every request. → Introduced a background worker with **separate intervals** for expensive operations, keeping fast metrics responsive.

3. **Background worker pruning bug.** History pruning reused the moderate-metrics timer, so it effectively never ran. → Created a **dedicated pruning timer** (`last_prune`) independent of `last_moderate`, `last_history`, `last_security` and `last_ports`, with a regression test.

4. **Weak security detection.** Analysis relied too heavily on process-name checks and resource rankings. → Implemented **multi-signal heuristic analysis** using process name, executable path, CPU, RAM, network connections, parent process and privilege information.

5. **Limited process coverage.** Suspicious low-resource processes could be missed. → Implemented a two-stage pipeline: **all processes → lightweight prefilter → suspicious candidates → detailed analysis**.

6. **Misleading malware terminology.** Simple heuristics could not justify claims of malware detection. → Replaced with accurate wording: **Heuristic Security Analysis**, **Suspicious Process**, **Potential Security Risk**, **Heuristic Warning**.

7. **Misleading confidence score.** A raw score divided by 100 was presented as confidence. → Replaced with **heuristic strength** — clearly documented as normalized heuristic evidence strength (capped at 0.9), not a probability.

8. **Oversimplified prediction.** Forecasts were based on simplistic calculations. → Implemented **linear regression** with slope, **R²** reliability, residual analysis, forecast range and risk level.

9. **Misleading AI claim.** Simple statistical forecasting could be misrepresented as AI. → Clearly described as **Short-Term Trend-Based Predictive Analysis**.

10. **Abrupt health-score thresholds.** A small metric change could produce a very large penalty. → Replaced step thresholds with **gradual penalty** calculations.

11. **Fake network health factor.** Network appeared as a health factor without meaningful analysis. → **Removed** the placeholder factor (network is genuinely analyzed only in security/port analysis).

12. **Unsafe process termination.** Termination lacked safeguards. → Added PID validation, protected-process list, graceful-terminate-first flow, force kill as an explicit second-level action, `AccessDenied`/`NoSuchProcess` handling and a confirmation UI.

13. **Unsafe Flask configuration.** The app could run with `debug=True` on `0.0.0.0`. → Safe defaults: **`127.0.0.1`**, **`debug=False`**.

14. **Poor API error handling.** Responses were inconsistent. → Introduced a standardized JSON response envelope (`success` / `data` / `error` / `timestamp`) and consistent error codes.

15. **Broad exception handling.** Generic `except: pass` could hide real errors. → Replaced with specific exception handling and structured logging.

16. **Weak port analysis.** An open port could be misinterpreted as automatically dangerous. → Port analysis now considers port, service, listening address, exposure (loopback vs all interfaces) and risk.

17. **Runtime database dependency.** The project could depend on a pre-existing SQLite database. → Database initialization **auto-creates** all tables on first run.

18. **Lack of historical analytics.** The dashboard relied on temporary frontend data. → Historical metrics are persisted in SQLite and used for history, statistics, trend analysis and prediction.

19. **No proper testing structure.** Important logic was insufficiently tested. → Added tests for health, security, prediction, process control, API (including parameter validation) and database (including pruning).

20. **Poor project packaging.** Development files could be included in submissions. → Added `.gitignore` and prepared a **clean final submission package** (no `.venv`, `.git`, database, logs, reports, caches or OS metadata in the delivered ZIP).

---

## Future Improvements

- Optional pluggable threat-intelligence feed for known hashes/IOCs.
- Per-process history and CPU/RAM profiles over time.
- Alert notifications (desktop/email) on threshold breaches.
- Configurable user-defined suspicion rules.
- Export to CSV/JSON for external tooling.
- Network traffic-rate monitoring (per-interface deltas).
