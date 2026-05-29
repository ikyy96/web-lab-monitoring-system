"""
Lab Monitoring System - Complete Solution with Robust Error Handling
FastAPI + MQTT Subscriber + WebSocket + Demo Mode
Version: 2.1.0 - Enhanced stability and error handling
"""

import json
import asyncio
import logging
import random
import queue
import time
import traceback
import subprocess
from datetime import datetime
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import paho.mqtt.client as mqtt
import uvicorn

# ==================== KONFIGURASI ====================
# Server MQTT di Device A menggunakan localhost
# Agent.py di Device B menggunakan 192.168.2.2
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "lab/monitoring/+"
MQTT_CLIENT_ID = f"monitoring_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
SERVER_PORT = 8800
USE_MQTT = True  # Set False untuk mode demo tanpa MQTT

# Konfigurasi error handling
MAX_RECONNECT_DELAY = 300  # 5 menit
INITIAL_RECONNECT_DELAY = 5  # 5 detik
MAX_BROADCAST_RETRIES = 3
BROADCAST_TIMEOUT = 5  # detik
MAX_CLIENTS = 1000  # Batas maksimal clients untuk mencegah memory overflow
MAX_HISTORY_LENGTH = 50  # Batas history per client

# ==================== COMMAND CONFIGURATION ====================
COMMAND_WHITELIST = {
    'tasklist': 'List processes',
    'ipconfig': 'Network configuration',
    'whoami': 'Current user',
    'systeminfo': 'System information',
    'taskkill': 'Kill process',
    'shutdown': '⚠️ Shutdown PC (30 detik)',
    'restart': '🔄 Restart PC (30 detik)',
    'cancel_shutdown': '❌ Cancel scheduled shutdown/restart',
}

# Commands that require additional parameters
COMMAND_PARAMS = {
    'taskkill': ['process_name'],  # taskkill memerlukan parameter process_name
}

# Setup command logger untuk logging execution
command_logger = logging.getLogger('commands')
command_handler = logging.FileHandler('commands.log', encoding='utf-8')
command_formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
command_handler.setFormatter(command_formatter)
command_logger.addHandler(command_handler)
command_logger.setLevel(logging.INFO)

# Demo PC data (hanya digunakan jika USE_MQTT = False)
DEMO_PCS = [
    {"id": "PC-LAB-01", "ip": "10.230.250.101", "user": "student1", "os": "Windows 11 Pro"},
    {"id": "PC-LAB-02", "ip": "10.230.250.102", "user": "student2", "os": "Windows 11 Pro"},
    {"id": "PC-LAB-03", "ip": "10.230.250.103", "user": "student3", "os": "Ubuntu 22.04"},
    {"id": "PC-LAB-04", "ip": "10.230.250.104", "user": "student4", "os": "Windows 11 Pro"},
    {"id": "PC-LAB-05", "ip": "10.230.250.105", "user": "student5", "os": "Windows 11 Pro"},
    {"id": "PC-LAB-06", "ip": "10.230.250.106", "user": "student6", "os": "Ubuntu 22.04"},
    {"id": "PC-LAB-07", "ip": "10.230.250.107", "user": "student7", "os": "Windows 11 Pro"},
    {"id": "PC-LAB-08", "ip": "10.230.250.108", "user": "student8", "os": "Windows 11 Pro"},
]

PROCESS_NAMES = ["chrome.exe", "python.exe", "code.exe", "discord.exe", "spotify.exe", 
                 "firefox.exe", "node.exe", "java.exe", "pycharm.exe", "slack.exe"]
