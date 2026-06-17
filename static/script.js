/* =========================
   ADVANCED OS EXPLANATION ENGINE
========================= */
function explain(cpu, ram, predictions){
    let insights = [];
    
    // Current state analysis
    if(cpu > 80){
        insights.push("🔥 CPU bottleneck detected - scheduler overload");
        if(predictions && predictions.cpu && predictions.cpu.trend === "increasing"){
            insights.push("📈 CPU load trending upward - likely more pressure incoming");
        }
    } else if(cpu > 60){
        insights.push("⚡ Moderate CPU load - normal scheduling activity");
    } else {
        insights.push("✅ CPU utilization optimal - scheduler has capacity");
    }
    
    if(ram > 80){
        insights.push("💾 Memory pressure - page swapping may occur");
        if(predictions && predictions.ram && predictions.ram.trend === "increasing"){
            insights.push("📈 Memory usage increasing - allocation requests rising");
        }
    } else if(ram > 60){
        insights.push("📊 Moderate memory usage - normal allocation patterns");
    } else {
        insights.push("✅ Memory allocation healthy - ample free pages");
    }
    
    return insights.join(" | ");
}

function systemAlert(cpu, ram, security, health_issues){
    if(cpu > 85 && ram > 85){
        return "🚨 CRITICAL: System near collapse - CPU + RAM saturation";
    }
    
    if(security < 50){
        return "🔴 SECURITY BREACH: Immediate action required";
    }
    
    if(health_issues && health_issues.length > 0){
        return "⚠️ " + health_issues[0];
    }
    
    if(cpu > 80 || ram > 80){
        return "⚠️ Resource exhaustion warning";
    }
    
    return "✅ All systems nominal";
}

function recommendation(cpu, ram, security, diagnostics){
    let msg = [];
    
    if(diagnostics && diagnostics.recommendations){
        for(let rec of diagnostics.recommendations){
            msg.push(rec.text + " → " + rec.action);
        }
    }
    
    if(msg.length === 0){
        if(cpu > 70) msg.push("Consider reducing CPU load");
        if(ram > 70) msg.push("Consider freeing memory");
        if(security < 70) msg.push("Review security settings");
    }
    
    if(msg.length === 0){
        msg.push("System optimized - no action needed");
    }
    
    return msg.join(" | ");
}

function systemBrain(cpu, ram, security, predictions){
    let analysis = [];
    
    // Predictive analysis
    if(predictions && predictions.cpu && predictions.cpu.trend === "increasing"){
        analysis.push("📈 CPU load expected to rise - prepare for scaling");
    }
    if(predictions && predictions.ram && predictions.ram.trend === "increasing"){
        analysis.push("📈 Memory usage increasing - check for leaks");
    }
    
    // Security analysis
    if(security < 60){
        analysis.push("🔐 Security posture compromised - analyze threats");
    }
    
    // Performance analysis
    if(cpu > 70 || ram > 70){
        analysis.push("⚙️ Resource contention detected - optimize processes");
    }
    
    if(analysis.length === 0){
        analysis.push("🧠 System intelligence: All subsystems operating within parameters");
    }
    
    return analysis.join(" | ");
}

/* =========================
   DATA STORAGE WITH TIME SERIES
========================= */
let cpuData = [];
let ramData = [];
let diskData = [];
let securityData = [];
let labels = [];
let rawDataHistory = [];

/* =========================
   INIT CHARTS (CPU + RAM + DISK + SECURITY)
========================= */
const cpuChart = new Chart(document.getElementById('cpuChart'), {
    type: 'line',
    data: {
        labels: labels,
        datasets: [{
            label: 'CPU %',
            data: cpuData,
            borderColor: '#ff4757',
            backgroundColor: 'rgba(255,71,87,0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 3
        }]
    },
    options: {
        responsive: true,
        animation: { duration: 300 },
        plugins: {
            legend: { labels: { color: 'white' } }
        },
        scales: {
            y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white' } },
            x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white', maxTicksLimit: 10 } }
        }
    }
});

const ramChart = new Chart(document.getElementById('ramChart'), {
    type: 'line',
    data: {
        labels: labels,
        datasets: [{
            label: 'RAM %',
            data: ramData,
            borderColor: '#3498db',
            backgroundColor: 'rgba(52,152,219,0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 3
        }]
    },
    options: {
        responsive: true,
        animation: { duration: 300 },
        plugins: {
            legend: { labels: { color: 'white' } }
        },
        scales: {
            y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white' } },
            x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white', maxTicksLimit: 10 } }
        }
    }
});

