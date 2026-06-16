# =========================
# SYSTEM HEALTH SCORE ENGINE
# =========================

def system_health_score(cpu, ram, disk):

    score = 100

    # CPU weight
    if cpu > 80:
        score -= 25
    elif cpu > 60:
        score -= 10

    # RAM weight
    if ram > 80:
        score -= 30
    elif ram > 60:
        score -= 15

    # DISK weight
    if disk > 85:
        score -= 20
    elif disk > 70:
        score -= 10

    return max(score, 0)


# =========================
# HEALTH STATUS LABEL
# =========================
def system_status(score):

    if score >= 80:
        return "GOOD"
    elif score >= 50:
        return "WARNING"
    else:
        return "CRITICAL"