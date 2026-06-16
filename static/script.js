/* =========================
   OS EXPLANATION ENGINE
========================= */
function explain(cpu, ram){

    if(cpu > 80){
        return "High CPU usage → process scheduling pressure";
    }

    if(ram > 80){
        return "High memory usage → memory allocation pressure";
    }

    return "System stable → normal OS resource resource usage";
}

/* =========================
   DATA STORAGE (CHART)
========================= */
let cpuData = [];
let ramData = [];
let labels = [];

/* =========================
   INIT CHARTS (CPU + RAM)
========================= */
const cpuChart = new Chart(document.getElementById('cpuChart'), {
    type: 'line',
    data: {
        labels: labels,
        datasets: [{
            label: 'CPU %',
            data: cpuData,
            borderColor: 'red',
            fill: false,
            tension: 0.3
        }]
    }
});

const ramChart = new Chart(document.getElementById('ramChart'), {
    type: 'line',
    data: {
        labels: labels,
        datasets: [{
            label: 'RAM %',
            data: ramData,
            borderColor: 'blue',
            fill: false,
            tension: 0.3
        }]
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

        if(labels.length > 10){
            labels.shift();
            cpuData.shift();
            ramData.shift();
        }

        /* =====================
           SYSTEM INFO UI
        ====================== */
        document.getElementById("cpu").innerText = data.cpu + "%";
        document.getElementById("ram").innerText = data.ram + "%";
        document.getElementById("disk").innerText = data.disk + "%";

        document.getElementById("health").innerText =
            data.health_score + "/100";

        document.getElementById("healthState").innerText =
            data.health_state;

        document.getElementById("security").innerText =
            data.security_score + "/100";

        document.getElementById("securityState").innerText =
            data.security_state;

        /* =====================
           OS EXPLANATION BOX
        ====================== */
        document.getElementById("osExplain").innerText =
            explain(data.cpu, data.ram);

        /* =====================
           PROCESS LIST UI
        ====================== */
        let list = document.getElementById("processList");

        if(list){
            list.innerHTML = "";

            data.processes.forEach(p => {

                let li = document.createElement("li");

                li.innerHTML = `
                    ${p.name || "Unknown"}
                    (${(p.memory_percent || 0).toFixed(1)}%)
                    <button onclick="kill(${p.pid})">Kill</button>
                `;

                list.appendChild(li);
            });
        }

        /* =====================
           UPDATE CHARTS
        ====================== */
        cpuChart.update();
        ramChart.update();

    }
    catch(err){
        console.log("System Error:", err);
    }
}

/* =========================
   KILL PROCESS (SAFE)
========================= */
async function kill(pid){

    try{
        await fetch('/kill', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({pid})
        });

        update(); // refresh list after kill
    }
    catch(err){
        console.log("Kill failed:", err);
    }
}

/* =========================
   FREE MEMORY ACTION
========================= */
async function freeMemory(){

    try{
        let res = await fetch('/free-memory');
        let data = await res.json();

        alert(data.status);
    }
    catch(err){
        console.log("Memory error:", err);
    }
}

/* =========================
   AUTO START
========================= */
window.onload = function(){
    update();
    setInterval(update, 3000);
};