import socket

# =========================
# RISK CONFIGURATION
# =========================
RISKY_PORTS = [21, 22, 23, 80, 443, 445, 3389, 8080]

SUSPICIOUS_KEYWORDS = [
    "miner",
    "hack",
    "virus",
    "trojan",
    "unknown",
    "keylogger"
]


# =========================
# OPEN PORT CHECKER
# =========================
def check_open_ports():

    open_ports = []

    for port in RISKY_PORTS:

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.3)

        try:
            result = s.connect_ex(('127.0.0.1', port))

            if result == 0:
                open_ports.append(port)

        except:
            pass

        finally:
            s.close()

    return open_ports


# =========================
# SUSPICIOUS PROCESS DETECTION
# =========================
def detect_suspicious_process(processes):

    threats = []

    for p in processes:

        name = (p.get("name") or "").lower()

        for keyword in SUSPICIOUS_KEYWORDS:
            if keyword in name:
                threats.append({
                    "pid": p.get("pid"),
                    "name": p.get("name"),
                    "reason": f"Matched keyword: {keyword}"
                })

    return threats


# =========================
# SECURITY SCORE ENGINE
# =========================
def security_score(open_ports, threats):

    score = 100

    score -= len(open_ports) * 10
    score -= len(threats) * 20

    return max(score, 0)


# =========================
# SECURITY STATUS LABEL
# =========================
def security_status(score):

    if score >= 80:
        return "SAFE"
    elif score >= 50:
        return "RISK"
    else:
        return "DANGEROUS"