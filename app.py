from flask import Flask, render_template, jsonify, request, send_file
import psutil
import json
from datetime import datetime
import threading
import time

from modules.analyzer import system_health_score, system_status, get_health_details
from modules.security import (
    check_open_ports,
    detect_suspicious_process,
    security_score,
    security_status,
    SecurityAnalyzer,
    get_security_details
)
from database import init_db, save_log, get_history, get_statistics
from report_generator import generate_system_report

app = Flask(__name__)

# Initialize database
init_db()

# =========================
# CACHE FOR PREDICTIVE ANALYTICS
# =========================
system_cache = {
    'history': [],
    'anomalies': [],
    'last_update': None
}

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
    
    # Network metrics
    net_io = psutil.net_io_counters()
    network = {
        'bytes_sent': net_io.bytes_sent,
        'bytes_recv': net_io.bytes_recv,
        'packets_sent': net_io.packets_sent,
        'packets_recv': net_io.packets_recv
    }
    
    # Process list with risk classification
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent', 'exe', 'username']):
        try:
            p_info = p.info
            # Add risk classification
            mem = p_info.get('memory_percent', 0)
            if mem > 20:
                p_info['risk'] = "HIGH"
            elif mem > 10:
                p_info['risk'] = "MEDIUM"
            else:
                p_info['risk'] = "LOW"
            processes.append(p_info)
        except:
            pass
    
    processes = sorted(
        processes,
        key=lambda x: x.get('memory_percent', 0) or 0,
        reverse=True
    )
    top_processes = processes[:10]
    process_count = len(psutil.pids())
    
    # =====================
    # ENHANCED SECURITY MODULE
    # =====================
    security_data = get_security_details()
    open_ports = security_data['ports']['ports']
    threats = security_data['threats']['threats']
    sec_score = security_data['score']['score']
    sec_state = security_status(sec_score)
    
    # =====================
    # ENHANCED HEALTH MODULE
    # =====================
    health_details = get_health_details(cpu, ram, disk)
    health_score = health_details['score']
    health_state = system_status(health_score)
    
    # =====================
    # PROCESS RISK CLASSIFICATION
    # =====================
    risk_classification = {
        'high': [p for p in top_processes if p.get('risk') == 'HIGH'],
        'medium': [p for p in top_processes if p.get('risk') == 'MEDIUM'],
        'low': [p for p in top_processes if p.get('risk') == 'LOW']
    }
    
    # =====================
    # SYSTEM DIAGNOSTICS
    # =====================
    diagnostics = generate_diagnostics(cpu, ram, disk, security_data, health_details)
    
    # =====================
    # PREDICTIVE ANALYTICS
    # =====================
    predictions = health_details.get('predictions', {})
    
    # =====================
    # SAVE TO DATABASE
    # =====================
    save_log(cpu, ram, disk, health_score, sec_score, process_count)
    
    # =====================
    # RESPONSE JSON
    # =====================
    return jsonify({
        "cpu": cpu,
        "ram": ram,
        "disk": disk,
        "network": network,
        "timestamp": datetime.now().isoformat(),
        
        "processes": top_processes,
        "process_count": process_count,
        "risk_classification": risk_classification,
        
        "health_score": health_score,
        "health_state": health_state['status'],
        "health_icon": health_state['icon'],
        "health_color": health_state['color'],
        "health_issues": health_details.get('issues', []),
        "health_predictions": predictions,
        
        "security_score": sec_score,
        "security_state": sec_state['status'],
        "security_icon": sec_state['icon'],
        "security_color": sec_state['color'],
        "security_warnings": security_data['score'].get('warnings', []),
        "security_ports": open_ports,
        "security_threats": threats,
        "security_risk_factors": security_data['score'].get('risk_factors', {}),
        
        "diagnostics": diagnostics,
        
        # Legacy compatibility
        "open_ports": open_ports,
        "threats": threats
    })

