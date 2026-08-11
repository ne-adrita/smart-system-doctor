/* =====================================================================
   Smart System Doctor Pro - dashboard controller
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
    report: "/api/reports/pdf",
    gc: "/api/maintenance/gc",
};

const state = {
    cpu: 0,
    ram: 0,
    disk: 0,
    health: { score: 0, status: "Unknown" },
    security: { score: 100, status: "Safe", findings: [], reasons: [] },
    live: { labels: [], cpu: [], ram: [], health: [], security: [] },
    range: "live",
    lastSnapshot: null,
};

/* ---------------- Chart setup ---------------- */
const chartOpts = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 200 },
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
    health: makeChart(document.getElementById("chartHealth"), "#667eea"),
    security: makeChart(document.getElementById("chartSecurity"), "#2ecc71"),
};

function setChartData(chart, labels, values) {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update();
}

/* ---------------- API helper ---------------- */
async function getJSON(url, options) {
    const res = await fetch(url, options);
    const body = await res.json();
    if (!body.success) {
        throw new Error((body.error && body.error.message) || "Request failed");
    }
    return body.data;
}

/* ---------------- Polling ---------------- */
let systemTimer = null;
let securityTimer = null;
let recTimer = null;

async function pollFast() {
    try {
        const [system, health] = await Promise.all([
            getJSON(API.system),
            getJSON(API.health),
        ]);
        state.cpu = system.cpu;
        state.ram = system.ram.percent;
        state.disk = system.disk_percent;
        state.health = health;
        state.lastSnapshot = system;
        renderTiles();
        renderAlert();
        renderSnapshot(system);
        renderHealthFactors(health.factors, health.issues);
        if (state.range === "live") {
            pushLivePoint();
        }
        setConnection(true);
    } catch (err) {
        console.error("pollFast failed:", err);
        setConnection(false);
    }
}

async function pollSecurity() {
    try {
        const data = await getJSON(API.security);
        state.security = data;
        renderTiles();
        renderAlert();
        if (state.range === "live") pushLivePoint();
        if (isTabActive("security")) renderSecurity(data);
        if (isTabActive("ports")) renderPorts(data.ports);
    } catch (err) {
        console.error("pollSecurity failed:", err);
    }
}

async function pollRecommendations() {
    try {
        const [recs, preds] = await Promise.all([
            getJSON(API.recommendations),
            getJSON(API.predictions),
        ]);
        renderRecommendations(recs.recommendations);
        renderPredictions(preds);
        if (isTabActive("overview")) renderTopProcesses();
    } catch (err) {
        console.error("pollRecommendations failed:", err);
    }
}

