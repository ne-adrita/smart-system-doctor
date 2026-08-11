/* =====================================================================
   Smart System Doctor Pro - dashboard controller
   =====================================================================
   Real-time architecture:
     - Central refresh manager registers sections with per-section
       intervals (no scattered setInterval calls).
     - Overlap guard prevents a new request while the previous one for
       the same section is still in flight.
     - Visibility optimization pauses expensive polling when the tab is
       hidden and refreshes immediately on return.
     - LIVE / RECONNECTING / OFFLINE connection states + per-section
       "last updated" and stale-data indicators.
   ===================================================================== */
"use strict";

const API = {
    system: "/api/system",
    health: "/api/health",
    security: "/api/security",
    processes: "/api/processes",
    history: "/api/history",
    statistics: "/api/statistics",
    predictions: "/api/predictions",
    recommendations: "/api/recommendations",
    ports: "/api/ports",
    report: "/api/reports/pdf",
    gc: "/api/maintenance/gc",
};

/* Per-section polling intervals (ms). Security/ports stay slow because
   they are the expensive scans. */
const REFRESH_INTERVALS = {
    system: 2000,
    health: 3000,
    processes: 5000,
    security: 20000,
    ports: 20000,
    history: 10000,
    predictions: 30000,
    recommendations: 20000,
};

/* How many consecutive failures before the connection is marked OFFLINE. */
const OFFLINE_AFTER_FAILURES = 3;
/* A section is flagged "stale" when older than this multiple of its interval. */
const STALE_MULTIPLIER = 3;
/* Max points kept per live chart (bounds browser memory/CPU growth). */
const MAX_LIVE_POINTS = 60;

const state = {
    cpu: 0,
    ram: 0,
    disk: 0,
    health: { score: 0, status: "Unknown", color: "#667eea", factors: [], issues: [] },
    security: { score: 100, status: "Safe", color: "#2ecc71", findings: [], ports: [], reasons: [], last_scan: null },
    ports: [],
    processes: [],
    live: { labels: [], cpu: [], ram: [], disk: [], health: [], security: [], processes: [] },
    range: "live",
    lastSnapshot: null,
    predictions: null,
    recommendations: [],
    lastUpdate: {},     // section -> timestamp of last successful update
    failures: 0,        // consecutive API failures
    visible: true,
};

/* ---------------- Central refresh manager ---------------- */
const refreshManager = {
    timers: {},
    inFlight: {},

    start(name, callback, interval) {
        this.stop(name);
        // Run immediately so the page shows data without waiting for the
        // first timer tick, then poll on the section interval.
        this.timers[name] = setInterval(() => this.tick(name, callback), interval);
        this.tick(name, callback);
    },

    stop(name) {
        if (this.timers[name]) {
            clearInterval(this.timers[name]);
            delete this.timers[name];
        }
        delete this.inFlight[name];
    },

    stopAll() {
        Object.keys(this.timers).forEach(name => this.stop(name));
    },

    /* Overlap guard: skip a tick if the previous request is still running.
       Also skip entirely when the tab is hidden (visibility optimization). */
    tick(name, callback) {
        if (!state.visible) return;
        if (this.inFlight[name]) return;
        this.inFlight[name] = true;
        Promise.resolve()
            .then(callback)
            .catch(err => {
                console.error(`[${name}] poll failed:`, err);
                registerFailure();
            })
            .finally(() => {
                this.inFlight[name] = false;
            });
    },

    /* Effective interval currently used for a section (respects visibility). */
    currentInterval(name) {
        return REFRESH_INTERVALS[name];
    },
};

/* ---------------- API helper ---------------- */
async function apiRequest(url, options) {
    const response = await fetch(url, options);
    const result = await response.json();
    if (!response.ok || !result.success) {
        const message = (result.error && result.error.message) || `HTTP ${response.status}`;
        const err = new Error(message);
        err.code = result.error && result.error.code;
        throw err;
    }
    return result.data;
}

/* ---------------- Connection state ---------------- */
function setConnection(mode) {
    const el = document.getElementById("connectionState");
    if (!el) return;
    if (mode === "live") {
        el.className = "pill pill-good";
        el.textContent = "● LIVE";
    } else if (mode === "reconnecting") {
        el.className = "pill pill-warn";
        el.textContent = "● RECONNECTING…";
    } else {
        el.className = "pill pill-bad";
        el.textContent = "● OFFLINE";
    }
}

