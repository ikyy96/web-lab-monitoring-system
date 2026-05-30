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
HOSTNAME = socket.gethostname()
TOPIC = f"lab/monitoring/{HOSTNAME}"
BROKER_URL = "192.168.2.2"
PORT = 1883
PING_TARGET = "8.8.8.8"

# Ambil Spek CPU Sekali Saja (Statik)
CPU_THREADS = psutil.cpu_count(logical=True)
CPU_CORES = psutil.cpu_count(logical=False)
CPU_NAME = "Unknown CPU"

def get_cpu_name():
    """Get detailed CPU name with multiple fallback methods"""
    import platform as pf
    
    if pf.system() == "Windows":
        # Method 1: Try wmic (legacy, works on older Windows)
        try:
            result = subprocess.run(['wmic', 'cpu', 'get', 'name', '/format:csv'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                # Parse CSV format: "Node,CpuName"
                for line in result.stdout.strip().split('\n'):
                    if ',' in line and not line.strip().startswith('Node'):
                        parts = line.strip().split(',', 1)
                        if len(parts) > 1 and parts[1].strip():
                            name = parts[1].strip()
                            if name and not name.startswith('Node'):
                                return name
        except:
            pass
        
        # Method 2: wmic simple format (fallback)
        try:
            result = subprocess.run(['wmic', 'cpu', 'get', 'name'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
                # lines[0] is header "Name", lines[1] is the actual CPU name
                for line in lines:
                    if line.lower() != 'name' and line:
                        return line
        except:
            pass
        
        # Method 3: Use PowerShell (most reliable on Windows 10/11)
        try:
            result = subprocess.run([
                'powershell', '-Command',
                '(Get-CimInstance Win32_Processor).Name'
            ], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        
        # Method 4: Fallback - try to get from registry
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
        
        # Method 5: platform.processor() as last resort (returns generic identifier)
        proc = pf.processor()
        if proc and proc != "Unknown CPU":
            return proc
        return "Unknown CPU"
    
    elif pf.system() == "Linux":
        # Try /proc/cpuinfo for detailed name
        try:
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('model name'):
                        name = line.split(':')[1].strip()
                        if name:
                            return name
        except:
            pass
        
        # Try lscpu
        try:
            result = subprocess.run(['lscpu'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if 'Model name' in line:
                    name = line.split(':')[1].strip()
                    if name:
                        return name
        except:
            pass
        
        proc = pf.processor()
        return proc if proc else "Unknown CPU"
    
    else:
        # macOS or other
        try:
            result = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'],
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        
        proc = pf.processor()
        return proc if proc else "Unknown CPU"

CPU_NAME = get_cpu_name()
print(f"[✓] CPU Terdeteksi: {CPU_NAME}")

# Initialize GPU monitoring
def init_gpu_monitoring():
    """Initialize GPU monitoring for NVIDIA GPUs"""
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
    
    # Get NVIDIA GPU info via pynvml
    if GPU_INITIALIZED:
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                if isinstance(name, bytes):
                    name = name.decode('utf-8')
                
                # Get memory info
                memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                memory_used_gb = round(memory_info.used / (1024**3), 2)
                memory_total_gb = round(memory_info.total / (1024**3), 2)
                
                # Get temperature
                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                except:
                    temperature = 0
                
                # Get utilization
                try:
                    utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpu_util = utilization.gpu
                    memory_util = utilization.memory
                except:
                    gpu_util = 0
                    memory_util = 0
                
                gpus.append({
                    "name": name,
                    "type": "NVIDIA",
                    "temperature": temperature,
                    "utilization": gpu_util,
                    "memory_util": memory_util,
                    "memory_used_gb": memory_used_gb,
                    "memory_total_gb": memory_total_gb
                })
        except Exception as e:
            print(f"Error getting NVIDIA GPU info: {e}")
    
    # Get AMD/Intel GPU info via WMI (Windows only)
    if WIN32_AVAILABLE and platform.system() == "Windows":
        try:
            wmi = win32com.client.GetObject("winmgmts:")
            gpu_list = wmi.InstancesOf("Win32_VideoController")
            
            for gpu in gpu_list:
                gpu_name = gpu.Name
                # Skip if already captured by pynvml (check if NVIDIA)
                if "NVIDIA" in gpu_name and gpus:
                    continue
                
                # Get adapter RAM
                adapter_ram = gpu.AdapterRAM
                if adapter_ram:
                    memory_total_gb = round(adapter_ram / (1024**3), 1)
                else:
                    memory_total_gb = 0
                
                # Get driver version
                driver_version = gpu.DriverVersion if gpu.DriverVersion else "N/A"
                
                gpus.append({
                    "name": gpu_name,
                    "type": "AMD/Intel" if "AMD" in gpu_name or "Intel" in gpu_name else "Unknown",
                    "temperature": 0,  # Not available via WMI
                    "utilization": 0,  # Not available via WMI
                    "memory_util": 0,
                    "memory_used_gb": 0,
                    "memory_total_gb": memory_total_gb,
                    "driver_version": driver_version
                })
        except Exception as e:
            print(f"Error getting AMD/Intel GPU info: {e}")
    
    # Fallback: Try using subprocess to get GPU info
    if not gpus:
        try:
            result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                for line in lines:
                    name = line.strip()
                    if name:
                        gpus.append({
                            "name": name,
                            "type": "Unknown",
                            "temperature": 0,
                            "utilization": 0,
                            "memory_util": 0,
                            "memory_used_gb": 0,
                            "memory_total_gb": 0
                        })
        except:
            pass
    
    return gpus

def get_active_interface_via_ping():
    print("[*] Mencari interface aktif dengan akses internet...")
    is_windows = platform.system() == "Windows"
    addrs = psutil.net_if_addrs()
    
    for intf, addr_list in addrs.items():
        if intf.lower() in ['lo', 'loopback', 'localhost']: continue
            
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
                except: continue
    return list(addrs.keys())[0] if addrs else "eth0"

INTERFACE_NAME = get_active_interface_via_ping()

def get_interface_ip_mac(interface_name):
    """Get the IP address and MAC address for the given interface."""
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
    """Get top processes by CPU usage."""
    processes = []
    try:
        for proc in psutil.process_iter(['name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['name'] and pinfo['cpu_percent']:
                    processes.append((pinfo['name'], round(pinfo['cpu_percent'], 1), round(pinfo['memory_percent'] or 0, 1)))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        processes.sort(key=lambda x: x[1], reverse=True)
    except:
        pass
    return [{"name": p[0], "cpu": p[1], "mem": p[2]} for p in processes[:limit]]

def get_largest_files(limit=5):
    """Get largest files from common locations."""
    files = []
    search_paths = []
    is_windows = platform.system() == "Windows"
    if is_windows:
        search_paths = [os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Public'), 'Desktop'),
                       os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Public'), 'Documents'),
                       os.path.join(os.environ.get('USERPROFILE', 'C:\\Users\\Public'), 'Downloads')]
    else:
        search_paths = [os.path.expanduser('~/Desktop'),
                       os.path.expanduser('~/Documents'),
                       os.path.expanduser('~/Downloads')]
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
                                if size > 1024 * 1024:  # > 1MB
                                    files.append((fpath, size))
                        except:
                            continue
                    if len(files) >= limit * 3:
                        break
        files.sort(key=lambda x: x[1], reverse=True)
    except:
        pass
    return [{"name": os.path.basename(f[0]), "path": f[0], "size_mb": round(f[1] / (1024 * 1024), 1)} for f in files[:limit]]

# --- FUNGSI METRIK ---
def get_uptime():
    try:
        uptime_seconds = time.time() - psutil.boot_time()
        return f"{int(uptime_seconds // 3600)}h {int((uptime_seconds % 3600) // 60)}m"
    except: return "N/A"

def get_latency(host):
    try:
        is_windows = platform.system() == "Windows"
        cmd = ["ping", "-n" if is_windows else "-c", "1", "-w" if is_windows else "-W", "1", host]
        startupinfo = None
        if is_windows:
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(cmd, startupinfo=startupinfo, stderr=subprocess.STDOUT, universal_newlines=True)
        if "time=" in output:
            val = output.split("time=")[1].split("ms")[0].strip()
            return int(float(val))
    except: return 999
    return 0

def get_net_usage(interface):
    try:
        net_io = psutil.net_io_counters(pernic=True)
        if interface in net_io:
            return net_io[interface].bytes_recv, net_io[interface].bytes_sent
    except: pass
    return 0, 0

# ==================== REMOTE COMMAND EXECUTION ====================
COMMAND_TIMEOUT = 15  # Max execution time per command (detik)
ALLOWED_COMMANDS = {
    'tasklist': 'tasklist' if platform.system() == 'Windows' else 'ps aux',
    'ipconfig': 'ipconfig' if platform.system() == 'Windows' else 'ifconfig',
    'whoami': 'whoami',
    'systeminfo': 'systeminfo' if platform.system() == 'Windows' else 'uname -a',
    'taskkill': None,  # Special handling with params
    'shutdown': None,  # Special handling
    'restart': None,   # Special handling
    'cancel_shutdown': None,  # Special handling
}

def execute_command(command_name, params=None):
    """
    Execute a command with timeout.
    Returns dict dengan status, output, error.
    """
    start_time = time.time()
    
    if command_name not in ALLOWED_COMMANDS:
        return {"status": "error", "output": "", "error": f"Command '{command_name}' tidak diizinkan"}
    
    try:
        # Special commands with custom handling
        if command_name == 'taskkill':
            process_name = (params or {}).get('process_name', '')
            if not process_name:
                return {"status": "error", "output": "", "error": "Nama proses tidak diberikan"}
            cmd = f"taskkill /IM {process_name} /F" if platform.system() == "Windows" else f"killall {process_name}"
            
        elif command_name == 'shutdown':
            if platform.system() == "Windows":
                cmd = "shutdown /s /t 30"
            else:
                cmd = "shutdown -h +1"
            print(f"[!] Perintah SHUTDOWN diterima! PC akan mati dalam 30 detik...")
            
        elif command_name == 'restart':
            if platform.system() == "Windows":
                cmd = "shutdown /r /t 30"
            else:
                cmd = "shutdown -r +1"
            print(f"[!] Perintah RESTART diterima! PC akan restart dalam 30 detik...")
            
        elif command_name == 'cancel_shutdown':
            if platform.system() == "Windows":
                cmd = "shutdown /a"
            else:
                cmd = "shutdown -c"
            print(f"[!] Perintah CANCEL SHUTDOWN diterima!")
            
        else:
            cmd = ALLOWED_COMMANDS[command_name]
        
        # Execute with timeout
        startupinfo = None
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Use binary mode first, then decode with system encoding to avoid Unicode errors
        proc_result = subprocess.run(
            cmd if isinstance(cmd, str) else cmd,
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
            startupinfo=startupinfo,
            shell=True
        )
        
        # Decode with proper encoding (handle Windows locale encoding)
        try:
            stdout = proc_result.stdout.decode('utf-8', errors='replace')
        except:
            try:
                stdout = proc_result.stdout.decode('cp1252', errors='replace')
            except:
                stdout = proc_result.stdout.decode('latin-1', errors='replace')
        
        try:
            stderr = proc_result.stderr.decode('utf-8', errors='replace')
        except:
            try:
                stderr = proc_result.stderr.decode('cp1252', errors='replace')
            except:
                stderr = proc_result.stderr.decode('latin-1', errors='replace')
        
        elapsed = time.time() - start_time
        output = (stdout or "") + (stderr or "")
        output = output.strip()
        
        if proc_result.returncode == 0 and output:
            return {"status": "success", "output": output, "error": "", "execution_time": round(elapsed, 2)}
        elif proc_result.returncode == 0 and not output:
            return {"status": "success", "output": "Command executed successfully (no output)", "error": "", "execution_time": round(elapsed, 2)}
        else:
            return {"status": "error", "output": output, "error": f"Return code: {proc_result.returncode}", "execution_time": round(elapsed, 2)}
    
    except subprocess.TimeoutExpired:
        return {"status": "error", "output": "", "error": f"Command timeout ({COMMAND_TIMEOUT}s)", "execution_time": COMMAND_TIMEOUT}
    except Exception as e:
        return {"status": "error", "output": "", "error": str(e), "execution_time": round(time.time() - start_time, 2)}

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
        
        # Execute command
        result = execute_command(command, params)
        
        # Send result back
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
        print(f"[✗] Error processing command: {e}")

def on_connect(client, userdata, connect_flags, rc, properties=None):
    if rc == 0:
        print(f"[✓] MQTT Terhubung ke {BROKER_URL}:{PORT}")
        # Subscribe ke topic command khusus hostname ini
        command_topic = f"lab/command/{HOSTNAME}"
        client.subscribe(command_topic)
        print(f"[📡] Subscribed ke: {command_topic}")
    else:
        print(f"[✗] MQTT Gagal dengan kode {rc}")

def on_disconnect(client, userdata, disconnect_flags, rc, properties=None):
    if rc != 0:
        print(f"[!] Putus koneksi tidak terduga. Kode: {rc}")

def on_publish(client, userdata, mid, reason_code=None, properties=None):
    pass

try:
    from paho.mqtt.enums import CallbackAPIVersion
    client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
except (ImportError, AttributeError):
    client = mqtt.Client()

client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish
client.on_message = on_message
client.will_set(TOPIC, json.dumps({"id": HOSTNAME, "status": "offline"}), retain=True)

mqtt_connected = False
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

# Pre-calc ip/mac once (could also refresh each loop if network changes)
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
        disk_path = 'C:\\' if platform.system() == "Windows" else '/'
        disk = psutil.disk_usage(disk_path)
        
        freq = psutil.cpu_freq()
        current_ghz = round(freq.current / 1000, 2) if freq else 0
        max_ghz = round(freq.max / 1000, 2) if freq else 0

        # Get GPU info
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
                    "total_gb": round(disk.total / (1024**3), 1),
                    "used_gb": round(disk.used / (1024**3), 1),
                    "free_gb": round(disk.free / (1024**3), 1),
                    "percent": round(disk.percent, 1)
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
    except Exception as e: print(f"Err: {e}")
    time.sleep(2)