FILE_NAMES = ["lecture_video.mp4", "project_backup.zip", "dataset.csv", "presentation.pptx", 
              "research_paper.pdf", "database_dump.sql", "vm_image.vdi", "photos.zip"]

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('lab_monitoring.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ==================== ERROR HANDLING UTILITIES ====================
class CircuitBreaker:
    """Circuit breaker pattern untuk mencegah cascade failure"""
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                logger.warning("Circuit breaker entering HALF_OPEN state")
                self.state = "HALF_OPEN"
            else:
                raise Exception(f"Circuit breaker is OPEN. Will recover at {self.last_failure_time + self.recovery_timeout}")
        
        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                logger.info("Circuit breaker recovered successfully")
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            logger.error(f"Circuit breaker failure #{self.failure_count}: {e}")
            if self.failure_count >= self.failure_threshold:
                logger.error(f"Circuit breaker OPENED after {self.failure_count} failures")
                self.state = "OPEN"
            raise

class RateLimiter:
    """Rate limiter untuk mencegah flooding"""
    def __init__(self, max_calls=10, period=1.0):
        self.max_calls = max_calls
        self.period = period
        self.calls = []
    
    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            now = time.time()
            self.calls = [t for t in self.calls if now - t < self.period]
            if len(self.calls) >= self.max_calls:
                sleep_time = self.period / self.max_calls
                logger.debug(f"Rate limiting: sleeping for {sleep_time}s")
                await asyncio.sleep(sleep_time)
            self.calls.append(now)
            return await func(*args, **kwargs)
        return wrapper

# Global circuit breaker for broadcast operations
broadcast_circuit_breaker = CircuitBreaker(failure_threshold=10, recovery_timeout=60)

# ==================== COMMAND HANDLING ====================
# Dictionary untuk store pending command requests dan results
pending_commands: Dict[str, asyncio.Event] = {}
command_results: Dict[str, dict] = {}

# ==================== FASTAPI APP ====================
app = FastAPI(title="Lab Monitoring System", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__}
    )

# ==================== CLIENT STATE ====================
clients: Dict[str, dict] = {}
active_connections: Set[WebSocket] = set()

# Statistics untuk monitoring
stats = {
    "total_messages": 0,
    "failed_messages": 0,
    "broadcast_failures": 0,
    "mqtt_reconnects": 0,
    "start_time": datetime.now()
}

@dataclass
class ClientState:
    """State untuk setiap PC client"""
    id: str
    status: str = "offline"
    user: str = ""
    time: str = ""
    ip: str = ""
    mac: str = ""
    iface: str = ""
    uptime: str = ""
    os: str = ""
    cpu_name: str = ""
    cpu_percent: float = 0.0
    cpu_threads: int = 0
    cpu_cores: int = 0
    cpu_ghz: float = 0.0
    cpu_max_ghz: float = 0.0
    ram_percent: float = 0.0
    ram_used_gb: float = 0.0
    ram_total_gb: float = 0.0
    storage_total_gb: float = 0.0
    storage_used_gb: float = 0.0
    storage_free_gb: float = 0.0
    storage_percent: float = 0.0
    down_mbps: float = 0.0
    traffic_in_gb: float = 0.0
    latency_ms: float = 0.0
    top_processes: list = field(default_factory=list)
    top_files: list = field(default_factory=list)
    gpu: list = field(default_factory=list)
    last_seen: str = ""
    last_seen_ts: float = 0.0
    cpu_history: list = field(default_factory=list)
    ram_history: list = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id, "status": self.status, "user": self.user,
            "time": self.time, "ip": self.ip, "mac": self.mac, "iface": self.iface,
            "uptime": self.uptime, "os": self.os, "cpu_name": self.cpu_name, 
            "cpu_percent": self.cpu_percent,
            "cpu_threads": self.cpu_threads, "cpu_cores": self.cpu_cores,
            "cpu_ghz": self.cpu_ghz, "cpu_max_ghz": self.cpu_max_ghz,
            "ram_percent": self.ram_percent, "ram_used_gb": self.ram_used_gb,
            "ram_total_gb": self.ram_total_gb, "storage_total_gb": self.storage_total_gb,
            "storage_used_gb": self.storage_used_gb, "storage_free_gb": self.storage_free_gb,
            "storage_percent": self.storage_percent,
            "down_mbps": self.down_mbps,
            "traffic_in_gb": self.traffic_in_gb, "latency_ms": self.latency_ms,
            "top_processes": self.top_processes, "top_files": self.top_files,
            "gpu": self.gpu, "last_seen": self.last_seen, "cpu_history": self.cpu_history,
            "ram_history": self.ram_history
        }

