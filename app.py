from flask import Flask, render_template, jsonify, request
import psutil

from modules.analyzer import system_health_score, system_status
from modules.security import (
    check_open_ports,
    detect_suspicious_process,
    security_score,
    security_status
)

app = Flask(__name__)


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/data')
def data():

    # =====================
    # SYSTEM METRICS
    # =====================
    cpu = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent

    # =====================
    # PROCESS LIST
    # =====================
    processes = []

    for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
        try:
            processes.append(p.info)
        except:
            pass

    processes = sorted(
        processes,
        key=lambda x: x['memory_percent'] or 0,
        reverse=True
    )

    top_processes = processes[:7]

    # =====================
    # SECURITY MODULE
    # =====================
    open_ports = check_open_ports()
    threats = detect_suspicious_process(top_processes)

    sec_score = security_score(open_ports, threats)
    sec_state = security_status(sec_score)

    # =====================
    # OS HEALTH MODULE
    # =====================
    health_score = system_health_score(cpu, ram, disk)
    health_state = system_status(health_score)

    # =====================
    # RESPONSE JSON
    # =====================
    return jsonify({
        "cpu": cpu,
        "ram": ram,
        "disk": disk,

        "processes": top_processes,

        "health_score": health_score,
        "health_state": health_state,

        "security_score": sec_score,
        "security_state": sec_state,

        "open_ports": open_ports,
        "threats": threats
    })


# =====================
# KILL PROCESS (OS action)
# =====================
@app.route('/kill', methods=['POST'])
def kill():

    pid = request.json.get("pid")

    try:
        p = psutil.Process(pid)
        p.terminate()

        return jsonify({"status": "Process terminated"})
    except:
        return jsonify({"status": "Failed to terminate"})


# =====================
# MEMORY ACTION (SIMULATED SAFE)
# =====================
@app.route('/free-memory')
def free_memory():

    # safe simulation (no system damage)
    return jsonify({
        "status": "Memory optimization completed (simulated)"
    })


if __name__ == '__main__':
    app.run(debug=True)