function registerSuccess() {
    state.failures = 0;
    setConnection("live");
}

function registerFailure() {
    state.failures += 1;
    if (state.failures >= OFFLINE_AFTER_FAILURES) {
        setConnection("offline");
    } else {
        setConnection("reconnecting");
    }
}

function markUpdated(section) {
    state.lastUpdate[section] = Date.now();
    registerSuccess();
    renderUpdatedStamp(section);
}

/* ---------------- Last-updated + stale indicators ---------------- */
function renderUpdatedStamp(section) {
    const ts = state.lastUpdate[section];
    const text = ts ? "Updated " + relativeTime(ts) : "Waiting for data…";
    const ids = ["updated-" + section];
    if (section === "processes") ids.push("updated-processes-tab");
    for (const id of ids) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    }
}

function relativeTime(ts) {
    const secs = Math.max(0, Math.round((Date.now() - ts) / 1000));
    if (secs < 2) return "just now";
    if (secs < 60) return `${secs} second${secs === 1 ? "" : "s"} ago`;
    const mins = Math.round(secs / 60);
    return `${mins} minute${mins === 1 ? "" : "s"} ago`;
}

function updateStaleFlags() {
    for (const [section, interval] of Object.entries(REFRESH_INTERVALS)) {
        const ts = state.lastUpdate[section];
        const stale = ts && (Date.now() - ts) > interval * STALE_MULTIPLIER;
        const flagText = stale ? "⚠ data may be stale" : "";
        const flagClass = stale ? "stale-flag warn" : "stale-flag";
        const ids = ["stale-" + section];
        if (section === "processes") ids.push("stale-processes-tab");
        for (const id of ids) {
            const el = document.getElementById(id);
            if (el) { el.textContent = flagText; el.className = flagClass; }
        }
    }
}

/* ---------------- Chart setup ---------------- */
const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 0 },
    plugins: { legend: { display: false } },
    scales: {
        y: {
            min: 0, max: 100,
            grid: { color: "rgba(255,255,255,0.06)" },
            ticks: { color: "#8b95ab", font: { size: 10 } },
        },
        x: {
            grid: { display: false },
            ticks: { color: "#8b95ab", font: { size: 10 }, maxTicksLimit: 8 },
        },
    },
};

function makeChart(ctx, color, fill = true) {
    return new Chart(ctx, {
        type: "line",
        data: {
            labels: [],
            datasets: [{
                label: "",
                data: [],
                borderColor: color,
                backgroundColor: fill ? color + "22" : "transparent",
                borderWidth: 2,
                fill,
                tension: 0.35,
                pointRadius: 0,
            }],
        },
        options: chartOpts,
    });
}

const charts = {
    cpu: makeChart(document.getElementById("chartCpu"), "#ff4757"),
    ram: makeChart(document.getElementById("chartRam"), "#3498db"),
    disk: makeChart(document.getElementById("chartDisk"), "#e67e22"),
    health: makeChart(document.getElementById("chartHealth"), "#667eea"),
    security: makeChart(document.getElementById("chartSecurity"), "#2ecc71"),
    processes: makeChart(document.getElementById("chartProcesses"), "#a55eea"),
};

/* Live update only - never recreates the chart. */
function setChartData(chart, labels, values) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update("none");
}

/* ---------------- Section: system metrics ---------------- */
async function fetchSystemMetrics() {
    const system = await apiRequest(API.system);
    state.cpu = system.cpu;
    state.ram = system.memory ? system.memory.percent : system.ram;
    state.disk = system.disk_percent;
    state.lastSnapshot = system;
    markUpdated("system");
    renderTiles();
    renderAlert();
    renderSnapshot(system);
    updateHeaderTimestamp();
    updateLiveSnapshot();
}

function updateHeaderTimestamp() {
    const el = document.getElementById("lastUpdated");
    if (el) el.textContent = "Last updated: " + new Date().toLocaleTimeString();
}

/* ---------------- Section: health ---------------- */
async function fetchHealth() {
    const health = await apiRequest(API.health);
    state.health = health;
    markUpdated("health");
    renderTiles();
    renderAlert();
    renderHealthFactors(health.factors, health.issues);
}