// Additional chart for security
const securityChart = new Chart(document.getElementById('securityChart'), {
    type: 'line',
    data: {
        labels: labels,
        datasets: [{
            label: 'Security Score',
            data: securityData,
            borderColor: '#2ecc71',
            backgroundColor: 'rgba(46,204,113,0.1)',
            fill: true,
            tension: 0.4,
            pointRadius: 3
        }]
    },
    options: {
        responsive: true,
        animation: { duration: 300 },
        plugins: {
            legend: { labels: { color: 'white' } }
        },
        scales: {
            y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white' } },
            x: { grid: { color: 'rgba(255,255,255,0.1)' }, ticks: { color: 'white', maxTicksLimit: 10 } }
        }
    }
});

/* =========================
   MAIN UPDATE FUNCTION
========================= */
async function update(){
    try{
        let res = await fetch('/data');
        let data = await res.json();
        
        let time = new Date().toLocaleTimeString();
        
        /* =====================
           GRAPH DATA UPDATE
        ====================== */
        labels.push(time);
        cpuData.push(data.cpu);
        ramData.push(data.ram);
        diskData.push(data.disk);
        securityData.push(data.security_score);
        rawDataHistory.push(data);
        
        if(labels.length > 15){
            labels.shift();
            cpuData.shift();
            ramData.shift();
            diskData.shift();
            securityData.shift();
            rawDataHistory.shift();
        }
        
        /* =====================
           SYSTEM INFO UI
        ====================== */
        document.getElementById("cpu").innerHTML = `<strong>${data.cpu}%</strong>`;
        document.getElementById("ram").innerHTML = `<strong>${data.ram}%</strong>`;
        document.getElementById("disk").innerHTML = `<strong>${data.disk}%</strong>`;
        document.getElementById("processCount").innerHTML = `Active Processes: <strong>${data.process_count}</strong>`;
        
        // Health section
        document.getElementById("health").innerHTML = 
            `<span style="color: ${data.health_color}">${data.health_icon} ${data.health_score}/100</span>`;
        document.getElementById("healthState").innerHTML = 
            `<span style="color: ${data.health_color}">${data.health_state}</span>`;
        
        // Health issues
        let issuesList = document.getElementById("healthIssues");
        if(issuesList && data.health_issues && data.health_issues.length > 0){
            issuesList.innerHTML = data.health_issues.map(issue => 
                `<li style="color: #ff6b6b;">${issue}</li>`
            ).join('');
        } else if(issuesList) {
            issuesList.innerHTML = '<li style="color: #2ecc71;">No issues detected</li>';
        }
        
        // Predictions
        let predictionsDiv = document.getElementById("predictions");
        if(predictionsDiv && data.health_predictions){
            let html = '';
            if(data.health_predictions.cpu){
                html += `<div>CPU: ${data.health_predictions.cpu.trend} (peak: ${data.health_predictions.cpu.predicted_peak.toFixed(1)}%)</div>`;
            }
            if(data.health_predictions.ram){
                html += `<div>RAM: ${data.health_predictions.ram.trend} (peak: ${data.health_predictions.ram.predicted_peak.toFixed(1)}%)</div>`;
            }
            predictionsDiv.innerHTML = html || 'No predictions available';
        }
        
        // Security section
        document.getElementById("security").innerHTML = 
            `<span style="color: ${data.security_color}">${data.security_icon} ${data.security_score}/100</span>`;
        document.getElementById("securityState").innerHTML = 
            `<span style="color: ${data.security_color}">${data.security_state}</span>`;
        
        // Security warnings
        let warningsList = document.getElementById("securityWarnings");
        if(warningsList && data.security_warnings && data.security_warnings.length > 0){
            warningsList.innerHTML = data.security_warnings.map(warning => 
                `<li style="color: #ff6b6b;">${warning}</li>`
            ).join('');
        } else if(warningsList) {
            warningsList.innerHTML = '<li style="color: #2ecc71;">No security warnings</li>';
        }
        
        // Security threats
        let threatsList = document.getElementById("threatsList");
        if(threatsList && data.security_threats && data.security_threats.length > 0){
            threatsList.innerHTML = data.security_threats.map(threat => 
                `<li style="color: #e74c3c;">
                    ${threat.name || 'Unknown'} (PID: ${threat.pid}) - ${threat.severity}
                    <br><small>${threat.reasons ? threat.reasons.join(', ') : ''}</small>
                </li>`
            ).join('');
        } else if(threatsList) {
            threatsList.innerHTML = '<li style="color: #2ecc71;">No suspicious processes</li>';
        }
        
        // Open ports
        let portsList = document.getElementById("portsList");
        if(portsList && data.security_ports && data.security_ports.length > 0){
            portsList.innerHTML = data.security_ports.map(port => 
                `<li style="color: #f39c12;">Port ${port} open</li>`
            ).join('');
        } else if(portsList) {
            portsList.innerHTML = '<li style="color: #2ecc71;">No open risky ports</li>';
        }
        
        /* =====================
           ALERT, RECOMMENDATION, BRAIN
        ====================== */
        document.getElementById("alertBox").innerHTML = 
            systemAlert(data.cpu, data.ram, data.security_score, data.health_issues);
        
        document.getElementById("recommendBox").innerHTML = 
            recommendation(data.cpu, data.ram, data.security_score, data.diagnostics);
        
        document.getElementById("brainBox").innerHTML = 
            systemBrain(data.cpu, data.ram, data.security_score, data.health_predictions);
        
        /* =====================
           OS EXPLANATION BOX
        ====================== */
        document.getElementById("osExplain").innerHTML = 
            explain(data.cpu, data.ram, data.health_predictions);
        
        /* =====================
           PROCESS LIST UI
        ====================== */
        let list = document.getElementById("processList");
        if(list){
            list.innerHTML = "";
            
            data.processes.forEach((p, index) => {
                let li = document.createElement("li");
                let threatLevel = data.security_threats.find(t => t.pid === p.pid);
                let color = threatLevel ? '#e74c3c' : '#ecf0f1';
                
                li.style.borderBottom = '1px solid #2c3e50';
                li.style.padding = '8px 0';
                li.innerHTML = `
                    <span style="color: ${color};">
                        <strong>${p.name || 'Unknown'}</strong>
                    </span>
                    <span style="float: right;">
                        Memory: ${(p.memory_percent || 0).toFixed(1)}% | CPU: ${(p.cpu_percent || 0).toFixed(1)}%
                        ${threatLevel ? `🚨 ${threatLevel.severity}` : ''}
                        <button onclick="killProcess(${p.pid})" style="margin-left:10px; background:#e74c3c; color:white; border:none; padding:2px 8px; border-radius:3px; cursor:pointer;">
                            Kill
                        </button>
                        <button onclick="showProcessDetails(${p.pid})" style="margin-left:5px; background:#3498db; color:white; border:none; padding:2px 8px; border-radius:3px; cursor:pointer;">
                            Info
                        </button>
                    </span>
                `;
                list.appendChild(li);
            });
        }
        
        /* =====================
           UPDATE CHARTS
        ====================== */
        cpuChart.update();
        ramChart.update();
        securityChart.update();
        
    } catch(err){
        console.log("System Error:", err);
    }
}