def validate_payload_structure(payload: dict) -> bool:
    """Validasi struktur payload MQTT sebelum diproses"""
    try:
        # Check required fields
        if not isinstance(payload, dict):
            logger.error("Payload is not a dictionary")
            return False
        
        # Validate numeric fields
        if 'metrics' in payload:
            metrics = payload['metrics']
            if not isinstance(metrics, dict):
                logger.error("metrics field is not a dictionary")
                return False
            
            # Validate CPU data
            if 'cpu' in metrics:
                cpu = metrics['cpu']
                if not isinstance(cpu, dict):
                    logger.error("cpu field is not a dictionary")
                    return False
                if 'percent' in cpu and not isinstance(cpu['percent'], (int, float)):
                    logger.error(f"cpu.percent is not numeric: {cpu['percent']}")
                    return False
            
            # Validate RAM percentage
            if 'ram_percent' in metrics and not isinstance(metrics['ram_percent'], (int, float)):
                logger.error(f"ram_percent is not numeric: {metrics['ram_percent']}")
                return False
        
        return True
    except Exception as e:
        logger.error(f"Error validating payload: {e}")
        return False

def safe_update_client_state(client_id: str, data: dict):
    """Update state client dengan error handling yang aman"""
    try:
        # Limit number of clients
        if client_id not in clients and len(clients) >= MAX_CLIENTS:
            logger.warning(f"Maximum clients ({MAX_CLIENTS}) reached. Ignoring new client: {client_id}")
            return
        
        if client_id not in clients:
            clients[client_id] = ClientState(id=client_id)
        
        client = clients[client_id]
        
        # Update basic fields with type checking
        client.status = str(data.get("status", client.status))
        client.user = str(data.get("user", client.user))
        client.time = str(data.get("time", client.time))
        client.last_seen = datetime.now().strftime("%H:%M:%S")
        client.last_seen_ts = time.time()
        
        # Update network data with validation
        network = data.get("network", {})
        if isinstance(network, dict):
            client.ip = str(network.get("ip", client.ip))
            client.mac = str(network.get("mac", client.mac))
            client.iface = str(network.get("iface", client.iface))
            
            try:
                client.down_mbps = float(network.get("down_mbps", client.down_mbps))
                client.traffic_in_gb = float(network.get("traffic_in_gb", client.traffic_in_gb))
                client.latency_ms = float(network.get("latency_ms", client.latency_ms))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid network data for {client_id}: {e}")
        
        # Update info data
        info = data.get("info", {})
        if isinstance(info, dict):
            client.uptime = str(info.get("uptime", client.uptime))
            client.os = str(info.get("os", client.os))
            client.cpu_name = str(info.get("cpu_name", client.cpu_name))
        
        # Update metrics with validation
        metrics = data.get("metrics", {})
        if isinstance(metrics, dict):
            cpu = metrics.get("cpu", {})
            if isinstance(cpu, dict):
                try:
                    client.cpu_percent = float(cpu.get("percent", client.cpu_percent))
                    client.cpu_threads = int(cpu.get("threads", client.cpu_threads))
                    client.cpu_cores = int(cpu.get("cores", client.cpu_cores))
                    client.cpu_ghz = float(cpu.get("ghz", client.cpu_ghz))
                    client.cpu_max_ghz = float(cpu.get("max_ghz", client.cpu_max_ghz))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid CPU data for {client_id}: {e}")
            
            try:
                client.ram_percent = float(metrics.get("ram_percent", client.ram_percent))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid ram_percent for {client_id}: {e}")
            
            ram = metrics.get("ram", {})
            if isinstance(ram, dict):
                try:
                    client.ram_used_gb = float(ram.get("used_gb", client.ram_used_gb))
                    client.ram_total_gb = float(ram.get("total_gb", client.ram_total_gb))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid RAM data for {client_id}: {e}")
            
            storage = metrics.get("storage", {})
            if isinstance(storage, dict):
                try:
                    client.storage_total_gb = float(storage.get("total_gb", client.storage_total_gb))
                    client.storage_used_gb = float(storage.get("used_gb", client.storage_used_gb))
                    client.storage_free_gb = float(storage.get("free_gb", client.storage_free_gb))
                    client.storage_percent = float(storage.get("percent", client.storage_percent))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid storage data for {client_id}: {e}")
            
            # Update lists with validation
            top_processes = metrics.get("top_processes", client.top_processes)
            if isinstance(top_processes, list):
                client.top_processes = top_processes[:10]  # Limit to 10 processes
            
            top_files = metrics.get("top_files", client.top_files)
            if isinstance(top_files, list):
                client.top_files = top_files[:10]  # Limit to 10 files
            
            gpu = metrics.get("gpu", client.gpu)
            if isinstance(gpu, list):
                client.gpu = gpu[:5]  # Limit to 5 GPUs
        
        # Update history with limits
        client.cpu_history.append(client.cpu_percent)
        client.ram_history.append(client.ram_percent)
        if len(client.cpu_history) > MAX_HISTORY_LENGTH:
            client.cpu_history = client.cpu_history[-MAX_HISTORY_LENGTH:]
        if len(client.ram_history) > MAX_HISTORY_LENGTH:
            client.ram_history = client.ram_history[-MAX_HISTORY_LENGTH:]
        
        stats["total_messages"] += 1
        
    except Exception as e:
        logger.error(f"Error updating client state for {client_id}: {e}\n{traceback.format_exc()}")
        stats["failed_messages"] += 1