/* ---------------- Tiles & alert ---------------- */
function renderTiles() {
    setTile("cpu", `${state.cpu.toFixed(0)}%`, pctColor(state.cpu));
    setTile("ram", `${state.ram.toFixed(0)}%`, pctColor(state.ram));
    setTile("disk", `${state.disk.toFixed(0)}%`, pctColor(state.disk));
    setBar("cpu", state.cpu);
    setBar("ram", state.ram);
    setBar("disk", state.disk);
    setTile("health", `${state.health.score}/100`, state.health.color || "#667eea");
    setTileSub("health", state.health.status || "-");
    setTile("security", `${state.security.score}/100`, state.security.color || "#2ecc71");
    setTileSub("security", state.security.status || "-");
    document.getElementById("lastUpdated").textContent = "Last updated: " + new Date().toLocaleTimeString();
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
    const rows = [
        ["Operating System", `${os.system || "-"} ${os.release || ""}`],
        ["Hostname", os.hostname || "-"],
        ["Uptime", uptime.uptime_human || "-"],
        ["Boot time", uptime.boot_time_iso || "-"],
        ["CPU cores", `${system.cpu_info.count || "-"} (${system.cpu_info.physical_count || "-"} physical)`],
        ["RAM", `${mem.used_human || "-"} / ${mem.total_human || "-"}`],
        ["Disk free", `${disk.free_human || "-"}`],
        ["Processes", system.process_count ?? "-"],
        ["Network recv", system.network.bytes_recv_human || "-"],
        ["Network sent", system.network.bytes_sent_human || "-"],
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
        el.innerHTML = `<p class="muted small">${preds ? esc(preds.reason || "") : "Predictions unavailable."}</p>`;
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
            <div class="muted small">Risk: ${esc(d.risk)}</div>
            ${d.reliability_note ? `<div class="muted small warn">${esc(d.reliability_note)}</div>` : ""}
        </li>`;
    }
    html += "</ul>";
    el.innerHTML = html;
}

/* ---------------- Overview: top processes ---------------- */
async function renderTopProcesses() {
    const el = document.getElementById("topProcesses");
    if (!el) return;
    try {
        const data = await getJSON(`${API.processes}?sort_by=cpu&limit=8`);
        if (!data.processes.length) { el.innerHTML = "<tr><td colspan='6' class='muted'>No processes.</td></tr>"; return; }
        el.innerHTML = data.processes.map(p => `
            <tr>
                <td>${p.pid}</td>
                <td>${esc(p.name || "-")}</td>
                <td>${(p.cpu_percent || 0).toFixed(1)}</td>
                <td>${(p.memory_percent || 0).toFixed(1)}</td>
                <td>${esc(p.status || "-")}</td>
                <td><button class="btn btn-sm" onclick="showProcessDetails(${p.pid})">Details</button></td>
            </tr>`).join("");
    } catch (err) {
        el.innerHTML = "<tr><td colspan='6' class='muted'>Failed to load processes.</td></tr>";
    }
}

/* ---------------- Charts ---------------- */
function pushLivePoint() {
    const now = new Date().toLocaleTimeString();
    const live = state.live;
    live.labels.push(now);
    live.cpu.push(state.cpu);
    live.ram.push(state.ram);
    live.health.push(state.health.score);
    live.security.push(state.security.score);
    if (live.labels.length > 60) {
        live.labels.shift(); live.cpu.shift(); live.ram.shift();
        live.health.shift(); live.security.shift();
    }
    setChartData(charts.cpu, live.labels.slice(), live.cpu.slice());
    setChartData(charts.ram, live.labels.slice(), live.ram.slice());
    setChartData(charts.health, live.labels.slice(), live.health.slice());
    setChartData(charts.security, live.labels.slice(), live.security.slice());
}

async function loadHistoryRange(range) {
    const hours = { "1h": 1, "6h": 6, "24h": 24 }[range];
    try {
        const data = await getJSON(`${API.history}?hours=${hours}&limit=120`);
        const rows = data.history;
        const labels = rows.map(r => r.time ? r.time.slice(11, 19) : "");
        setChartData(charts.cpu, labels, rows.map(r => r.cpu));
        setChartData(charts.ram, labels, rows.map(r => r.ram));
        setChartData(charts.health, labels, rows.map(r => r.health));
        setChartData(charts.security, labels, rows.map(r => r.security));
    } catch (err) {
        console.error("loadHistoryRange failed:", err);
    }
}

function setRange(range) {
    state.range = range;
    document.querySelectorAll(".range-btn").forEach(b => {
        b.classList.toggle("active", b.dataset.range === range);
    });
    if (range === "live") {
        pushLivePoint();
    } else {
        loadHistoryRange(range);
    }
}

/* ---------------- Processes tab ---------------- */
async function loadProcesses() {
    const el = document.getElementById("processTable");
    if (!el) return;
    const sort = document.getElementById("procSort").value;
    const filter = document.getElementById("procFilter").value.trim().toLowerCase();
    el.innerHTML = "<tr><td colspan='8' class='muted'>Loading…</td></tr>";
    try {
        const data = await getJSON(`${API.processes}?sort_by=${sort}&limit=200`);
        let rows = data.processes;
        if (filter) rows = rows.filter(p => (p.name || "").toLowerCase().includes(filter));
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
    } catch (err) {
        el.innerHTML = "<tr><td colspan='8' class='muted'>Failed to load processes.</td></tr>";
    }
}

/* ---------------- Security tab ---------------- */
function renderSecurity(data) {
    const summary = document.getElementById("securitySummary");
    if (summary) {
        summary.innerHTML = `<div class="stat-inline">
            <div><strong>Score</strong><br>${data.score}/100</div>
            <div><strong>Status</strong><br>${esc(data.status)}</div>
            <div><strong>Findings</strong><br>${data.findings.length}</div>
            <div><strong>Last scan</strong><br>${esc(data.last_scan || "-")}</div>
        </div>`;
    }
    const list = document.getElementById("findings");
    if (!list) return;
    if (!data.findings.length) {
        list.innerHTML = "<p class='muted'>No processes flagged by heuristics.</p>";
        return;
    }
    list.innerHTML = data.findings.map(f => `
        <div class="finding-card sev-${esc(f.severity)}">
            <div class="finding-header">
                <span class="finding-name">${esc(f.name)}</span>
                <span class="badge ${severityBadge(f.severity)}">${esc(f.severity)}</span>
                <span class="badge badge-blue">score ${f.score}</span>
                <span class="badge badge-gray">strength ${(f.heuristic_strength * 100).toFixed(0)}%</span>
                <span class="muted small">PID ${f.pid}</span>
            </div>
            <ul class="finding-reasons">${f.reasons.map(r => `<li>• ${esc(r)}</li>`).join("")}</ul>
            ${f.evidence && f.evidence.exe ? `<div class="muted small monospace">${esc(f.evidence.exe)}</div>` : ""}
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
        const res = await fetch(`/api/processes/${pid}`);
        const body = await res.json();
        if (!body.success) {
            alert((body.error && body.error.message) || "Failed to load process");
            return;
        }
        const d = body.data;
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
        alert("Failed to load process details");
    }
}

