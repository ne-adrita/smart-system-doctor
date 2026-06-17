import socket
import re
from collections import defaultdict, deque  # ← Added deque here
import psutil
# =========================
# ADVANCED RISK CONFIGURATION
# =========================
RISKY_PORTS = {
    21: "FTP (unencrypted file transfer)",
    22: "SSH (potential brute force target)",
    23: "Telnet (insecure remote access)",
    80: "HTTP (unencrypted web)",
    443: "HTTPS (usually safe)",
    445: "SMB (vulnerable to ransomware)",
    3389: "RDP (remote desktop vulnerability)",
    8080: "HTTP Proxy (common attack vector)",
    3306: "MySQL (database exposure)",
    5432: "PostgreSQL (database exposure)",
    27017: "MongoDB (database exposure)",
    6379: "Redis (cache exposure)"
}

SUSPICIOUS_KEYWORDS = [
    "miner", "hack", "virus", "trojan", "keylogger",
    "spyware", "ransomware", "crypt", "backdoor",
    "exploit", "malware", "worm", "rootkit", "adware"
]

# Behavioral patterns for advanced detection
BEHAVIORAL_PATTERNS = {
    'high_network_io': ['chrome', 'firefox', 'edge', 'browser'],
    'suspicious_paths': ['/tmp/', '/var/tmp/', 'C:\\Users\\Public\\'],
    'elevated_privileges': ['SYSTEM', 'root', 'Administrator']
}