async def safe_broadcast_update():
    """Broadcast update ke semua WebSocket client dengan error handling"""
    if not active_connections:
        return
    
    try:
        # Use circuit breaker to prevent cascade failures
        # IMPORTANT: stats['start_time'] berisi datetime -> harus diubah ke string agar bisa di-JSON.
        stats_payload = stats.copy()
        if isinstance(stats_payload.get("start_time"), datetime):
            stats_payload["start_time"] = stats_payload["start_time"].isoformat()

        # Build JSON-safe payload (avoid datetime serialization issues)
        # JSON-safe payload (ensure no datetime objects leak)
        stats_payload_safe = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in stats_payload.items()
        }

        message_obj = {
            "type": "update",
            "clients": [
                c.to_dict() if isinstance(c, ClientState) else c
                for c in clients.values()
            ],
            "timestamp": datetime.now().isoformat(),
            "stats": stats_payload_safe,
        }

        message = broadcast_circuit_breaker.call(json.dumps, message_obj)
        
        
        disconnected = set()
        for conn in active_connections:
            try:
                # Add timeout to prevent blocking
                await asyncio.wait_for(conn.send_text(message), timeout=BROADCAST_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning(f"Broadcast timeout to client, marking as disconnected")
                disconnected.add(conn)
            except Exception as e:
                logger.debug(f"Error sending to client: {e}")
                disconnected.add(conn)
        
        if disconnected:
            active_connections.difference_update(disconnected)
            logger.info(f"Removed {len(disconnected)} disconnected clients")
            
    except Exception as e:
        logger.error(f"Broadcast failed: {e}\n{traceback.format_exc()}")
        stats["broadcast_failures"] += 1
        # If broadcast fails repeatedly, circuit breaker will open

# ==================== MQTT SETUP ====================
mqtt_message_queue = queue.Queue()
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
mqtt_reconnect_delay = INITIAL_RECONNECT_DELAY

def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"✅ Connected to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        client.subscribe("lab/command/result/+")  # Subscribe ke command result topic
        logger.info(f"📡 Subscribed to: {MQTT_TOPIC} dan lab/command/result/+")
        # Reset reconnect delay on successful connection
        global mqtt_reconnect_delay
        mqtt_reconnect_delay = INITIAL_RECONNECT_DELAY
    else:
        logger.error(f"❌ MQTT connection failed. Return code: {rc}")

def handle_command_result(msg):
    """
    Handle command result dari agent
    Topic: lab/command/result/{hostname}
    Payload: JSON dengan hasil command
    """
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        request_id = payload.get('request_id')
        hostname = payload.get('hostname')
        command = payload.get('command')
        result = payload.get('result', {})
        
        # Log command execution
        command_logger.info(
            f"Command: {command} | Host: {hostname} | "
            f"Status: {result.get('status')} | Output: {result.get('output', '')[:100]}..."
        )
        
        # Store result
        command_results[request_id] = {
            'hostname': hostname,
            'command': command,
            'result': result,
            'timestamp': datetime.now().isoformat()
        }
        
        # Signal waiting coroutine
        if request_id in pending_commands:
            pending_commands[request_id].set()
        
        logger.info(f"[✓] Command result diterima: {command} dari {hostname}")
        
    except Exception as e:
        logger.error(f"Error handling command result: {e}")

def on_mqtt_message(client, userdata, msg):
    try:
        # Decode payload
        try:
            payload_str = msg.payload.decode('utf-8')
        except UnicodeDecodeError:
            logger.error(f"Failed to decode payload as UTF-8 from topic {msg.topic}")
            return
        
        # Parse JSON
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MQTT message from {msg.topic}: {e}")
            logger.debug(f"Payload: {payload_str[:200]}...")  # Log first 200 chars
            return
        
        # Handle command result
        if msg.topic.startswith("lab/command/result/"):
            handle_command_result(msg)
            return
        
        # Handle monitoring data
        if not validate_payload_structure(payload):
            logger.error(f"Invalid payload structure from {msg.topic}")
            return
        
        # Extract client ID
        client_id = payload.get("id", msg.topic.split('/')[-1])
        if not client_id or not isinstance(client_id, str):
            logger.error(f"Invalid client_id in payload from {msg.topic}")
            return
        
        logger.debug(f"📥 Received from {client_id}: status={payload.get('status')}")
        
        # Put message in queue for main thread to process
        mqtt_message_queue.put((client_id, payload))
        
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}\n{traceback.format_exc()}")