/* =========================
   KILL PROCESS (SAFE)
========================= */
async function killProcess(pid){
    if(!confirm(`Terminate process ${pid}?`)) return;
    
    try{
        let res = await fetch('/kill', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({pid})
        });
        let data = await res.json();
        alert(data.status);
        update();
    } catch(err){
        console.log("Kill failed:", err);
        alert("Failed to terminate process");
    }
}

/* =========================
   PROCESS DETAILS
========================= */
async function showProcessDetails(pid){
    try{
        let res = await fetch(`/process/${pid}`);
        let data = await res.json();
        
        if(data.error){
            alert(data.error);
            return;
        }
        
        alert(`
Process: ${data.name}
PID: ${data.pid}
Memory: ${JSON.stringify(data.memory, null, 2)}
CPU: ${data.cpu_percent}%
Created: ${data.create_time}
Connections: ${data.connections ? data.connections.length : 0}
        `);
    } catch(err){
        console.log("Process details error:", err);
    }
}

/* =========================
   FREE MEMORY ACTION
========================= */
async function freeMemory(){
    try{
        let res = await fetch('/free-memory', {
            method: 'POST',
            headers: {'Content-Type':'application/json'}
        });
        let data = await res.json();
        alert(data.status);
        update();
    } catch(err){
        console.log("Memory error:", err);
    }
}

/* =========================
   EXPORT DATA
========================= */
function exportData(){
    let data = {
        timestamp: new Date().toISOString(),
        history: rawDataHistory,
        summary: {
            avg_cpu: cpuData.length > 0 ? cpuData.reduce((a,b) => a+b, 0) / cpuData.length : 0,
            avg_ram: ramData.length > 0 ? ramData.reduce((a,b) => a+b, 0) / ramData.length : 0,
            avg_security: securityData.length > 0 ? securityData.reduce((a,b) => a+b, 0) / securityData.length : 0
        }
    };
    
    let blob = new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'});
    let url = URL.createObjectURL(blob);
    let a = document.createElement('a');
    a.href = url;
    a.download = `system_data_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

/* =========================
   AUTO START
========================= */
window.onload = function(){
    update();
    setInterval(update, 3000);
};