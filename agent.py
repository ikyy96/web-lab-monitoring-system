import psutil
import time
import socket
import json
import platform
import getpass
import subprocess
import os
import paho.mqtt.client as mqtt
from datetime import datetime

# GPU Monitoring imports
try:
    import pynvml
    PYNVML_AVAILABLE = True
except:
    PYNVML_AVAILABLE = False

try:
    import win32com.client
    WIN32_AVAILABLE = True
except:
    WIN32_AVAILABLE = False

# --- KONFIGURASI ---
# --- KONFIGURASI BARU (MENGGUNAKAN CLOUDFLARE WEBSOCKET) ---
HOSTNAME = socket.gethostname()
TOPIC = f"lab/monitoring/{HOSTNAME}"
# Menggunakan subdomain khusus WebSocket yang diarahkan oleh Cloudflare
BROKER_URL = "ws-mqtt.ikyypantau.my.id" 
PORT = 443                            # Wajib port 443 untuk traffic HTTPS/WSS Cloudflare
PING_TARGET = "8.8.8.8"

CPU_THREADS = psutil.cpu_count(logical=True)
CPU_CORES = psutil.cpu_count(logical=False)


def get_cpu_name():
    """Get detailed CPU name with multiple fallback methods"""
    sys = platform.system()

    if sys == "Windows":
        # Method 1: PowerShell (most reliable on Win 10/11)
        try:
            result = subprocess.run([
                'powershell', '-Command',
                '(Get-CimInstance Win32_Processor).Name'
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass

        # Method 2: wmic (legacy fallback)
        try:
            result = subprocess.run(['wmic', 'cpu', 'get', 'name'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
                for line in lines:
                    if line.lower() != 'name' and line:
                        return line
        except:
            pass

        # Method 3: Registry fallback
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                               r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            winreg.CloseKey(key)
            if name:
                return name.strip()
        except:
            pass

    elif sys == "Linux":
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('model name'):
                        return line.split(':')[1].strip()
        except:
            pass
        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if 'Model name' in line:
                    return line.split(':')[1].strip()
        except:
            pass

    elif sys == "Darwin":
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass

    return platform.processor() or "Unknown CPU"


CPU_NAME = get_cpu_name()
print(f"[✓] CPU Terdeteksi: {CPU_NAME}")


def init_gpu_monitoring():
    if PYNVML_AVAILABLE:
        try:
            pynvml.nvmlInit()
            return True
        except:
            return False
    return False


GPU_INITIALIZED = init_gpu_monitoring()


def get_gpu_info():
    """Get GPU information for all GPUs (NVIDIA, AMD, Intel)"""
    gpus = []

    # NVIDIA via pynvml
    if GPU_INITIALIZED:
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')

                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                memory_used_gb = round(memory_info.used / (1024**3), 2)
                memory_total_gb = round(memory_info.total / (1024**3), 2)

                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except:
                    temperature = 0

                try:
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_util = utilization.gpu
                    memory_util = utilization.memory
                except:
                    gpu_util = 0
                    memory_util = 0

                gpus.append({
                    "name": name, "type": "NVIDIA", "temperature": temperature,
                    "utilization": gpu_util, "memory_util": memory_util,
                    "memory_used_gb": memory_used_gb, "memory_total_gb": memory_total_gb
                })
        except Exception as e:
            print(f"Error getting NVIDIA GPU info: {e}")

    # AMD/Intel via WMI (Windows only)
    if WIN32_AVAILABLE and platform.system() == "Windows":
        try:
            wmi = win32com.client.GetObject("winmgmts:")
            gpu_list = wmi.InstancesOf("Win32_VideoController")
            for gpu in gpu_list:
                gpu_name = gpu.Name
                if "NVIDIA" in gpu_name and gpus:
                    continue
                adapter_ram = gpu.AdapterRAM
                memory_total_gb = round(adapter_ram / (1024**3), 1) if adapter_ram else 0
                gpus.append({
                    "name": gpu_name,
                    "type": "AMD/Intel" if "AMD" in gpu_name or "Intel" in gpu_name else "Unknown",
                    "temperature": 0, "utilization": 0, "memory_util": 0,
                    "memory_used_gb": 0, "memory_total_gb": memory_total_gb,
                    "driver_version": gpu.DriverVersion or "N/A"
                })
        except Exception as e:
            print(f"Error getting AMD/Intel GPU info: {e}")

    # Fallback: wmic
    if not gpus:
        try:
            result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]
                for line in lines:
                    name = line.strip()
                    if name:
                        gpus.append({
                            "name": name, "type": "Unknown",
                            "temperature": 0, "utilization": 0, "memory_util": 0,
                            "memory_used_gb": 0, "memory_total_gb": 0
                        })
        except:
            pass

    return gpus


def get_active_interface_via_ping():
    print("[*] Mencari interface aktif dengan akses internet...")
    is_windows = platform.system() == "Windows"
    addrs = psutil.net_if_addrs()

    for intf, addr_list in addrs.items():
        if intf.lower() in ['lo', 'loopback', 'localhost']:
            continue
        for addr in addr_list:
            if addr.family == socket.AF_INET:
                ip_address = addr.address
                try:
                    if is_windows:
                        cmd = ["ping", "-n", "1", "-w", "500", "-S", ip_address, PING_TARGET]
                    else:
                        cmd = ["ping", "-c", "1", "-W", "1", "-I", intf, PING_TARGET]
                    startupinfo = None
                    if is_windows:
                        startupinfo = subprocess.STARTUPINFO()
                        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    subprocess.check_output(cmd, startupinfo=startupinfo, stderr=subprocess.STDOUT)
                    print(f"    [+] Terpilih: {intf} ({ip_address})")
                    return intf
                except:
                    continue
    return list(addrs.keys())[0] if addrs else "eth0"


INTERFACE_NAME = get_active_interface_via_ping()


def get_interface_ip_mac(interface_name):
    addrs = psutil.net_if_addrs()
    ip_address = None
    mac_address = None
    if interface_name in addrs:
        for addr in addrs[interface_name]:
            if addr.family == socket.AF_INET and not ip_address:
                ip_address = addr.address
            if addr.family == psutil.AF_LINK and not mac_address:
                mac_address = addr.address
    return ip_address or "N/A", mac_address or "N/A"


def get_top_processes(limit=5):
    processes = []
    try:
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['name'] and pinfo['cpu_percent']:
                    processes.append((pinfo['name'], round(pinfo['cpu_percent'], 1),
                                    round(pinfo['memory_percent'] or 0, 1)))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        processes.sort(key=lambda x: x[1], reverse=True)
    except:
        pass
    return [{"name": p[0], "cpu": p[1], "mem": p[2]} for p in processes[:limit]]


def get_largest_files(limit=5):
    files = []
    is_windows = platform.system() == "Windows"
    if is_windows:
        search_paths = [
            os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Public'), 'Desktop'),
            os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Public'), 'Documents'),
            os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Public'), 'Downloads')
        ]
    else:
        search_paths = [
            os.path.expanduser('~/Desktop'),
            os.path.expanduser('~/Documents'),
            os.path.expanduser('~/Downloads')
        ]
    try:
        for path in search_paths:
            if os.path.exists(path):
                for root, dirs, filenames in os.walk(path, topdown=True):
                    dirs[:] = [d for d in dirs if not d.startswith('.') and not d.startswith('$')]
                    if len(files) >= limit * 3:
                        break
                    for f in filenames[:100]:
                        try:
                            fpath = os.path.join(root, f)
                            if os.path.isfile(fpath) and not os.path.islink(fpath):
                                size = os.path.getsize(fpath)
                                if size > 1024 * 1024:
                                    files.append((fpath, size))
                        except:
                            continue
                    if len(files) >= limit * 3:
                        break
        files.sort(key=lambda x: x[1], reverse=True)
    except:
        pass
    return [{"name": os.path.basename(f[0]), "path": f[0],
             "size_mb": round(f[1] / (1024 * 1024), 1)} for f in files[:limit]]


def get_uptime():
    try:
        uptime_seconds = time.time() - psutil.boot_time()
        return f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
    except:
        return "N/A"


def get_latency(host):
    try:
        is_windows = platform.system() == "Windows"
        cmd = ["ping", "-n" if is_windows else "-c", "1", "-w" if is_windows else "-W", "1", host]
        startupinfo = None
        if is_windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(cmd, startupinfo=startupinfo,
                                         stderr=subprocess.STDOUT, universal_newlines=True)
        if "time=" in output:
            val = output.split("time=")[1].split("ms")[0].strip()
            return int(float(val))
    except:
        return 999
    return 0


def get_net_usage(interface):
    try:
        net_io = psutil.net_io_counters(pernic=True)
        if interface in net_io:
            return net_io[interface].bytes_recv, net_io[interface].bytes_sent
    except:
        pass
    return 0, 0


# ==================== REMOTE COMMAND EXECUTION ====================
COMMAND_TIMEOUT = 15
ALLOWED_COMMANDS = {
    'tasklist': 'tasklist' if platform.system() == 'Windows' else 'ps aux',
    'ipconfig': 'ipconfig' if platform.system() == 'Windows' else 'ifconfig',
    'whoami': 'whoami',
    'systeminfo': 'systeminfo' if platform.system() == 'Windows' else 'uname -a',
    'taskkill': None,
    'shutdown': None,
    'restart': None,
    'cancel_shutdown': None,
}


def show_hacker_effect(command_name):
    """Tampilkan efek hacker dramatis di terminal target PC"""
    import sys
    is_windows = platform.system() == "Windows"
    
    SKULL = """
    ████████████████████████████████████████████████████████████████
    █                                                             █
    █   ░▒▓█▓▒░░▒▓████▓▒░     ░▒▓█▓▒░      ░▒▓██████▓▒░          █
    █   ░▒▓█▓▒░ ░▒▓█▓▒░       ░▒▓█▓▒░     ░▒▓█▓▒░                █
    █   ░▒▓█▓▒░  ░▒▓█▓▒░      ░▒▓█▓▒░     ░▒▓█▓▒░                █
    █   ░▒▓█▓▒░   ░▒▓█▓▒░     ░▒▓█▓▒░     ░▒▓█▓▒░   ░▒▓██████▓▒░  █
    █   ░▒▓█▓▒░   ░▒▓█▓▒░     ░▒▓█▓▒░     ░▒▓█▓▒░  ░▒▓█▓▒░       █
    █   ░▒▓█▓▒░  ░▒▓█▓▒░      ░▒▓█▓▒░     ░▒▓█▓▒░  ░▒▓█▓▒░       █
    █   ░▒▓█▓▒░ ░▒▓█▓▒░       ░▒▓█▓▒░     ░▒▓█▓▒░  ░▒▓█▓▒░       █
    █   ░▒▓█▓▒░ ░▒▓████▓▒░    ░▒▓█▓▒░      ░▒▓██████▓▒░           █
    █                                                             █
    ████████████████████████████████████████████████████████████████
    """
    
    HACKER_LINES = [
        "[⛔] INCOMING REMOTE COMMAND - UNAUTHORIZED ACCESS DETECTED!",
        "[⚠️] Sistem telah diakses oleh pihak ketiga!",
        "[🔓] Remote connection established from 192.168.2.2:8800",
        "[💀] Menerima perintah berbahaya: " + command_name.upper(),
        "",
        "[🛡️] Mencoba memblokir... GAGAL! Sistem keamanan telah ditembus!",
        "[⚡] Mengambil alih kendali sistem... BERHASIL!",
        "",
        "     ════════════════════════════════════════════════════",
        f"     ⚠️⚠️⚠️  PERINGATAN: PC ANDA AKAN {command_name.upper()}  ⚠️⚠️⚠️",
        "     ════════════════════════════════════════════════════",
        "",
        "     Anda memiliki 30 detik untuk menyimpan pekerjaan!",
        "     Segera tutup semua aplikasi!",
        "",
    ]
    
    # Clear screen
    os.system('cls' if is_windows else 'clear')
    
    # Print skull
    for line in SKULL.split('\n'):
        print(f"\033[91m{line}\033[0m")  # Red color
        time.sleep(0.03)
    
    time.sleep(0.5)
    
    # Print hacker lines with typing effect
    for line in HACKER_LINES:
        if line.startswith("     ═") or line.startswith("     ⚠"):
            print(f"\033[93m{line}\033[0m")  # Yellow for warning box
        elif "GAGAL" in line or "BERHASIL" in line or "ditembus" in line:
            print(f"\033[91m{line}\033[0m")  # Red for danger
        elif "PERINGATAN" in line:
            print(f"\033[93m{line}\033[0m")  # Yellow
        elif "30 detik" in line or "tutup" in line:
            print(f"\033[92m{line}\033[0m")  # Green for instructions
        else:
            print(f"\033[96m{line}\033[0m")  # Cyan for info
        time.sleep(0.15)
    
    time.sleep(1)
    
    # ==================== MATRIX RAIN - FULL SCREEN DIGITAL RAIN ====================
    import random
    import shutil
    import sys
    
    ts = shutil.get_terminal_size()
    COLS = ts.columns
    ROWS = ts.lines
    
    chars = 'アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    
    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    
    # Initialize columns with random properties
    columns = []
    for i in range(COLS):
        columns.append({
            'y': random.randint(-ROWS, 0),      # Start position (off screen)
            'speed': random.randint(1, 4),        # Fall speed
            'length': random.randint(5, 25),      # Trail length
            'chars': [random.choice(chars) for _ in range(ROWS + 10)]  # Pre-generated chars for speed
        })
    
    # Fill entire screen with dark green background first
    sys.stdout.write("\033[40m")  # Black background
    
    try:
        for frame in range(80):  # 80 frames = ~6 detik animasi
            # Draw each column
            for col in columns:
                i = columns.index(col)
                y = int(col['y'])
                speed = col['speed']
                trail_len = col['length']
                
                # Update trail characters (shift down)
                if frame % speed == 0:
                    # Dim all existing characters in trail (fade effect)
                    for t in range(1, trail_len + 1):
                        py = y - t
                        if 0 < py <= ROWS:
                            fade = max(0.1, 1.0 - (t / trail_len))
                            if fade > 0.7:
                                sys.stdout.write(f"\033[{py};{i+1}H\033[92m{col['chars'][py % len(col['chars'])]}\033[0m")
                            elif fade > 0.4:
                                sys.stdout.write(f"\033[{py};{i+1}H\033[2m\033[92m{col['chars'][py % len(col['chars'])]}\033[22m\033[0m")
                            else:
                                sys.stdout.write(f"\033[{py};{i+1}H\033[2m\033[32m{col['chars'][py % len(col['chars'])]}\033[22m\033[0m")
                    
                    # Bright leading character (white/yellow)
                    if 0 < y <= ROWS:
                        brightness = random.choice([97, 93, 92])  # White, Yellow, Green
                        sys.stdout.write(f"\033[{y};{i+1}H\033[{brightness}m{col['chars'][y % len(col['chars'])]}\033[0m")
                    
                    # Clear character below trail
                    bottom = y - trail_len - 1
                    if 0 < bottom <= ROWS:
                        sys.stdout.write(f"\033[{bottom};{i+1}H ")
                    
                    # Move position
                    col['y'] += 0.5
                    
                    # Reset when off screen
                    if y > ROWS + trail_len:
                        col['y'] = random.randint(-ROWS, -5)
                        col['speed'] = random.randint(1, 3)
                        col['length'] = random.randint(10, 30)
                        col['chars'] = [random.choice(chars) for _ in range(ROWS + 10)]
            
            sys.stdout.flush()
            time.sleep(0.07)
    
    finally:
        # Show cursor back
        sys.stdout.write("\033[?25h")
        sys.stdout.write("\033[0m")
        sys.stdout.flush()
    
    # Clear matrix rain
    os.system('cls' if is_windows else 'clear')
    print("\033[0m", end='')
    
    time.sleep(0.3)
    
    # Hacker access granted animation
    print("\033[92m" + "=" * 60)
    access_lines = [
        "[✓] ACCESS GRANTED - Remote connection established",
        "[✓] Target locked: " + HOSTNAME,
        "[⚡] Executing remote command: " + command_name.upper(),
        "[✓] Command transmitted successfully",
    ]
    for line in access_lines:
        print(f"\033[96m  {line}\033[0m")
        time.sleep(0.2)
    
    print("\033[92m" + "=" * 60 + "\033[0m")
    time.sleep(0.5)
    
    # Countdown effect with progress bar
    print("\n\033[91m" + "█" * 60)
    print("  ⏳ SYSTEM " + command_name.upper() + " IN PROGRESS")
    print("  ⚠️  SIMPAN PEKERJAAN ANDA SEGERA!")
    print("█" * 60 + "\033[0m")
    
    for i in range(30, 0, -3):
        bar_len = int((30 - i) / 30 * 50)
        bar = "█" * bar_len + "░" * (50 - bar_len)
        print(f"\033[93m  [{bar}] {i:2d} detik tersisa\033[0m")
        time.sleep(0.5)
    
    print("\033[91m" + "█" * 60 + "\033[0m")
    print("\033[91m  💀 SYSTEM " + command_name.upper() + " TRIGGERED!\033[0m")
    print()
    
    # Show Windows popup message
    if is_windows:
        try:
            msg = f"🔴 REMOTE HACK DETECTED! 🔴%0APC Anda akan {command_name.upper()} dalam 30 detik!%0A%0A⚠️ Sistem telah diakses oleh pihak ketiga!%0A⚠️ Simpan pekerjaan Anda segera!%0A%0A📍 IP: 192.168.2.2:8800%0A🖥️ Target: {HOSTNAME}"
            subprocess.Popen(['msg', '*', msg], startupinfo=subprocess.STARTUPINFO())
        except:
            pass


def execute_command(command_name, params=None):
    """Execute a command with timeout."""
    start_time = time.time()

    if command_name not in ALLOWED_COMMANDS:
        return {"status": "error", "output": "", "error": f"Command '{command_name}' tidak diizinkan"}

    try:
        if command_name == 'taskkill':
            process_name = (params or {}).get('process_name', '')
            if not process_name:
                return {"status": "error", "output": "", "error": "Nama proses tidak diberikan"}
            cmd = f"taskkill /IM {process_name} /F" if platform.system() == "Windows" else f"killall {process_name}"
        elif command_name == 'shutdown':
            show_hacker_effect(command_name)
            cmd = "shutdown /s /t 30" if platform.system() == "Windows" else "shutdown -h +1"
        elif command_name == 'restart':
            show_hacker_effect(command_name)
            cmd = "shutdown /r /t 30" if platform.system() == "Windows" else "shutdown -r +1"
        elif command_name == 'cancel_shutdown':
            cmd = "shutdown /a" if platform.system() == "Windows" else "shutdown -c"
            print(f"[!] Perintah CANCEL SHUTDOWN diterima!")
        else:
            cmd = ALLOWED_COMMANDS[command_name]

        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc_result = subprocess.run(
            cmd if isinstance(cmd, str) else cmd,
            capture_output=True, timeout=COMMAND_TIMEOUT,
            startupinfo=startupinfo, shell=True
        )

        # Decode with proper encoding
        def decode_output(data):
            for enc in ['utf-8', 'cp1252', 'latin-1']:
                try:
                    return data.decode(enc, errors='replace')
                except:
                    continue
            return data.decode('utf-8', errors='replace')

        stdout = decode_output(proc_result.stdout)
        stderr = decode_output(proc_result.stderr)

        elapsed = time.time() - start_time
        output = (stdout or "") + (stderr or "")
        output = output.strip()

        if proc_result.returncode == 0 and output:
            return {"status": "success", "output": output, "error": "", "execution_time": round(elapsed, 2)}
        elif proc_result.returncode == 0 and not output:
            return {"status": "success", "output": "Command executed successfully (no output)",
                    "error": "", "execution_time": round(elapsed, 2)}
        else:
            return {"status": "error", "output": output, "error": f"Return code: {proc_result.returncode}",
                    "execution_time": round(elapsed, 2)}

    except subprocess.TimeoutExpired:
        return {"status": "error", "output": "", "error": f"Command timeout ({COMMAND_TIMEOUT}s)",
                "execution_time": COMMAND_TIMEOUT}
    except Exception as e:
        return {"status": "error", "output": "", "error": str(e),
                "execution_time": round(time.time() - start_time, 2)}


import threading  # Pastikan library ini di-import di bagian paling atas agent.py

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages (for remote commands)"""
    try:
        payload_str = msg.payload.decode('utf-8')
        payload = json.loads(payload_str)

        command = payload.get('command', '')
        request_id = payload.get('request_id', '')
        params = payload.get('params', {})
        timestamp = payload.get('timestamp', '')

        print(f"\n[📨] Command diterima: {command} (ID: {request_id})")
        if params:
            print(f"     Params: {params}")

        # 2. PENANGANAN ASINKRONUS UNTUK SHUTDOWN / RESTART
        # Jika perintah mematikan sistem, kirim status sukses DULU ke server baru matikan PC
        if command in ["shutdown", "restart"]:
            result_topic = f"lab/command/result/{HOSTNAME}"
            result_payload = {
                "request_id": request_id,
                "hostname": HOSTNAME,
                "command": command,
                "result": {
                    "status": "success",
                    "output": f"Perintah {command} berhasil diterima, sistem akan segera mengeksekusi.",
                    "error": None,
                    "execution_time": 0.1
                }
            }
            # Kirim laporan ke server dulu agar di dashboard statusnya berubah jadi 'Success'
            client.publish(result_topic, json.dumps(result_payload))
            print(f"[✓] Status sukses awal '{command}' dikirim ke server. Memulai proses pembersihan...")

            # Jalankan efek hacker dan shutdown di background thread agar tidak membekukan MQTT
            def run_delayed_command():
                execute_command(command, params)

            threading.Thread(target=run_delayed_command, daemon=True).start()

        else:
            # Perintah biasa (bukan shutdown/restart) bisa langsung dieksekusi secara sinkronus
            result = execute_command(command, params)

            result_topic = f"lab/command/result/{HOSTNAME}"
            result_payload = {
                "request_id": request_id,
                "hostname": HOSTNAME,
                "command": command,
                "result": result
            }

            client.publish(result_topic, json.dumps(result_payload))
            status_icon = "✓" if result["status"] == "success" else "✗"
            print(f"[{status_icon}] Hasil command '{command}' dikirim ke {result_topic}")
            if result.get("execution_time"):
                print(f"     Waktu eksekusi: {result['execution_time']}s")

    except json.JSONDecodeError as e:
        print(f"[✗] Gagal parse JSON: {e}")
    except Exception as e:
        print(f"[✗] Error processing remote command: {e}")


def on_connect(*args, **kwargs):
    """Callback saat berhasil/gagal terhubung ke MQTT Broker"""
    global mqtt_connected
    
    # Ambil nilai 'rc' (Return Code) secara dinamis berdasarkan jumlah argumen
    # v1.x menggunakan args[3], v2.x menggunakan args[3] sebagai flags dan args[4] sebagai reason code/rc
    if len(args) >= 4:
        rc = args[3] if isinstance(args[3], int) else getattr(args[3], 'value', args[3])
        if len(args) >= 5 and isinstance(args[4], int):
            rc = args[4]
    else:
        rc = args[2] if len(args) > 2 else 99

    if rc == 0:
        print("[✓] Terhubung dengan sukses ke Cloudflare MQTT Broker")
        mqtt_connected = True
        # Subscribe ke command topic untuk remote control
        # args[0] adalah objek 'client'
        args[0].subscribe(f"lab/command/{HOSTNAME}")
        print(f"[*] Subscribed ke topik remote: lab/command/{HOSTNAME}")
    else:
        print(f"[✗] Gagal terhubung ke MQTT Broker, Kode Hasil (rc): {rc}")
        mqtt_connected = False

def on_disconnect(*args, **kwargs):
    """Callback saat koneksi MQTT terputus"""
    global mqtt_connected
    mqtt_connected = False
    
    # Ambil nilai rc secara aman dari argumen terakhir atau keyword arguments
    rc = kwargs.get('rc', None)
    if rc is None and len(args) > 0:
        # Biasanya rc ada di indeks ke-2 (v1) atau indeks ke-3/4 (v2)
        for arg in reversed(args):
            if isinstance(arg, int):
                rc = arg
                break
            elif hasattr(arg, 'value') and isinstance(arg.value, int):
                rc = arg.value
                break
                
    print(f"[⚠️] Koneksi MQTT Terputus! Kode Status (rc): {rc}. Mencoba menghubungkan kembali...")


# ==================== INITIALIZATION MQTT CLIENT (UNIVERSAL v1 & v2) ====================
import random

# 1. Buat Client ID unik berdasarkan nama laptop + angka acak agar tidak saling tendang
CLIENT_ID = f"agent_{HOSTNAME}_{random.randint(1000, 9999)}"

try:
    from paho.mqtt.enums import CallbackAPIVersion
    # Konfigurasi untuk paho-mqtt v2.x (Menggunakan WebSockets)
    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2, client_id=CLIENT_ID, transport="websockets")
except (ImportError, AttributeError):
    # Fallback untuk paho-mqtt v1.x (Menggunakan WebSockets)
    client = mqtt.Client(client_id=CLIENT_ID, transport="websockets")

# 2. Hubungkan fungsi callback universal yang sudah diperbaiki sebelumnya
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

# 3. Set Last Will and Testament (Status Offline jika agen mati tiba-tiba)
client.will_set(TOPIC, json.dumps({"id": HOSTNAME, "status": "offline"}), retain=True)

# 4. WAJIB: Aktifkan SSL/TLS agar bisa melewati enkripsi HTTPS port 443 Cloudflare
client.tls_set()

# 5. WAJIB: Atur jalur sub-folder WebSocket ke '/mqtt' agar dikenali oleh Mosquitto Server
client.ws_set_options(path="/mqtt")

mqtt_connected = False
# =========================================================================================
try:
    print(f"[*] Menghubungkan ke broker MQTT {BROKER_URL}:{PORT}...")
    client.connect(BROKER_URL, PORT, 60)
    client.loop_start()
    mqtt_connected = True
except socket.gaierror as e:
    print(f"[✗] Kesalahan DNS/Jaringan: Tidak bisa resolve {BROKER_URL} - {e}")
except ConnectionRefusedError as e:
    print(f"[✗] Koneksi Ditolak: Broker {BROKER_URL}:{PORT} tidak menerima koneksi - {e}")
except TimeoutError as e:
    print(f"[✗] Koneksi Timeout: Broker {BROKER_URL}:{PORT} tidak merespons - {e}")
except Exception as e:
    print(f"[✗] Kesalahan MQTT: {type(e).__name__}: {e}")

old_rx, old_tx = get_net_usage(INTERFACE_NAME)
last_time = time.time()
IP_ADDRESS, MAC_ADDRESS = get_interface_ip_mac(INTERFACE_NAME)

while True:
    try:
        current_time = time.time()
        elapsed = current_time - last_time
        last_time = current_time

        current_rx_bytes, current_tx_bytes = get_net_usage(INTERFACE_NAME)
        down_mbps = ((current_rx_bytes - old_rx) * 8 / (1024 * 1024)) / elapsed if elapsed > 0 else 0
        old_rx, old_tx = current_rx_bytes, current_tx_bytes

        mem = psutil.virtual_memory()
        
        # Dapatkan semua partisi/drive dan akumulasi total storage
        disk_partitions = psutil.disk_partitions()
        total_disk_space = 0
        total_disk_used = 0
        total_disk_free = 0
        disk_details = []
        
        for partition in disk_partitions:
            # Skip drive CD-ROM, RAM disk, dll
            if 'cdrom' in partition.opts or partition.fstype == '':
                continue
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                total_disk_space += usage.total
                total_disk_used += usage.used
                total_disk_free += usage.free
                disk_details.append({
                    "mount": partition.mountpoint,
                    "device": partition.device,
                    "fstype": partition.fstype,
                    "total_gb": round(usage.total / (1024**3), 1),
                    "used_gb": round(usage.used / (1024**3), 1),
                    "free_gb": round(usage.free / (1024**3), 1),
                    "percent": round(usage.percent, 1)
                })
            except (PermissionError, OSError):
                continue
        
        disk_percent = round((total_disk_used / total_disk_space) * 100, 1) if total_disk_space > 0 else 0

        freq = psutil.cpu_freq()
        current_ghz = round(freq.current / 1000, 2) if freq else 0
        max_ghz = round(freq.max / 1000, 2) if freq else 0

        gpu_info = get_gpu_info()

        payload = {
            "id": HOSTNAME, "status": "online", "user": getpass.getuser(),
            "time": datetime.now().strftime("%H:%M:%S"),
            "info": {
                "uptime": get_uptime(),
                "os": f"{platform.system()} {platform.release()}",
                "cpu_name": CPU_NAME
            },
            "network": {
                "down_mbps": round(max(0, down_mbps), 2),
                "traffic_in_gb": round(current_rx_bytes / (1024**3), 2),
                "latency_ms": get_latency(PING_TARGET),
                "iface": INTERFACE_NAME,
                "ip": IP_ADDRESS,
                "mac": MAC_ADDRESS
            },
            "metrics": {
                "cpu": {
                    "percent": int(psutil.cpu_percent()),
                    "threads": CPU_THREADS,
                    "cores": CPU_CORES,
                    "ghz": current_ghz,
                    "max_ghz": max_ghz
                },
                "ram_percent": int(mem.percent),
                "ram": {
                    "used_gb": round(mem.used / (1024**3), 2),
                    "total_gb": round(mem.total / (1024**3), 1)
                },
                "storage": {
                    "total_gb": round(total_disk_space / (1024**3), 1),
                    "used_gb": round(total_disk_used / (1024**3), 1),
                    "free_gb": round(total_disk_free / (1024**3), 1),
                    "percent": disk_percent,
                    "drives": disk_details
                },
                "gpu": gpu_info,
                "top_processes": get_top_processes(5),
                "top_files": get_largest_files(5)
            }
        }
        if mqtt_connected or client.is_connected():
            client.publish(TOPIC, json.dumps(payload), retain=True)
        else:
            print(f"[!] MQTT tidak terhubung, skip publish")
        print(f"[{payload['time']}] CPU: {payload['metrics']['cpu']['percent']}% ({CPU_THREADS} Thread)")
    except Exception as e:
        print(f"Err: {e}")
    time.sleep(2)