def on_mqtt_disconnect(client, userdata, rc):
    logger.warning(f"⚠️ Disconnected from MQTT Broker (rc={rc})")
    logger.info(f"Will attempt to reconnect in {mqtt_reconnect_delay} seconds...")

def on_mqtt_connect_failure(client, userdata, rc):
    logger.error(f"MQTT connection failed with rc={rc}")
    # Schedule reconnect
    global mqtt_reconnect_delay
    logger.info(f"Retrying MQTT connection in {mqtt_reconnect_delay} seconds...")
    mqtt_reconnect_delay = min(mqtt_reconnect_delay * 2, MAX_RECONNECT_DELAY)

mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
mqtt_client.on_disconnect = on_mqtt_disconnect
mqtt_client.on_connect_fail = on_mqtt_connect_failure

async def process_mqtt_messages():
    """Background task to process MQTT messages from queue"""
    while True:
        try:
            # Process all messages in queue
            batch_size = 0
            while not mqtt_message_queue.empty() and batch_size < 100:  # Process max 100 messages per cycle
                try:
                    client_id, payload = mqtt_message_queue.get_nowait()
                    safe_update_client_state(client_id, payload)
                    batch_size += 1
                except queue.Empty:
                    break
            
            # Broadcast if we processed any messages
            if batch_size > 0:
                await safe_broadcast_update()
                
        except Exception as e:
            logger.error(f"Error in process_mqtt_messages: {e}\n{traceback.format_exc()}")
        
        await asyncio.sleep(0.1)  # Small delay to avoid busy loop