/* ---------------- Section: processes ---------------- */
async function fetchProcesses() {
    const data = await apiRequest(`${API.processes}?limit=200&sort_by=cpu`);
    state.processes = data.processes;
    markUpdated("processes");
    renderProcessTable();
    renderTopProcesses();
}

function renderProcessTable() {
    const el = document.getElementById("processTable");
    if (!el) return;
    const sort = document.getElementById("procSort").value;
    const filter = document.getElementById("procFilter").value.trim().toLowerCase();
    let rows = state.processes;
    if (filter) rows = rows.filter(p => (p.name || "").toLowerCase().includes(filter));
    rows = rows.slice().sort((a, b) => {
        const av = a[sort] ?? 0, bv = b[sort] ?? 0;
        if (sort === "name") return String(av).localeCompare(String(bv));
        return bv - av;
    });
    if (!rows.length) { el.innerHTML = "<tr><td colspan='8' class='muted'>No matching processes.</td></tr>"; return; }
    el.innerHTML = rows.map(p => {
        const cpuColor = p.cpu_percent > 70 ? "badge-red" : p.cpu_percent > 40 ? "badge-orange" : "badge-gray";
        const memColor = p.memory_percent > 50 ? "badge-red" : p.memory_percent > 25 ? "badge-orange" : "badge-gray";
        return `<tr>
            <td>${p.pid}</td>
            <td>${esc(p.name || "-")}</td>
            <td><span class="badge ${cpuColor}">${(p.cpu_percent || 0).toFixed(1)}</span></td>
            <td><span class="badge ${memColor}">${(p.memory_percent || 0).toFixed(1)}</span></td>
            <td>${esc(p.memory_rss_human || "-")}</td>
            <td>${esc(p.status || "-")}</td>
            <td>${esc(p.username || "-")}</td>
            <td>
                <button class="btn btn-sm" onclick="showProcessDetails(${p.pid})">Details</button>
                <button class="btn btn-sm btn-danger" onclick="requestTerminate(${p.pid})">Terminate</button>
            </td>
        </tr>`;
    }).join("");
}

function renderTopProcesses() {
    const el = document.getElementById("topProcesses");
    if (!el) return;
    const rows = state.processes.slice().sort((a, b) => (b.cpu_percent || 0) - (a.cpu_percent || 0)).slice(0, 8);
    if (!rows.length) { el.innerHTML = "<tr><td colspan='6' class='muted'>No processes.</td></tr>"; return; }
    el.innerHTML = rows.map(p => `
        <tr>
            <td>${p.pid}</td>
            <td>${esc(p.name || "-")}</td>
            <td>${(p.cpu_percent || 0).toFixed(1)}</td>
            <td>${(p.memory_percent || 0).toFixed(1)}</td>
            <td>${esc(p.status || "-")}</td>
            <td><button class="btn btn-sm" onclick="showProcessDetails(${p.pid})">Details</button></td>
        </tr>`).join("");
}

/* ---------------- Section: security ---------------- */
async function fetchSecurity() {
    const data = await apiRequest(API.security);
    state.security = data;
    markUpdated("security");
    renderTiles();
    renderAlert();
    renderSecurity(data);
}

/* ---------------- Section: ports ---------------- */
async function fetchPorts() {
    const data = await apiRequest(API.ports);
    state.security.ports = data.ports;
    state.ports = data.ports;
    markUpdated("ports");
    renderPorts(data.ports);
}

/* ---------------- Section: history charts ---------------- */
async function fetchHistory() {
    if (state.range === "live") return; // live points are pushed per-tick
    const hours = { "1h": 1, "6h": 6, "24h": 24 }[state.range] || 1;
    const data = await apiRequest(`${API.history}?hours=${hours}&limit=120`);
    const rows = data.history;
    markUpdated("history");
    const labels = rows.map(r => r.time ? r.time.slice(11, 19) : "");
    setChartData(charts.cpu, labels, rows.map(r => r.cpu));
    setChartData(charts.ram, labels, rows.map(r => r.ram));
    setChartData(charts.disk, labels, rows.map(r => r.disk));
    setChartData(charts.health, labels, rows.map(r => r.health));
    setChartData(charts.security, labels, rows.map(r => r.security));
    setChartData(charts.processes, labels, rows.map(r => r.processes));
}

/* ---------------- Section: predictions ---------------- */
async function fetchPredictions() {
    const preds = await apiRequest(`${API.predictions}?hours=24`);
    state.predictions = preds;
    markUpdated("predictions");
    renderPredictions(preds);
}