def generate_diagnostics(cpu, ram, disk, security_data, health_details):
    """Generate comprehensive system diagnostics"""
    diagnostics = {
        'performance': [],
        'security': [],
        'storage': [],
        'recommendations': []
    }
    
    # Performance diagnostics
    if cpu > 80:
        diagnostics['performance'].append({
            'severity': 'HIGH',
            'issue': 'CPU overloaded',
            'details': f'Current usage: {cpu}%',
            'action': 'Close resource-intensive applications'
        })
    elif cpu > 60:
        diagnostics['performance'].append({
            'severity': 'MEDIUM',
            'issue': 'High CPU usage',
            'details': f'Current usage: {cpu}%',
            'action': 'Monitor running processes'
        })
    
    if ram > 80:
        diagnostics['performance'].append({
            'severity': 'HIGH',
            'issue': 'Memory exhaustion',
            'details': f'Current usage: {ram}%',
            'action': 'Close unnecessary applications or add more RAM'
        })
    elif ram > 60:
        diagnostics['performance'].append({
            'severity': 'MEDIUM',
            'issue': 'Elevated memory usage',
            'details': f'Current usage: {ram}%',
            'action': 'Check for memory leaks'
        })
    
    # Security diagnostics
    if security_data['score']['score'] < 60:
        diagnostics['security'].append({
            'severity': 'HIGH',
            'issue': 'System security compromised',
            'details': security_data['score'].get('warnings', ['Security risks detected'])[0],
            'action': 'Immediate security investigation required'
        })
    
    # Storage diagnostics
    if disk > 90:
        diagnostics['storage'].append({
            'severity': 'HIGH',
            'issue': 'Disk critically full',
            'details': f'Available: {100-disk}%',
            'action': 'Free up disk space immediately'
        })
    elif disk > 80:
        diagnostics['storage'].append({
            'severity': 'MEDIUM',
            'issue': 'Low disk space',
            'details': f'Available: {100-disk}%',
            'action': 'Consider clearing temporary files'
        })
    
    # Recommendations
    if health_details.get('issues'):
        for issue in health_details['issues']:
            if 'CPU' in issue and cpu > 70:
                diagnostics['recommendations'].append({
                    'priority': 'HIGH' if cpu > 80 else 'MEDIUM',
                    'text': f'Reduce CPU load: {issue}',
                    'action': 'Terminate heavy processes'
                })
            elif 'Memory' in issue and ram > 70:
                diagnostics['recommendations'].append({
                    'priority': 'HIGH' if ram > 80 else 'MEDIUM',
                    'text': f'Free memory: {issue}',
                    'action': 'Close memory-intensive applications'
                })
    
    return diagnostics

@app.route('/kill', methods=['POST'])
def kill():
    pid = request.json.get("pid")
    force = request.json.get("force", False)
    
    try:
        p = psutil.Process(pid)
        if force:
            p.kill()
        else:
            p.terminate()
        
        gone, alive = psutil.wait_procs([p], timeout=3)
        
        if alive:
            return jsonify({"status": "Process still running"})
        return jsonify({"status": "Process terminated successfully"})
    except psutil.NoSuchProcess:
        return jsonify({"status": "Process not found"})
    except Exception as e:
        return jsonify({"status": f"Failed to terminate: {str(e)}"})

@app.route('/free-memory', methods=['POST'])
def free_memory():
    try:
        import gc
        gc.collect()
        
        return jsonify({
            "status": "Memory optimization completed",
            "freed_mb": 0,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"status": f"Memory optimization failed: {str(e)}"})

@app.route('/report', methods=['GET'])
def generate_report():
    """Generate and download PDF report"""
    try:
        # Get current system data
        cpu = psutil.cpu_percent(interval=0.5)
        ram = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        
        # Get security data
        security_data = get_security_details()
        threats = security_data['threats']['threats'][:5]
        
        # Get health data
        health_details = get_health_details(cpu, ram, disk)
        health_score = health_details['score']
        health_state = system_status(health_score)
        
        # Prepare report data
        report_data = {
            'cpu': cpu,
            'ram': ram,
            'disk': disk,
            'health_score': health_score,
            'health_state': health_state['status'],
            'security_score': security_data['score']['score'],
            'security_state': security_data['status']['status'],
            'threats': threats,
            'process_count': len(psutil.pids())
        }
        
        # Generate PDF
        filename = generate_system_report(report_data)
        
        return send_file(filename, as_attachment=True, download_name=filename)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/history')
def get_history_data():
    """Get historical data for charts"""
    limit = request.args.get('limit', 50, type=int)
    history = get_history(limit)
    
    return jsonify({
        'data': [{
            'time': row[0],
            'cpu': row[1],
            'ram': row[2],
            'disk': row[3],
            'health': row[4],
            'security': row[5],
            'processes': row[6]
        } for row in history]
    })

@app.route('/statistics')
def get_stats():
    """Get statistical analysis"""
    stats = get_statistics()
    return jsonify(stats)

@app.route('/system-info')
def system_info():
    """Get detailed system information"""
    info = {
        'cpu_count': psutil.cpu_count(),
        'cpu_freq': psutil.cpu_freq()._asdict() if psutil.cpu_freq() else {},
        'total_ram': psutil.virtual_memory().total,
        'total_disk': psutil.disk_usage('/').total,
        'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat(),
        'os': psutil.os.name,
        'platform': psutil.sys.platform
    }
    return jsonify(info)

@app.route('/process/<int:pid>')
def process_details(pid):
    """Get detailed process information"""
    try:
        p = psutil.Process(pid)
        details = {
            'pid': p.pid,
            'name': p.name(),
            'exe': p.exe(),
            'cmdline': p.cmdline(),
            'memory': p.memory_info()._asdict(),
            'cpu_percent': p.cpu_percent(),
            'connections': [c._asdict() for c in p.connections()],
            'open_files': [f.path for f in p.open_files()],
            'create_time': datetime.fromtimestamp(p.create_time()).isoformat()
        }
        return jsonify(details)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)