# ==================== DEMO MODE ====================
def generate_demo_data(pc_info):
    """Generate data dummy untuk demo"""
    cpu = random.uniform(5, 85)
    ram = random.uniform(20, 75)
    
    return {
        "id": pc_info["id"], "status": "online", "user": pc_info["user"],
        "time": datetime.now().strftime("%H:%M:%S"), "ip": pc_info["ip"],
        "mac": f"AA:BB:CC:DD:EE:{random.randint(1,99):02d}", "iface": "eth0",
        "uptime": f"{random.randint(1,24)}h {random.randint(0,59)}m", "os": pc_info["os"],
        "cpu_percent": round(cpu, 1), "cpu_threads": random.choice([4,8,12,16]),
        "cpu_cores": random.choice([2,4,6,8]), "cpu_ghz": round(random.uniform(2.0,3.5), 2),
        "cpu_max_ghz": round(random.uniform(3.5,5.0), 2), "ram_percent": round(ram, 1),
        "ram_used_gb": round(random.uniform(2,12), 1), "ram_total_gb": random.choice([8,16,32]),
        "storage_total_gb": random.choice([256,512,1024]),
        "storage_used_gb": round(random.uniform(50,300), 1),
        "storage_free_gb": round(random.uniform(100,500), 1),
        "storage_percent": round(random.uniform(20,70), 1),
        "down_mbps": round(random.uniform(1,100), 1),
        "traffic_in_gb": round(random.uniform(0.5,10), 2),
        "latency_ms": round(random.uniform(5,50), 1),
        "last_seen": datetime.now().strftime("%H:%M:%S"),
        "top_processes": [{"name": random.choice(PROCESS_NAMES), 
                          "cpu": round(random.uniform(1,30), 1),
                          "mem": round(random.uniform(0.5,4), 2)} for _ in range(5)],
        "top_files": [{"name": random.choice(FILE_NAMES),
                      "path": f"C:/Users/{pc_info['user']}/Documents",
                      "size_mb": round(random.uniform(100,2000), 1)} for _ in range(5)],
        "cpu_history": [], "ram_history": []
    }

async def update_demo_data():
    """Update data demo dan broadcast"""
    try:
        for pc_info in DEMO_PCS:
            if pc_info["id"] not in clients:
                clients[pc_info["id"]] = ClientState(**generate_demo_data(pc_info))
            else:
                new_data = generate_demo_data(pc_info)
                old = clients[pc_info["id"]].to_dict()
                new_data["cpu_history"] = old["cpu_history"] + [old["cpu_percent"]]
                new_data["ram_history"] = old["ram_history"] + [old["ram_percent"]]
                if len(new_data["cpu_history"]) > MAX_HISTORY_LENGTH:
                    new_data["cpu_history"] = new_data["cpu_history"][-MAX_HISTORY_LENGTH:]
                if len(new_data["ram_history"]) > MAX_HISTORY_LENGTH:
                    new_data["ram_history"] = new_data["ram_history"][-MAX_HISTORY_LENGTH:]
                clients[pc_info["id"]] = ClientState(**new_data)
        
        await safe_broadcast_update()
    except Exception as e:
        logger.error(f"Error in update_demo_data: {e}\n{traceback.format_exc()}")

async def demo_loop():
    """Background task untuk generate demo data"""
    while True:
        try:
            await update_demo_data()
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error in demo_loop: {e}\n{traceback.format_exc()}")
            await asyncio.sleep(5)  # Wait longer on error

# ==================== FASTAPI EVENTS ====================

# Threshold: kalau tidak ada data masuk dalam X detik, mark offline
OFFLINE_TIMEOUT = 15  # detik

async def check_offline_clients():
    """Background task: mark client offline kalau tidak ada data masuk"""
    while True:
        try:
            now = time.time()
            changed = False
            for client_id, client in clients.items():
                if client.status == "online":
                    elapsed = now - client.last_seen_ts
                    if elapsed > OFFLINE_TIMEOUT:
                        client.status = "offline"
                        logger.warning(f"[TIMEOUT] {client_id} marked offline (no data for {elapsed:.0f}s)")
                        changed = True
            if changed:
                await safe_broadcast_update()
        except Exception as e:
            logger.error(f"Error in check_offline_clients: {e}")
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Lab Monitoring System v2.1.0")
    logger.info(f"Configuration: USE_MQTT={USE_MQTT}, SERVER_PORT={SERVER_PORT}")
    
    if USE_MQTT:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_start()
            logger.info("🚀 MQTT client started")
            # Start background task to process MQTT messages from queue
            asyncio.create_task(process_mqtt_messages())
        except Exception as e:
            logger.error(f"Failed to connect MQTT: {e}")
            logger.warning("⚠️ Running in offline mode - no MQTT data")
            logger.info("💡 Set USE_MQTT=False in config to run in demo mode")
    else:
        logger.info("🎭 Running in DEMO MODE - generating fake data")
        asyncio.create_task(demo_loop())
    
    # Start offline checker
    asyncio.create_task(check_offline_clients())
    # Start stats logging
    asyncio.create_task(log_stats())

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 Shutting down Lab Monitoring System")
    if USE_MQTT:
        try:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        except:
            pass