/* ---------------- Section: recommendations ---------------- */
async function fetchRecommendations() {
    const data = await apiRequest(API.recommendations);
    state.recommendations = data.recommendations || [];
    markUpdated("recommendations");
    renderRecommendations(state.recommendations);
}

/* ---------------- Tiles & alert ---------------- */
function renderTiles() {
    const hasSystem = state.lastUpdate.system && state.lastUpdate.health;
    setTile("cpu", hasSystem ? `${state.cpu.toFixed(0)}%` : "--%", pctColor(state.cpu));
    setTile("ram", hasSystem ? `${state.ram.toFixed(0)}%` : "--%", pctColor(state.ram));
    setTile("disk", hasSystem ? `${state.disk.toFixed(0)}%` : "--%", pctColor(state.disk));
    setBar("cpu", state.cpu);
    setBar("ram", state.ram);
    setBar("disk", state.disk);
    setTile("health", hasSystem ? `${state.health.score}/100` : "--", state.health.color || "#667eea");
    setTileSub("health", hasSystem ? (state.health.status || "-") : "-");
    const hasSecurity = state.lastUpdate.security;
    setTile("security", hasSecurity ? `${state.security.score}/100` : "--", state.security.color || "#2ecc71");
    setTileSub("security", hasSecurity ? (state.security.status || "-") : "-");
}

function setTile(key, value, color) {
    const el = document.getElementById("tile-" + key);
    if (el) { el.textContent = value; el.style.color = color; }
}
function setTileSub(key, value) {
    const el = document.getElementById("tile-" + key + "-status");
    if (el) el.textContent = value;
}
function setBar(key, value) {
    const bar = document.getElementById("bar-" + key);
    if (bar) { bar.style.width = value + "%"; bar.style.background = pctColor(value); }
}
function pctColor(v) {
    if (v >= 85) return "#e74c3c";
    if (v >= 70) return "#e67e22";
    if (v >= 50) return "#f1c40f";
    return "#2ecc71";
}

function renderAlert() {
    const banner = document.getElementById("alertBanner");
    const healthScore = state.health.score || 0;
    const securityScore = state.security.score || 100;
    let cls = "alert-good";
    let msg = "All systems nominal.";

    if (state.cpu > 85 && state.ram > 85) {
        cls = "alert-bad";
        msg = "CRITICAL: CPU and RAM saturation detected.";
    } else if (securityScore < 50) {
        cls = "alert-bad";
        msg = "Security posture degraded - review the findings in the Security tab.";
    } else if (healthScore <= 39) {
        cls = "alert-bad";
        msg = "System health is critical - action recommended.";
    } else if (state.cpu > 80 || state.ram > 80) {
        cls = "alert-warn";
        msg = "High resource usage detected.";
    } else if (securityScore < 80) {
        cls = "alert-warn";
        msg = "Minor security findings to review.";
    } else if (healthScore <= 74) {
        cls = "alert-warn";
        msg = "System health is fair - monitor resource usage.";
    }

    banner.className = "alert " + cls;
    banner.innerHTML = `<span>${msg}</span>`;
}

/* ---------------- Snapshot ---------------- */
function renderSnapshot(system) {
    const el = document.getElementById("systemSnapshot");
    if (!el) return;
    const mem = system.memory || {};
    const disk = system.disk || {};
    const uptime = system.uptime || {};
    const os = system.os || {};
    const net = system.network || {};
    const rows = [
        ["Operating System", `${os.system || "-"} ${os.release || ""}`],
        ["Hostname", os.hostname || "-"],
        ["Uptime", uptime.uptime_human || "-"],
        ["Boot time", uptime.boot_time_iso || "-"],
        ["CPU cores", `${system.cpu_info.count || "-"} (${system.cpu_info.physical_count || "-"} physical)`],
        ["RAM", `${mem.used_human || "-"} / ${mem.total_human || "-"}`],
        ["Disk free", `${disk.free_human || "-"}`],
        ["Processes", system.process_count ?? "-"],
        ["Network recv", net.bytes_recv_human || "-"],
        ["Network sent", net.bytes_sent_human || "-"],
        ["Packets recv", net.packets_recv ?? "-"],
        ["Packets sent", net.packets_sent ?? "-"],
    ];
    el.innerHTML = "<ul class='snapshot-list'>" + rows.map(
        ([k, v]) => `<li><span>${k}</span><span>${v}</span></li>`
    ).join("") + "</ul>";
}

