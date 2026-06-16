import psutil

def get_system_info():

    processes = []

    for p in psutil.process_iter(['pid','name','memory_percent']):
        try:
            processes.append(p.info)
        except:
            pass

    processes = sorted(
        processes,
        key=lambda x: x['memory_percent'] or 0,
        reverse=True
    )

    return {
        "cpu": psutil.cpu_percent(interval=1),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "top_processes": processes[:5]
    }