import sqlite3
from datetime import datetime

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect("system_logs.db")
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT,
            cpu REAL,
            ram REAL,
            disk REAL,
            health INTEGER,
            security INTEGER,
            process_count INTEGER
        )
    """)
    
    conn.commit()
    conn.close()

def save_log(cpu, ram, disk, health, security, process_count):
    """Save system metrics to database"""
    conn = sqlite3.connect("system_logs.db")
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO logs (time, cpu, ram, disk, health, security, process_count)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        cpu, ram, disk, health, security, process_count
    ))
    
    conn.commit()
    conn.close()

def get_history(limit=50):
    """Retrieve historical data from database"""
    conn = sqlite3.connect("system_logs.db")
    c = conn.cursor()
    
    c.execute("""
        SELECT time, cpu, ram, disk, health, security, process_count
        FROM logs
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    
    rows = c.fetchall()
    conn.close()
    
    return rows

def get_statistics():
    """Get statistical analysis from historical data"""
    conn = sqlite3.connect("system_logs.db")
    c = conn.cursor()
    
    c.execute("""
        SELECT 
            AVG(cpu) as avg_cpu,
            AVG(ram) as avg_ram,
            AVG(health) as avg_health,
            AVG(security) as avg_security,
            MIN(cpu) as min_cpu,
            MAX(cpu) as max_cpu,
            COUNT(*) as total_records
        FROM logs
    """)
    
    stats = c.fetchone()
    conn.close()
    
    return {
        'avg_cpu': round(stats[0], 2) if stats[0] else 0,
        'avg_ram': round(stats[1], 2) if stats[1] else 0,
        'avg_health': round(stats[2], 2) if stats[2] else 0,
        'avg_security': round(stats[3], 2) if stats[3] else 0,
        'min_cpu': round(stats[4], 2) if stats[4] else 0,
        'max_cpu': round(stats[5], 2) if stats[5] else 0,
        'total_records': stats[6] if stats[6] else 0
    }