/* ---------------- Overview: health factors ---------------- */
function renderHealthFactors(factors, issues) {
    const el = document.getElementById("healthFactors");
    if (!el) return;
    if (!factors || !factors.length) { el.innerHTML = "<p class='muted'>No factors available.</p>"; return; }
    el.innerHTML = "<ul class='factor-list'>" + factors.map(f => {
        const cls = f.impact < 0 ? "impact-neg" : "impact-pos";
        return `<li><span>${esc(f.factor)}</span> <span class="${cls}">${f.impact > 0 ? "+" : ""}${f.impact}</span>
                <div class="muted small">${esc(f.reason)}</div></li>`;
    }).join("") + "</ul>";
}

/* ---------------- Overview: recommendations ---------------- */
function renderRecommendations(recs) {
    const el = document.getElementById("recommendations");
    if (!el) return;
    if (!recs || !recs.length) { el.innerHTML = "<p class='muted'>No recommendations.</p>"; return; }
    el.innerHTML = "<ul class='rec-list'>" + recs.map(r => {
        return `<li>
            <span class="badge ${severityBadge(r.severity)}">${esc(r.severity)}</span>
            <strong>${esc(r.title)}</strong>
            <div class="muted small">${esc(r.description)}</div>
            <div class="muted small">→ ${esc(r.action)}</div>
        </li>`;
    }).join("") + "</ul>";
}

/* ---------------- Overview: predictions ---------------- */
function renderPredictions(preds) {
    const el = document.getElementById("predictions");
    if (!el) return;
    if (!preds || !preds.available) {
        el.innerHTML = `<p class="muted small">${preds ? esc(preds.reason || "") : "Not enough historical data for reliable forecasting."}</p>`;
        return;
    }
    let html = "<ul class='pred-list'>";
    for (const key of ["cpu", "ram", "disk"]) {
        const d = preds[key];
        if (!d) continue;
        html += `<li>
            <strong>${key.toUpperCase()}</strong>
            <span class="badge ${trendBadge(d.trend)}">${esc(d.trend)}</span>
            <span class="badge badge-gray">reliability ${(d.reliability * 100).toFixed(0)}%</span>
            <div class="muted small">Current ${d.current.toFixed(1)}% → forecast ${d.range_low}-${d.range_high}%</div>
            <div class="muted small">R² ${Number(d.reliability).toFixed(3)} · Risk: ${esc(d.risk)}</div>
            ${d.reliability_note ? `<div class="muted small warn">${esc(d.reliability_note)}</div>` : ""}
        </li>`;
    }
    html += "</ul>";
    el.innerHTML = html;
}

/* ---------------- Live charts ---------------- */
/* Centralized live snapshot: each logical update cycle (anchored to the
   fastest, most regular poll — system metrics) collects the current
   frontend state and pushes exactly ONE coherent chart point. */
function updateLiveSnapshot() {
    if (!state.lastUpdate.health) return;
    const now = new Date().toLocaleTimeString();
    const live = state.live;
    live.labels.push(now);
    live.cpu.push(state.cpu);
    live.ram.push(state.ram);
    live.disk.push(state.disk);
    live.health.push(state.health.score);
    live.security.push(state.security.score);
    live.processes.push(state.lastSnapshot && state.lastSnapshot.process_count != null
        ? state.lastSnapshot.process_count : 0);
    if (live.labels.length > MAX_LIVE_POINTS) {
        live.labels.shift();
        ["cpu", "ram", "disk", "health", "security", "processes"].forEach(k => live[k].shift());
    }
    setChartData(charts.cpu, live.labels.slice(), live.cpu.slice());
    setChartData(charts.ram, live.labels.slice(), live.ram.slice());
    setChartData(charts.disk, live.labels.slice(), live.disk.slice());
    setChartData(charts.health, live.labels.slice(), live.health.slice());
    setChartData(charts.security, live.labels.slice(), live.security.slice());
    setChartData(charts.processes, live.labels.slice(), live.processes.slice());
}

function setRange(range) {
    state.range = range;
    document.querySelectorAll(".range-btn").forEach(b => {
        b.classList.toggle("active", b.dataset.range === range);
    });
    if (range === "live") {
        updateLiveSnapshot();
    } else {
        fetchHistory();
    }
}

