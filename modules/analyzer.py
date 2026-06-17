# =========================
# ADVANCED SYSTEM HEALTH SCORE ENGINE
# =========================
from collections import deque
import time
from collections import deque

class HealthAnalyzer:
    def __init__(self):
        self.history = {
            'cpu': deque(maxlen=60),
            'ram': deque(maxlen=60),
            'disk': deque(maxlen=60)
        }
        self.trends = {}
    
    def update_history(self, cpu, ram, disk):
        self.history['cpu'].append(cpu)
        self.history['ram'].append(ram)
        self.history['disk'].append(disk)
    
    def calculate_trend(self, data):
        if len(data) < 5:
            return "stable"
        
        recent = list(data)[-5:]
        avg_change = sum(recent[i] - recent[i-1] for i in range(1, len(recent))) / len(recent)
        
        if avg_change > 5:
            return "increasing"
        elif avg_change < -5:
            return "decreasing"
        return "stable"
    
    def predict_pressure(self):
        predictions = {}
        
        # CPU prediction
        if len(self.history['cpu']) >= 10:
            cpu_trend = self.calculate_trend(self.history['cpu'])
            cpu_avg = sum(self.history['cpu']) / len(self.history['cpu'])
            predictions['cpu'] = {
                'trend': cpu_trend,
                'predicted_peak': min(100, cpu_avg + 15 if cpu_trend == "increasing" else cpu_avg),
                'risk': cpu_trend == "increasing" and cpu_avg > 60
            }
        
        # RAM prediction
        if len(self.history['ram']) >= 10:
            ram_trend = self.calculate_trend(self.history['ram'])
            ram_avg = sum(self.history['ram']) / len(self.history['ram'])
            predictions['ram'] = {
                'trend': ram_trend,
                'predicted_peak': min(100, ram_avg + 20 if ram_trend == "increasing" else ram_avg),
                'risk': ram_trend == "increasing" and ram_avg > 60
            }
        
        return predictions
    
    def system_health_score(self, cpu, ram, disk):
        score = 100
        issues = []
        
        # CPU analysis with trend awareness
        if cpu > 90:
            score -= 30
            issues.append("CPU critically overloaded")
        elif cpu > 80:
            score -= 20
            issues.append("CPU high usage")
        elif cpu > 60:
            score -= 10
            issues.append("CPU moderate usage")
        
        # RAM analysis with trend awareness
        if ram > 90:
            score -= 35
            issues.append("Memory critically exhausted")
        elif ram > 80:
            score -= 25
            issues.append("Memory high usage")
        elif ram > 60:
            score -= 12
            issues.append("Memory moderate usage")
        
        # Disk analysis
        if disk > 95:
            score -= 25
            issues.append("Disk critically full")
        elif disk > 85:
            score -= 15
            issues.append("Disk nearly full")
        elif disk > 70:
            score -= 8
            issues.append("Disk usage elevated")
        
        # Trend penalties
        trends = self.predict_pressure()
        for resource, data in trends.items():
            if data.get('risk', False):
                score -= 10
                issues.append(f"{resource.upper()} usage trending upward")
        
        # Update history
        self.update_history(cpu, ram, disk)
        
        return {
            'score': max(score, 0),
            'issues': issues,
            'trends': trends,
            'predictions': self.predict_pressure()
        }
    
    def system_status(self, score):
        if score >= 80:
            return {
                'status': "GOOD",
                'icon': "✅",
                'color': "green",
                'description': "System operating optimally"
            }
        elif score >= 60:
            return {
                'status': "WARNING",
                'icon': "⚠️",
                'color': "yellow",
                'description': "Performance degradation detected"
            }
        else:
            return {
                'status': "CRITICAL",
                'icon': "🚨",
                'color': "red",
                'description': "Immediate action required"
            }

# Initialize global analyzer
health_analyzer = HealthAnalyzer()

def system_health_score(cpu, ram, disk):
    result = health_analyzer.system_health_score(cpu, ram, disk)
    return result['score']

def get_health_details(cpu, ram, disk):
    return health_analyzer.system_health_score(cpu, ram, disk)

def system_status(score):
    return health_analyzer.system_status(score)