async def log_stats():
    """Log statistics periodically"""
    while True:
        try:
            await asyncio.sleep(60)  # Log every minute
            uptime = datetime.now() - stats["start_time"]
            logger.info(
                f"📊 Stats - Uptime: {uptime}, "
                f"Messages: {stats['total_messages']}, "
                f"Failed: {stats['failed_messages']}, "
                f"Clients: {len(clients)}, "
                f"WS Connections: {len(active_connections)}, "
                f"Broadcast Failures: {stats['broadcast_failures']}"
            )
        except Exception as e:
            logger.error(f"Error logging stats: {e}")

# ==================== API ENDPOINTS ====================
@app.get("/")
async def get_index():
    return HTMLResponse(content=open("static/index.html", "r", encoding="utf-8").read())

@app.get("/api/clients")
async def get_clients():
    stats_payload = stats.copy()
    if isinstance(stats_payload.get("start_time"), datetime):
        stats_payload["start_time"] = stats_payload["start_time"].isoformat()
    return {
        "clients": [c.to_dict() if isinstance(c, ClientState) else c 
                   for c in clients.values()],
        "count": len(clients),
        "stats": stats_payload
    }

@app.get("/api/stats")
async def get_stats():
    """Endpoint untuk monitoring statistics"""
    uptime = datetime.now() - stats["start_time"]
    return {
        "uptime": str(uptime),
        "total_messages": stats["total_messages"],
        "failed_messages": stats["failed_messages"],
        "broadcast_failures": stats["broadcast_failures"],
        "mqtt_reconnects": stats["mqtt_reconnects"],
        "active_clients": len(clients),
        "websocket_connections": len(active_connections),
        "circuit_breaker_state": broadcast_circuit_breaker.state
    }