/* ---------------- Security tab ---------------- */
function renderSecurity(data) {
    const summary = document.getElementById("securitySummary");
    if (summary) {
        summary.innerHTML = `<div class="stat-inline">
            <div><strong>Score</strong><br>${data.score}/100</div>
            <div><strong>Status</strong><br>${esc(data.status)}</div>
            <div><strong>Findings</strong><br>${(data.findings || []).length}</div>
            <div><strong>Last scan</strong><br>${esc(data.last_scan || "-")}</div>
        </div>`;
    }
    const list = document.getElementById("findings");
    if (!list) return;
    const findings = data.findings || [];
    if (!findings.length) {
        list.innerHTML = "<p class='muted'>No processes flagged by heuristics.</p>";
        return;
    }
    list.innerHTML = findings.map(f => `
        <div class="finding-card sev-${esc(f.severity)}">
            <div class="finding-header">
                <span class="finding-name">${esc(f.name)}</span>
                <span class="badge ${severityBadge(f.severity)}">${esc(f.severity)}</span>
                <span class="badge badge-blue">score ${f.score}</span>
                <span class="badge badge-gray">strength ${(f.heuristic_strength * 100).toFixed(0)}%</span>
                <span class="muted small">PID ${f.pid}</span>
            </div>
            <ul class="finding-reasons">${(f.reasons || []).map(r => `<li>• ${esc(r)}</li>`).join("")}</ul>
            ${f.evidence && f.evidence.exe ? `<div class="muted small monospace">${esc(f.evidence.exe)}</div>` : ""}
            ${f.recommendation ? `<div class="muted small"><strong>Recommended action:</strong> ${esc(f.recommendation)}</div>` : ""}
        </div>`).join("");
}

/* ---------------- Ports tab ---------------- */
function renderPorts(ports) {
    const summary = document.getElementById("portsSummary");
    const exposed = ports.filter(p => p.exposed).length;
    if (summary) {
        summary.innerHTML = `<div class="stat-inline">
            <div><strong>Listening</strong><br>${ports.length}</div>
            <div><strong>Exposed</strong><br>${exposed}</div>
            <div><strong>Last scan</strong><br>${esc(state.security.last_scan || "-")}</div>
        </div>`;
    }
    const tbody = document.getElementById("portsTable");
    if (!tbody) return;
    if (!ports.length) {
        tbody.innerHTML = "<tr><td colspan='8' class='muted'>No listening ports observed.</td></tr>";
        return;
    }
    tbody.innerHTML = ports.map(p => `
        <tr>
            <td>${p.port}</td>
            <td>${esc(p.protocol)}</td>
            <td class="monospace">${esc(p.local_address)}</td>
            <td>${p.pid ?? "-"}</td>
            <td>${esc(p.process_name || "-")}</td>
            <td>${esc(p.service || "-")}</td>
            <td><span class="badge ${riskBadge(p.risk_level)}">${esc(p.risk_level)}</span></td>
            <td class="muted small">${p.exposed ? "Exposed on all interfaces" : "Loopback only"}</td>
        </tr>`).join("");
}

/* ---------------- Process details modal ---------------- */
async function showProcessDetails(pid) {
    try {
        const d = await apiRequest(`/api/processes/${pid}`);
        const mem = d.memory || {};
        const conns = d.connections || [];
        const files = d.open_files || [];
        const rows = [
            ["Name", esc(d.name || "-")],
            ["PID", d.pid],
            ["Parent (PPID)", d.ppid_name ? `${esc(d.ppid_name)} (${d.ppid})` : (d.ppid ?? "-")],
            ["Status", esc(d.status || "-")],
            ["Username", esc(d.username || "-")],
            ["Executable", `<span class="monospace">${esc(d.exe || "-")}</span>`],
            ["Working dir", `<span class="monospace">${esc(d.cwd || "-")}</span>`],
            ["Command line", `<span class="monospace">${esc((d.cmdline || []).join(" "))}</span>`],
            ["CPU", `${d.cpu_percent}%`],
            ["Memory", `${d.memory_percent}% (RSS ${formatBytes(mem.rss)})`],
            ["Threads", d.num_threads ?? "-"],
            ["Created", esc(d.create_time || "-")],
            ["Connections", conns.length],
            ["Open files", files.length],
        ];
        const connHtml = conns.slice(0, 5).map(c => {
            const laddr = c.laddr ? `${c.laddr.ip}:${c.laddr.port}` : "-";
            const raddr = c.raddr ? `${c.raddr.ip}:${c.raddr.port}` : "-";
            return `<div class="muted small monospace">${esc(c.status)} ${esc(laddr)} → ${esc(raddr)}</div>`;
        }).join("") || "<div class='muted small'>None</div>";

        const modalBody = document.getElementById("modalBody");
        modalBody.innerHTML = `
            <h2>Process Details — ${esc(d.name || "Unknown")}</h2>
            <table class="detail-table">${rows.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join("")}</table>
            <h3>Recent Connections</h3>${connHtml}
            <h3>Open Files (${files.length})</h3>
            <div class="monospace muted small">${files.slice(0, 8).map(f => esc(f)).join("<br>") || "None"}</div>
        `;
        openModal("modalOverlay");
    } catch (err) {
        console.error(err);
        alert(err.message || "Failed to load process details");
    }
}

