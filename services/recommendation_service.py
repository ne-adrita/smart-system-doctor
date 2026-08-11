"""Rule-based recommendation engine.

Recommendations carry a severity, a title, a description and a concrete
action so the dashboard can present clear guidance.
"""
from models.schemas import Recommendation


def build_recommendations(health, security, disk, predictions=None):
    """Generate recommendations from the latest analysis snapshot."""
    recs = []

    # --- Memory ----------------------------------------------------------
    for f in health.factors:
        if f.factor == "RAM" and f.impact <= -30:
            recs.append(Recommendation(
                severity="High",
                title="High Memory Usage",
                description="RAM usage is critically high.",
                action="Close unused applications or inspect the top memory-consuming processes.",
            ))
        elif f.factor == "RAM" and f.impact <= -12:
            recs.append(Recommendation(
                severity="Medium",
                title="Elevated Memory Usage",
                description="RAM usage is above 60%.",
                action="Check for memory leaks in open applications.",
            ))
        # --- CPU -----------------------------------------------------------
        if f.factor == "CPU" and f.impact <= -30:
            recs.append(Recommendation(
                severity="High",
                title="High CPU Usage",
                description="CPU usage is critically high.",
                action="Inspect the top CPU-consuming processes in the Process Monitor.",
            ))
        elif f.factor == "CPU" and f.impact <= -12:
            recs.append(Recommendation(
                severity="Medium",
                title="Elevated CPU Usage",
                description="CPU usage is above 60%.",
                action="Monitor running processes for unexpected load.",
            ))
        # --- Disk ----------------------------------------------------------
        if f.factor == "Disk" and f.impact <= -20:
            recs.append(Recommendation(
                severity="High",
                title="Disk Space Critically Low",
                description="Disk usage is critically high.",
                action="Free up disk space - consider clearing temporary files.",
            ))
        elif f.factor == "Disk" and f.impact <= -10:
            recs.append(Recommendation(
                severity="Medium",
                title="Disk Space Running Low",
                description="Disk usage is above 70%.",
                action="Review large files and consider cleaning up.",
            ))

    # --- Security ----------------------------------------------------------
    if security and security.get("score", 100) < 60:
        recs.append(Recommendation(
            severity="High",
            title="Security Posture Degraded",
            description="Multiple suspicious findings or exposed services detected.",
            action="Review each flagged process in the Security tab and verify its "
                   "executable path and network connections.",
        ))
    if security and security.get("score", 100) < 80:
        recs.append(Recommendation(
            severity="Medium",
            title="Review Security Findings",
            description="A few heuristic findings were raised.",
            action="Inspect the flagged processes - heuristics may produce false positives.",
        ))

    exposed_ports = [p for p in (security or {}).get("ports", []) if p.exposed]
    if len(exposed_ports) >= 3:
        recs.append(Recommendation(
            severity="Medium",
            title="Several Externally Listening Services",
            description=f"{len(exposed_ports)} service(s) listen on all network interfaces.",
            action="Review whether each service must be reachable from the network.",
        ))

    # --- Predictions -------------------------------------------------------
    if predictions and predictions.get("available"):
        for resource in ("cpu", "ram", "disk"):
            data = predictions.get(resource)
            if data and data.get("risk") == "High":
                recs.append(Recommendation(
                    severity="Medium",
                    title=f"{resource.upper()} Forecast Rising",
                    description=f"{resource.upper()} is trending upward; near-term "
                                f"forecast {data.get('range_low')}-{data.get('range_high')}%.",
                    action="Take preventive action now to avoid hitting resource limits.",
                ))

    if not recs:
        recs.append(Recommendation(
            severity="Info",
            title="All Systems Normal",
            description="No pressing issues detected.",
            action="No action needed right now.",
        ))

    return [r.to_dict() for r in recs]