@app.post("/api/command")
async def execute_remote_command(request: Request):
    """
    Execute command di remote PC via MQTT
    
    Request body:
    {
        "hostname": "HOSTNAME",
        "command": "tasklist|ipconfig|whoami|systeminfo|taskkill"
    }
    
    Returns:
    {
        "status": "pending|error",
        "request_id": "unique_id",
        "message": "Command sent to agent..."
    }
    """
    try:
        data = await request.json()
        hostname = data.get('hostname')
        command = data.get('command')
        process_name = data.get('process_name', '').strip()
        
        # Validasi input
        if not hostname or not command:
            return JSONResponse(
                status_code=400,
                content={"error": "hostname dan command harus diisi"}
            )
        
        # Cek whitelist
        if command not in COMMAND_WHITELIST:
            logger.warning(f"Unauthorized command attempt: {command}")
            return JSONResponse(
                status_code=403,
                content={"error": f"Command '{command}' tidak diizinkan"}
            )
        
        # Validasi parameter tambahan (jika command memerlukannya)
        if command in COMMAND_PARAMS:
            required_params = COMMAND_PARAMS[command]
            for param in required_params:
                if param == 'process_name' and not process_name:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"Parameter 'process_name' diperlukan untuk command '{command}'"}
                    )
        
        # Cek apakah PC terhubung
        if hostname not in clients or clients[hostname].status != "online":
            return JSONResponse(
                status_code=404,
                content={"error": f"PC '{hostname}' tidak online"}
            )
        
        # Generate unique request ID
        request_id = f"{hostname}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"
        
        # Prepare command payload with params
        params = {}
        if command in COMMAND_PARAMS:
            for param in COMMAND_PARAMS[command]:
                if param == 'process_name':
                    params['process_name'] = process_name
        
        payload = {
            "command": command,
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "params": params
        }
        
        # Publish ke MQTT topic
        topic = f"lab/command/{hostname}"
        mqtt_client.publish(topic, json.dumps(payload))
        logger.info(f"Command published: {command} to {hostname} (ID: {request_id}, params: {params})")
        
        # Create event untuk wait result
        pending_commands[request_id] = asyncio.Event()
        
        # Return pending status
        return JSONResponse({
            "status": "pending",
            "request_id": request_id,
            "message": f"Command '{command}' dikirim ke {hostname}",
            "command": command,
            "hostname": hostname,
            "params": params
        })
    
    except Exception as e:
        logger.error(f"Error executing remote command: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

@app.get("/api/command/result/{request_id}")
async def get_command_result(request_id: str):
    """
    Get hasil command
    
    Returns:
    {
        "status": "completed|pending|notfound",
        "result": {...}
    }
    """
    if request_id in command_results:
        result = command_results[request_id]
        # Clean up
        if request_id in pending_commands:
            del pending_commands[request_id]
        return JSONResponse({
            "status": "completed",
            "result": result
        })
    elif request_id in pending_commands:
        return JSONResponse({
            "status": "pending",
            "message": "Menunggu hasil dari agent..."
        })
    else:
        return JSONResponse(
            status_code=404,
            content={"status": "notfound", "error": "Request ID tidak ditemukan"}
        )

@app.get("/api/commands/whitelist")
async def get_command_whitelist():
    """Get daftar command yang tersedia"""
    return JSONResponse({
        "commands": COMMAND_WHITELIST
    })

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"🔌 WebSocket connected. Total: {len(active_connections)}")
    
    try:
        # Send initial data
        # stats contains a datetime (start_time) -> convert to JSON-safe string
        stats_payload = stats.copy()
        if isinstance(stats_payload.get("start_time"), datetime):
            stats_payload["start_time"] = stats_payload["start_time"].isoformat()

        # Ensure stats_payload is JSON-safe (no datetime objects)
        stats_payload_safe = {
            k: (v.isoformat() if isinstance(v, datetime) else v)
            for k, v in stats_payload.items()
        }

        initial = json.dumps({
            "type": "initial",
            "clients": [c.to_dict() if isinstance(c, ClientState) else c
                       for c in clients.values()],
            "timestamp": datetime.now().isoformat(),
            "stats": stats_payload_safe
        })
        await websocket.send_text(initial)
        
        # Keep connection alive with ping/pong
        while True:
            try:
                # Wait for messages with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data:
                    # Echo acknowledgment
                    await websocket.send_text(json.dumps({"type": "ack", "timestamp": datetime.now().isoformat()}))
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": datetime.now().isoformat()})
                except Exception as e:
                    logger.debug(f"Failed to send ping: {e}")
                    break
            except Exception as e:
                logger.debug(f"WebSocket receive error: {e}")
                break
                
    except WebSocketDisconnect:
        logger.info("🔌 WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}\n{traceback.format_exc()}")
    finally:
        active_connections.discard(websocket)
        logger.info(f"🔌 WebSocket connection removed. Remaining: {len(active_connections)}")

@app.get("/health")
async def health_check():
    uptime = datetime.now() - stats["start_time"]
    stats_payload = stats.copy()
    if isinstance(stats_payload.get("start_time"), datetime):
        stats_payload["start_time"] = stats_payload["start_time"].isoformat()
    return {
        "status": "healthy",
        "mode": "demo" if not USE_MQTT else "mqtt",
        "mqtt_connected": mqtt_client.is_connected() if USE_MQTT else False,
        "active_clients": len(clients),
        "websocket_connections": len(active_connections),
        "uptime": str(uptime),
        "stats": stats_payload,
        "circuit_breaker_state": broadcast_circuit_breaker.state,
        "timestamp": datetime.now().isoformat()
    }

# ==================== MAIN ====================
if __name__ == "__main__":
    mode = "DEMO MODE" if not USE_MQTT else "MQTT MODE"
    print("=" * 60)
    print(f"  Lab Monitoring System v2.1.0 - {mode}")
    print("=" * 60)
    if USE_MQTT:
        print(f"  MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print(f"  Topic: {MQTT_TOPIC}")
    else:
        print("  🎭 Demo Mode: Generating fake data for 8 PCs")
    print(f"  Dashboard: http://localhost:{SERVER_PORT}")
    print(f"  API Stats: http://localhost:{SERVER_PORT}/api/stats")
    print(f"  Health Check: http://localhost:{SERVER_PORT}/health")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="info")