/* ---------------- Terminate modal ---------------- */
async function requestTerminate(pid) {
    try {
        const d = await apiRequest(`/api/processes/${pid}`);
        const terminateBody = document.getElementById("terminateBody");
        terminateBody.innerHTML = `
            <h2>Confirm Termination</h2>
            <p class="muted small">Terminating a process will close it and any dependent work. Protected system processes cannot be terminated.</p>
            <table class="detail-table">
                <tr><td>Process</td><td><strong>${esc(d.name || "Unknown")}</strong></td></tr>
                <tr><td>PID</td><td>${d.pid}</td></tr>
                <tr><td>Executable</td><td class="monospace">${esc(d.exe || "-")}</td></tr>
                <tr><td>Username</td><td>${esc(d.username || "-")}</td></tr>
            </table>
            <div class="terminate-actions">
                <button class="btn btn-danger" id="btnTerminate">Terminate (graceful)</button>
                <button class="btn" id="btnForceKill">Force Kill</button>
                <button class="btn" onclick="closeModal('terminateOverlay')">Cancel</button>
            </div>
            <div id="terminateStatus" class="muted small" style="margin-top:10px"></div>
        `;
        openModal("terminateOverlay");
        document.getElementById("btnTerminate").onclick = () => doTerminate(pid, false);
        document.getElementById("btnForceKill").onclick = () => doTerminate(pid, true);
    } catch (err) {
        alert(err.message || "Failed to load process details");
    }
}

async function doTerminate(pid, force) {
    const status = document.getElementById("terminateStatus");
    const btn = force ? document.getElementById("btnForceKill") : document.getElementById("btnTerminate");
    status.textContent = force ? "Force killing…" : "Terminating…";
    btn.disabled = true;
    try {
        const data = await apiRequest(`/api/processes/${pid}/${force ? "kill" : "terminate"}`, { method: "POST" });
        status.textContent = data.message || "Done.";
        setTimeout(() => {
            closeModal("terminateOverlay");
            // Immediately refresh the process list without a page reload.
            fetchProcesses();
        }, 800);
    } catch (err) {
        status.textContent = err.message || "Failed.";
    }
    btn.disabled = false;
}