class SecurityAnalyzer:
    def __init__(self):
        self.threat_history = deque(maxlen=20)
        self.detected_patterns = {}
    
    def check_open_ports(self):
        """Enhanced port scanning with service identification"""
        open_ports = []
        port_details = {}
        
        for port, service in RISKY_PORTS.items():
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.5)
            
            try:
                result = s.connect_ex(('127.0.0.1', port))
                if result == 0:
                    open_ports.append(port)
                    port_details[port] = service
            except:
                pass
            finally:
                s.close()
        
        return {
            'ports': open_ports,
            'details': port_details,
            'count': len(open_ports),
            'risk_level': "HIGH" if len(open_ports) > 3 else "MEDIUM" if len(open_ports) > 0 else "LOW"
        }
    
    def detect_suspicious_process(self, processes):
        """Advanced process detection with behavioral analysis"""
        threats = []
        suspicious_scores = defaultdict(int)
        
        for p in processes:
            name = (p.get("name") or "").lower()
            pid = p.get("pid")
            mem_percent = p.get("memory_percent", 0)
            cpu_percent = p.get("cpu_percent", 0)
            
            threat_score = 0
            reasons = []
            
            # Keyword matching
            for keyword in SUSPICIOUS_KEYWORDS:
                if keyword in name:
                    threat_score += 25
                    reasons.append(f"Matched keyword: {keyword}")
            
            # Behavioral analysis
            if mem_percent and mem_percent > 50:
                threat_score += 20
                reasons.append(f"Extreme memory usage: {mem_percent:.1f}%")
            
            if cpu_percent and cpu_percent > 70:
                threat_score += 15
                reasons.append(f"High CPU usage: {cpu_percent:.1f}%")
            
            # Path analysis (if available)
            if 'exe' in p and p['exe']:
                exe_path = p['exe'].lower()
                for pattern in BEHAVIORAL_PATTERNS['suspicious_paths']:
                    if pattern.lower() in exe_path:
                        threat_score += 20
                        reasons.append(f"Running from suspicious directory")
            
            # Name similarity to known processes (heuristic)
            known_services = ['system', 'svchost', 'explorer', 'wininit', 'kernel', 'launchd']
            if len(name) > 0 and name not in known_services:
                # Check if it looks like a random name
                if re.match(r'^[a-z0-9]{8,}$', name):
                    threat_score += 15
                    reasons.append("Randomized process name pattern")
            
            if threat_score > 0:
                threats.append({
                    "pid": pid,
                    "name": p.get("name"),
                    "score": threat_score,
                    "reasons": reasons,
                    "severity": "HIGH" if threat_score > 40 else "MEDIUM" if threat_score > 20 else "LOW"
                })
        
        # Sort by threat score
        threats.sort(key=lambda x: x['score'], reverse=True)
        
        return {
            'threats': threats[:10],
            'count': len(threats),
            'highest_threat': threats[0] if threats else None,
            'risk_level': "DANGEROUS" if len(threats) > 3 else "RISKY" if len(threats) > 0 else "SAFE"
        }
    
    def security_score(self, open_ports_data, threats_data):
        """Enhanced security scoring with weighted analysis"""
        score = 100
        warnings = []
        
        # Open ports penalty
        port_count = open_ports_data['count']
        if port_count > 5:
            score -= 30
            warnings.append(f"Multiple open ports ({port_count}) exposed")
        elif port_count > 2:
            score -= 20
            warnings.append(f"Several open ports ({port_count})")
        elif port_count > 0:
            score -= 10
            warnings.append(f"Open ports present ({port_count})")
        
        # Check for dangerous ports
        for port in open_ports_data['ports']:
            if port in [445, 3389, 22, 23]:
                score -= 10
                warnings.append(f"High-risk port {port} open")
        
        # Suspicious process penalty
        threat_count = threats_data['count']
        if threat_count > 5:
            score -= 40
            warnings.append(f"Multiple threats detected ({threat_count})")
        elif threat_count > 2:
            score -= 25
            warnings.append(f"Several suspicious processes ({threat_count})")
        elif threat_count > 0:
            score -= 15
            warnings.append(f"Suspicious processes present ({threat_count})")
        
        # High severity threats
        high_severity = sum(1 for t in threats_data['threats'] if t['severity'] == "HIGH")
        if high_severity > 0:
            score -= high_severity * 10
            warnings.append(f"High severity threats: {high_severity}")
        
        return {
            'score': max(score, 0),
            'warnings': warnings,
            'risk_factors': {
                'open_ports': port_count,
                'suspicious_processes': threat_count,
                'high_severity_threats': high_severity
            }
        }
    
    def security_status(self, score):
        if score >= 80:
            return {
                'status': "SAFE",
                'icon': "🛡️",
                'color': "green",
                'description': "System appears secure"
            }
        elif score >= 60:
            return {
                'status': "RISK",
                'icon': "⚠️",
                'color': "yellow",
                'description': "Security concerns detected"
            }
        else:
            return {
                'status': "DANGEROUS",
                'icon': "🚨",
                'color': "red",
                'description': "Immediate security action required"
            }

# Initialize global analyzer
security_analyzer = SecurityAnalyzer()

# Legacy functions for backward compatibility
def check_open_ports():
    result = security_analyzer.check_open_ports()
    return result['ports']

def detect_suspicious_process(processes):
    result = security_analyzer.detect_suspicious_process(processes)
    return result['threats']

def security_score(open_ports, threats):
    # Convert to new format
    ports_data = {'ports': open_ports, 'count': len(open_ports), 'details': {}}
    threats_data = {'threats': threats, 'count': len(threats)}
    result = security_analyzer.security_score(ports_data, threats_data)
    return result['score']

def security_status(score):
    return security_analyzer.security_status(score)

# New enhanced functions
def get_security_details():
    """Get comprehensive security analysis"""
    ports_data = security_analyzer.check_open_ports()
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent', 'exe', 'username']):
        try:
            processes.append(p.info)
        except:
            pass
    threats_data = security_analyzer.detect_suspicious_process(processes)
    score_data = security_analyzer.security_score(ports_data, threats_data)
    
    return {
        'ports': ports_data,
        'threats': threats_data,
        'score': score_data,
        'status': security_analyzer.security_status(score_data['score'])
    }