/* ---------------- Terminate modal ---------------- */
async function requestTerminate(pid) {
    try {
        const res = await fetch(`/api/processes/${pid}`);
        const body = await res.json();
        if (!body.success) {
            alert((body.error && body.error.message) || "Failed to load process");
            return;
        }
        const d = body.data;
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
        alert("Failed to load process details");
    }
}

async function doTerminate(pid, force) {
    const status = document.getElementById("terminateStatus");
    const btn = force ? document.getElementById("btnForceKill") : document.getElementById("btnTerminate");
    status.textContent = force ? "Force killing…" : "Terminating…";
    btn.disabled = true;
    try {
        const res = await fetch(`/api/processes/${pid}/${force ? "kill" : "terminate"}`, { method: "POST" });
        const body = await res.json();
        if (!body.success) {
            status.textContent = (body.error && body.error.message) || "Failed.";
        } else {
            status.textContent = body.data.message || "Done.";
            setTimeout(() => {
                closeModal("terminateOverlay");
                loadProcesses();
                if (isTabActive("overview")) renderTopProcesses();
            }, 800);
        }
    } catch (err) {
        status.textContent = "Request failed.";
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
        const data = await getJSON(API.gc, { method: "POST" });
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
            if (btn.dataset.tab === "processes") loadProcesses();
            if (btn.dataset.tab === "security") renderSecurity(state.security);
            if (btn.dataset.tab === "ports") renderPorts(state.security.ports || []);
        });
    });
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
function setConnection(connected) {
    const el = document.getElementById("connectionState");
    if (el) {
        el.className = connected ? "pill pill-good" : "pill pill-bad";
        el.textContent = connected ? "● Connected" : "● Offline";
    }
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

    document.getElementById("procSort").addEventListener("change", loadProcesses);
    document.getElementById("procFilter").addEventListener("input", debounce(loadProcesses, 300));
    document.getElementById("refreshProcesses").addEventListener("click", loadProcesses);
    document.getElementById("generateReport").addEventListener("click", generateReport);
    document.getElementById("runGc").addEventListener("click", runGc);
    document.getElementById("exportData").addEventListener("click", exportData);

    // Immediate first paint
    await pollFast();
    pollSecurity();
    pollRecommendations();
    renderHealthFactors(state.health.factors, state.health.issues);
    renderTopProcesses();
    setRange("live");

    // Regular polling (separated frequencies)
    systemTimer = setInterval(pollFast, 3000);
    securityTimer = setInterval(pollSecurity, 15000);
    recTimer = setInterval(pollRecommendations, 30000);
}

function debounce(fn, delay) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}

document.addEventListener("DOMContentLoaded", init);