/* ---------------- Report / GC / export ---------------- */
async function generateReport() {
    const status = document.getElementById("actionStatus");
    status.textContent = "Generating report…";
    try {
        const res = await fetch(API.report, { method: "POST" });
        if (!res.ok) {
            const body = await res.json().catch(() => null);
            status.textContent = (body && body.error && body.error.message) || "Report failed.";
            return;
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `system_report_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.pdf`;
        a.click();
        URL.revokeObjectURL(url);
        status.textContent = "Report downloaded.";
    } catch (err) {
        status.textContent = "Report generation failed.";
    }
}

async function runGc() {
    const status = document.getElementById("actionStatus");
    status.textContent = "Running garbage collection…";
    try {
        const data = await apiRequest(API.gc, { method: "POST" });
        status.textContent = `${data.message} (${data.objects_collected} objects collected) — note: this does not necessarily free OS-level RAM.`;
    } catch (err) {
        status.textContent = "Garbage collection failed.";
    }
}

function exportData() {
    const payload = {
        timestamp: new Date().toISOString(),
        snapshot: state.lastSnapshot,
        health: state.health,
        security: state.security,
        predictions: state.predictions,
        recommendations: state.recommendations,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `system_snapshot_${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

/* ---------------- Modals / tabs helpers ---------------- */
function openModal(id) { document.getElementById(id).classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id).classList.add("hidden"); }
function isTabActive(name) {
    return document.getElementById("tab-" + name).classList.contains("active");
}

function initTabs() {
    document.querySelectorAll(".tab").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
            btn.classList.add("active");
            document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
            // Refresh the newly-visible tab immediately.
            if (btn.dataset.tab === "processes") fetchProcesses();
            if (btn.dataset.tab === "security") fetchSecurity();
            if (btn.dataset.tab === "ports") fetchPorts();
            if (btn.dataset.tab === "charts") fetchHistory();
            if (btn.dataset.tab === "overview") { fetchHealth(); fetchRecommendations(); }
        });
    });
}

/* ---------------- Real-time control ---------------- */
function startRealtimeUpdates() {
    refreshManager.start("system", fetchSystemMetrics, REFRESH_INTERVALS.system);
    refreshManager.start("health", fetchHealth, REFRESH_INTERVALS.health);
    refreshManager.start("processes", fetchProcesses, REFRESH_INTERVALS.processes);
    refreshManager.start("security", fetchSecurity, REFRESH_INTERVALS.security);
    refreshManager.start("ports", fetchPorts, REFRESH_INTERVALS.ports);
    refreshManager.start("history", fetchHistory, REFRESH_INTERVALS.history);
    refreshManager.start("predictions", fetchPredictions, REFRESH_INTERVALS.predictions);
    refreshManager.start("recommendations", fetchRecommendations, REFRESH_INTERVALS.recommendations);
}

function stopRealtimeUpdates() {
    refreshManager.stopAll();
}

/* ---------------- Helpers ---------------- */
function esc(value) {
    if (value === null || value === undefined) return "";
    return String(value).replace(/[&<>"']/g, c => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}
function formatBytes(value) {
    if (!value) return "0 B";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let i = 0;
    let v = value;
    while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
    return `${v.toFixed(1)} ${units[i]}`;
}
function severityBadge(severity) {
    return { "Critical": "badge-red", "High": "badge-red", "Moderate": "badge-orange", "Low": "badge-yellow", "Info": "badge-blue", "Medium": "badge-orange" }[severity] || "badge-gray";
}
function riskBadge(risk) {
    return { "High": "badge-red", "Moderate": "badge-orange", "Low": "badge-green" }[risk] || "badge-gray";
}
function trendBadge(trend) {
    return { "increasing": "badge-red", "decreasing": "badge-green", "stable": "badge-blue" }[trend] || "badge-gray";
}
function debounce(fn, delay) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

/* ---------------- Init ---------------- */
async function init() {
    initTabs();

    document.getElementById("modalClose").addEventListener("click", () => closeModal("modalOverlay"));
    document.getElementById("terminateClose").addEventListener("click", () => closeModal("terminateOverlay"));
    [["modalOverlay", "modalOverlay"], ["terminateOverlay", "terminateOverlay"]].forEach(([id]) => {
        document.getElementById(id).addEventListener("click", (e) => {
            if (e.target.id === id) closeModal(id);
        });
    });

    document.querySelectorAll(".range-btn").forEach(btn => {
        btn.addEventListener("click", () => setRange(btn.dataset.range));
    });

    document.getElementById("procSort").addEventListener("change", renderProcessTable);
    document.getElementById("procFilter").addEventListener("input", debounce(renderProcessTable, 200));
    document.getElementById("refreshProcesses").addEventListener("click", fetchProcesses);
    document.getElementById("generateReport").addEventListener("click", generateReport);
    document.getElementById("runGc").addEventListener("click", runGc);
    document.getElementById("exportData").addEventListener("click", exportData);

    // Visibility optimization: pause expensive polling while hidden,
    // refresh immediately when the user returns.
    document.addEventListener("visibilitychange", () => {
        state.visible = !document.hidden;
        if (document.hidden) {
            stopRealtimeUpdates();
        } else {
            startRealtimeUpdates();
        }
    });

    // Stale-data indicator sweep (once per second, cheap).
    setInterval(updateStaleFlags, 1000);

    setConnection("reconnecting");
    startRealtimeUpdates();
}

document.addEventListener("DOMContentLoaded", init);
