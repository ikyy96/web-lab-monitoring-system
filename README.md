# Lab Monitoring System - Cyberpunk Dashboard

Sistem monitoring real-time untuk lab komputer berbasis LAN dengan tampilan Cyberpunk/Dark Mode yang futuristik.

## 📋 Daftar Isi

- [Fitur](#-fitur)
- [Arsitektur Sistem](#-arsitektur-sistem)
- [Prerequisites](#-prerequisites)
- [Instalasi](#-instalasi)
- [Cara Menjalankan](#-cara-menjalankan)
- [Cara Menggunakan](#-cara-menggunakan)
- [Struktur Project](#-struktur-project)
- [MQTT Payload Format](#-mqtt-payload-format)
- [API Endpoints](#-api-endpoints)
- [Setup Multi-Device](#-setup-multi-device)
- [Remote Command Execution](#-remote-command-execution)
- [Fitur Keamanan](#-fitur-keamanan)
- [Error Handling & Improvements](#-error-handling--improvements)
- [Bug Fixes](#-bug-fixes)
- [Monitoring & Troubleshooting](#-monitoring--troubleshooting)
- [Update & Maintenance](#-update--maintenance)
- [Changelog](#-changelog)

---

## 🚀 Fitur

- **Real-time Monitoring**: Data update secara real-time melalui WebSocket
- **MQTT Integration**: Subscribe ke broker MQTT untuk menerima data dari agent
- **Dark Mode / Cyberpunk Theme**: Tampilan futuristik dengan neon colors
- **Grid View**: Menampilkan semua PC dalam bentuk card yang informatif
- **Detail Modal**: Klik card untuk melihat detail lengkap PC
- **Sparkline Charts**: Grafik mini untuk melihat trend CPU usage
- **GPU Monitoring**: Mendukung NVIDIA (via pynvml), AMD/Intel (via WMI)
- **Storage Full Scan**: Akumulasi semua partisi/drive (Windows) atau mount (Linux)
- **Remote Command Execution**: Jalankan command di remote PC via MQTT
- **Status Indicators**: Indikator visual untuk status online/offline
- **Responsive Design**: Tampilan optimal di berbagai ukuran layar

---

## 🏗 Arsitektur Sistem

```
Device A (192.168.2.2) - Server
├── Mosquitto MQTT Broker (port 1883)
└── main.py (Dashboard Server, port 8800)
    ├── Subscribe ke: lab/monitoring/+
    └── Subscribe ke: lab/command/result/+

Device B, C, D, ... (Client/Agent)
└── agent.py
    ├── Publish ke: lab/monitoring/{HOSTNAME}
    └── Subscribe ke: lab/command/{HOSTNAME}

MQTT Topics:
  Client → Backend: lab/monitoring/{hostname}      (monitoring data)
  Backend → Client: lab/command/{hostname}         (remote command)
  Client → Backend: lab/command/result/{hostname}  (command result)
```

---

## 📋 Prerequisites

- Python 3.8 atau lebih tinggi
- MQTT Broker (Mosquitto) - sudah berjalan di `localhost:1883` untuk Device A
- Agent.py sudah berjalan di setiap client PC

---

## 🛠️ Instalasi

### 1. Install Dependencies

```bash
# Buat virtual environment (opsional tapi disarankan)
python -m venv venv

# Aktifkan virtual environment
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Konfigurasi

**Device A (Server - main.py):**
```python
MQTT_BROKER = "localhost"      # Selalu localhost di Device A
MQTT_PORT = 1883
MQTT_TOPIC = "lab/monitoring/+"
SERVER_PORT = 8800             # Port dashboard
```

**Device B (Client - agent.py):**
```python
BROKER_URL = "192.168.2.2"     # IP Device A
PORT = 1883
```

---

## 🚀 Cara Menjalankan

### Mode Development

```bash
python main.py
```

### Mode Production (dengan uvicorn)

```bash
uvicorn main:app --host 0.0.0.0 --port 8800 --workers 4
```

### Mode Background (Linux/Mac)

```bash
nohup python main.py > monitoring.log 2>&1 &
```

### Mode Demo (tanpa MQTT)

Edit `main.py`:
```python
USE_MQTT = False  # Set False untuk mode demo
```
Lalu jalankan:
```bash
python main.py
```

---

## 📊 Cara Menggunakan

1. **Buka Dashboard**: Akses `http://localhost:8800` di browser
2. **Lihat Status**: Dashboard akan otomatis menampilkan PC yang terhubung
3. **Detail PC**: Klik pada card PC untuk melihat detail lengkap (OS, CPU, GPU, RAM, Storage, Network, Processes, Files)
4. **Remote Command**: Di modal detail, pilih command dari dropdown → klik RUN
5. **Real-time Update**: Data akan terupdate otomatis tanpa refresh

---

## 🔧 Struktur Project

```
JARKOM/
├── main.py              # Backend server (FastAPI + MQTT + WebSocket)
├── agent.py             # Agent yang berjalan di client PC
├── requirements.txt     # Python dependencies
├── README.md           # Dokumentasi lengkap
├── run_diagnostic.bat  # Auto-run diagnostic MQTT
├── test_mqtt_connection.py  # Skrip diagnostik koneksi MQTT
├── lab_monitoring.log  # Log backend (auto-generated)
├── commands.log        # Log command execution (auto-generated)
├── static/
│   └── index.html      # Frontend dashboard (Single Page Application)
```

---

## 📡 MQTT Payload Format

Agent mengirim data dengan format JSON berikut ke topik `lab/monitoring/{HOSTNAME}`:

```json
{
    "id": "Nama-PC",
    "status": "online",
    "user": "username",
    "time": "12:00:00",
    "info": {
        "uptime": "2h 30m",
        "os": "Linux Ubuntu",
        "cpu_name": "Intel(R) Core(TM) i7-10750H"
    },
    "network": {
        "down_mbps": 0.5,
        "traffic_in_gb": 1.2,
        "latency_ms": 10,
        "iface": "eth0",
        "ip": "10.230.250.5",
        "mac": "aa:bb:cc:dd:ee:ff"
    },
    "metrics": {
        "cpu": {
            "percent": 25,
            "threads": 8,
            "cores": 4,
            "ghz": 2.5,
            "max_ghz": 3.0
        },
        "ram_percent": 45,
        "ram": {
            "used_gb": 3.6,
            "total_gb": 8.0
        },
        "storage": {
            "total_gb": 240,
            "used_gb": 100,
            "free_gb": 140,
            "percent": 41.6
        },
        "gpu": [
            {
                "name": "NVIDIA GeForce RTX 3060",
                "type": "NVIDIA",
                "temperature": 65,
                "utilization": 45,
                "memory_util": 30,
                "memory_used_gb": 3.2,
                "memory_total_gb": 6.0
            }
        ],
        "top_processes": [
            {"name": "python", "cpu": 12.5, "mem": 1.2}
        ],
        "top_files": [
            {"name": "video.mp4", "path": "/path/to/file", "size_mb": 150}
        ]
    }
}
```

---

## 🔌 API Endpoints

### Dashboard
- `GET /` - Halaman dashboard utama
- `GET /health` - Health check endpoint

### WebSocket
- `WS /ws` - WebSocket connection untuk real-time updates

### REST API
| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| GET | `/api/clients` | Mendapatkan data semua client |
| GET | `/api/stats` | Statistics monitoring |
| POST | `/api/command` | Execute remote command |
| GET | `/api/command/result/{request_id}` | Get hasil command |
| GET | `/api/commands/whitelist` | List available commands |

---

## 🎨 Fitur Tampilan

- **Header**: Menampilkan status MQTT, WebSocket, waktu, dan jumlah PC
- **Stats Bar**: Total systems, online count, average CPU & RAM usage
- **PC Grid**: Card untuk setiap PC dengan:
  - Status indicator (hijau = online, merah = offline)
  - Nama PC dan IP address
  - Progress bars for CPU, RAM, Storage
  - Sparkline chart for CPU history
  - GPU info (jika tersedia)
  - Network info (download speed, latency)
  - User dan last seen time
- **Detail Modal**: Informasi lengkap termasuk:
  - System info (OS, uptime, user)
  - Network details (IP, MAC, interface, latency)
  - CPU specifications (name, cores, threads, clock speeds)
  - GPU information (name, type, temperature, utilization, VRAM)
  - Top 5 processes (name, CPU%, memory)
  - Top 5 largest files (name, path, size)
  - Remote Command Execution (dropdown + RUN button + output box)

---

## 📦 Setup Multi-Device

### Setup Device A (Dashboard & Broker)

#### 1. Pastikan Mosquitto Broker Running
```bash
# Windows - Cek apakah sudah running
tasklist | findstr mosquitto

# Jika belum, start Mosquitto
mosquitto -v
# Atau dari Services di Windows jika sudah di-install sebagai service
```

#### 2. Verifikasi Mosquitto Listening di Port 1883
```bash
# Test koneksi lokal
mosquitto_sub -h localhost -t "lab/monitoring/#"
```

#### 3. Jalankan Dashboard Server (main.py)
```bash
python main.py
```

Seharusnya output:
```
🚀 Starting Lab Monitoring System v2.1.0
Configuration: USE_MQTT=True, SERVER_PORT=8800
✅ Connected to MQTT Broker at localhost:1883
📡 Subscribed to: lab/monitoring/+
🌐 Server running at http://localhost:8800
```

Dashboard bisa diakses dari Device B: `http://192.168.2.2:8800`

---

### Setup Device B (atau Device lain - Agent)

#### 1. Copy agent.py ke Device B
```bash
# Copy agent.py ke folder yang sesuai
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Jalankan Agent
```bash
python agent.py
```

Seharusnya output:
```
[*] Mencari interface aktif dengan akses internet...
    [+] Terpilih: Ethernet (192.168.X.X)
[*] Menghubungkan ke broker MQTT 192.168.2.2:1883...
[✓] MQTT Terhubung ke 192.168.2.2:1883
[19:25:10] CPU: 15% (8 Threads)
[19:25:12] CPU: 14% (8 Threads)
```

---

### Testing Setup

#### Test 1: Mosquitto Running (Device A)
```bash
mosquitto_sub -h localhost -t "lab/monitoring/#"
# Jika muncul prompt tanpa error = OK
```

#### Test 2: Agent Connect (Device B)
```bash
python agent.py
# Cek apakah ada output "MQTT Terhubung" = OK
```

#### Test 3: Data Flow
1. Run agent.py di Device B
2. Di Device A, jalankan:
   ```bash
   mosquitto_sub -h localhost -t "lab/monitoring/+" -v
   ```
3. Seharusnya melihat data dari Device B setiap 2 detik

#### Test 4: Dashboard
1. Buka browser
2. Ke: `http://192.168.2.2:8800`
3. Seharusnya melihat Device B terdaftar dan data real-time

---

### Tambahan: Mosquitto Configuration

Jika Mosquitto tidak listen di network, edit config:

**Windows:** `C:\Program Files\mosquitto\mosquitto.conf`
```conf
listener 1883 0.0.0.0
allow_anonymous true
```

**Linux:** `/etc/mosquitto/mosquitto.conf`
```conf
listener 1883 0.0.0.0
allow_anonymous true
```

Restart Mosquitto setelah edit.

---

## 🖥 Remote Command Execution

Fitur untuk menjalankan command di remote PC melalui MQTT.

### Command yang Tersedia

| Command | Deskripsi | Platform |
|---------|-----------|----------|
| `tasklist` | List semua proses running | Windows: `tasklist`, Linux: `ps aux` |
| `ipconfig` | Network configuration | Windows: `ipconfig`, Linux: `ifconfig` |
| `whoami` | Current user info | Cross-platform |
| `systeminfo` | System information | Windows: `systeminfo`, Linux: `uname -a` |
| `taskkill` | Kill process | Windows: `taskkill /IM {name} /F`, Linux: `killall {name}` |
| `shutdown` | ⛔ **Matikan PC** (delay 30 detik) | Windows: `shutdown /s /t 30`, Linux: `shutdown -h +1` |
| `restart` | 🔄 **Restart PC** (delay 30 detik) | Windows: `shutdown /r /t 30`, Linux: `shutdown -r +1` |
| `cancel_shutdown` | ✅ **Batalkan shutdown/restart** | Windows: `shutdown /a`, Linux: `shutdown -c` |

### Alur Kerja (MQTT Flow)

```
User click "RUN" 
    ↓
Dashboard POST /api/command
    ↓
Backend publish ke lab/command/{hostname}
    ↓
Agent receive & execute command (max 10s)
    ↓
Agent publish result ke lab/command/result/{hostname}
    ↓
Backend receive & store result
    ↓
Dashboard polling GET /api/command/result/{request_id}
    ↓
Display result ke PC card output box
```

### Cara Testing

```bash
# Test API whitelist
curl http://localhost:8800/api/commands/whitelist

# Test execute command
curl -X POST http://localhost:8800/api/command \
  -H "Content-Type: application/json" \
  -d '{"hostname":"PC-NAME","command":"whoami"}'

# Test get result
curl http://localhost:8800/api/command/result/{request_id}
```

### Security Features
- ✅ **Whitelist command** - Hanya 5 command yang diizinkan
- ✅ **Timeout 10 detik** - Prevent infinite hanging
- ✅ **Thread lock** - Prevent concurrent execution di agent
- ✅ **PC online check** - Tidak bisa command PC offline
- ✅ **Request ID tracking** - Unique ID untuk setiap request
- ✅ **Logging ke file** - Semua command tercatat di `commands.log`

### Configuration

Jika ingin menambah/mengubah command, edit di:

**Agent.py:**
```python
ALLOWED_COMMANDS = {
    'tasklist': 'tasklist' if platform.system() == 'Windows' else 'ps aux',
    'ipconfig': 'ipconfig' if platform.system() == 'Windows' else 'ifconfig',
    # Tambah command baru di sini
}
```

**Main.py:**
```python
COMMAND_WHITELIST = {
    'tasklist': 'List processes',
    'ipconfig': 'Network configuration',
    # Update description di sini
}
```

**Static/Index.html:**
```html
<select class="command-dropdown" data-hostname="${client.id}">
    <option value="">Pilih Command...</option>
    <option value="tasklist">📋 Task List</option>
    <!-- Tambah option baru di sini -->
</select>
```

---

## 🛡️ Fitur Keamanan

### 1. Rate Limiting
- Broadcast dibatasi untuk mencegah flooding
- Health check adaptive untuk mengurangi load

### 2. Memory Protection
- Max clients: 1000
- Max history: 50 per client
- Cleanup disconnected clients

### 3. Timeout Protection
- Broadcast timeout: 5 detik per client
- Health check timeout: 5 detik
- WebSocket ping/pong: 30 detik

### 4. Error Isolation
- Circuit breaker mencegah cascade failure
- Global exception handler
- Safe update dengan try-catch

---

## 🔧 Error Handling & Improvements

### Masalah yang Pernah Terjadi

Berdasarkan log error yang dilaporkan:
1. WebSocket connected
2. Data sempat masuk
3. WebSocket disconnected
4. WebSocket connection failed
5. Backend crash/mati sejenak
6. Auto-reconnect berhasil setelah backend menyala lagi

**Analisis**: Backend sempat crash karena error serialisasi datetime object, lalu di-restart.

### Solusi yang Diterapkan

#### A. Circuit Breaker Pattern
```python
class CircuitBreaker:
    """Mencegah cascade failure dengan pattern circuit breaker"""
    - failure_threshold=10: Buka circuit setelah 10 failure berturut-turut
    - recovery_timeout=60: Coba recover setelah 60 detik
    - States: CLOSED (normal), OPEN (isolated), HALF_OPEN (testing)
```
**Manfaat**: Mencegah broadcast failure yang berulang-ulang menyebabkan crash total.

#### B. Validasi Payload MQTT yang Ketat
```python
def validate_payload_structure(payload: dict) -> bool:
    - Validasi tipe data (dict, int, float)
    - Check required fields
    - Log error detail untuk debugging
```
**Manfaat**: Mencegah crash akibat payload JSON yang korup atau tidak sesuai format.

#### C. Safe Update Client State
```python
def safe_update_client_state(client_id: str, data: dict):
    - Try-catch di setiap operasi
    - Validasi tipe data sebelum konversi
    - Limit maksimal clients (MAX_CLIENTS = 1000)
    - Limit history length (MAX_HISTORY_LENGTH = 50)
```
**Manfaat**: Mencegah memory leak dan crash akibat data tidak valid.

#### D. Safe Broadcast Update
```python
async def safe_broadcast_update():
    - Gunakan circuit breaker untuk json.dumps
    - Timeout per client (BROADCAST_TIMEOUT = 5 detik)
    - Hapus client yang disconnected
    - Track broadcast failures
```
**Manfaat**: Mencegah broadcast macet karena client yang lambat atau disconnected.

#### E. MQTT Reconnect dengan Exponential Backoff
- Delay awal: 5 detik
- Maksimal delay: 5 menit (300 detik)
- Delay digandakan setiap failure
- Reset ke 5 detik saat berhasil connect
**Manfaat**: Mencegah flooding reconnect request ke MQTT broker.

#### F. Enhanced Logging
```python
logging.basicConfig(
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('lab_monitoring.log', encoding='utf-8')
    ]
)
```
**Manfaat**: Semua error tercatat di file log untuk analisis.

#### G. Statistics Monitoring
```python
stats = {
    "total_messages": 0,
    "failed_messages": 0,
    "broadcast_failures": 0,
    "mqtt_reconnects": 0,
    "start_time": datetime.now()
}
```
**Manfaat**: Memantau kesehatan sistem secara real-time.

#### H. Global Exception Handler
```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log dan return error response
```
**Manfaat**: Mencegah crash akibat unhandled exception.

### Frontend Reconnect Optimization

#### A. Exponential Backoff dengan Jitter
```javascript
let reconnectInterval = 1000; // Start 1 detik
const maxReconnectInterval = 30000; // Max 30 detik
const reconnectJitter = 500; // Random jitter 500ms
```
**Manfaat**: Mencegah flooding reconnect request dan thundering herd.

#### B. Adaptive Health Check
```javascript
let healthCheckInterval = 10000; // Start 10 detik
const maxHealthCheckInterval = 60000; // Max 60 detik
// On success: reset ke 10 detik
// On failure: interval *= 1.5 (max 60 detik)
```
**Manfaat**: Saat server down, health check semakin jarang (tidak membebani).

#### C. Connection State Tracking
```javascript
let reconnectAttempts = 0;
// Log setiap attempt dengan nomor
// Reset saat berhasil connect
```
**Manfaat**: Memudahkan debugging dan monitoring.

### Performance Improvements

| Sebelum | Sesudah |
|---------|---------|
| ❌ Crash saat payload invalid | ✅ Robust error handling |
| ❌ Memory leak (history tidak dibatasi) | ✅ Memory protection |
| ❌ Reconnect spam (fixed interval 3 detik) | ✅ Exponential backoff (1s -> 30s) |
| ❌ Health check spam (fixed interval 10 detik) | ✅ Adaptive health check (10s -> 60s) |
| ❌ No error logging | ✅ Comprehensive logging |
| ❌ No statistics | ✅ Real-time statistics |

### Storage Full Scan Fix

- ✅ Storage adalah akumulasi semua partisi/drive (Windows) atau semua mount (Linux)
- ✅ Payload `metrics.storage` tetap format yang sama (total_gb/used_gb/free_gb/percent) supaya frontend tidak perlu diubah
- ✅ Nilai storage meningkat sesuai total disk keseluruhan

---

## 🐛 Bug Fixes

### Bug: Device Kedua Tidak Muncul di Dashboard

#### Problem
Device kedua (dan semua device) tidak muncul di dashboard meski sudah terhubung ke MQTT broker.

#### Root Cause
WebSocket connection gagal karena error `TypeError: Object of type datetime is not JSON serializable` pada 3 endpoint:

1. **`/ws` endpoint** (WebSocket) - `json.dumps()` mencoba serialize `stats` dict yang berisi `start_time` (datetime object)
2. **`/api/clients` endpoint** (REST API) - `stats.copy()` dikembalikan tanpa konversi datetime
3. **`/health` endpoint** - `stats.copy()` dikembalikan tanpa konversi datetime

#### Solution
Konversi `start_time` (datetime object) ke ISO format string sebelum JSON serialization di semua 3 endpoint:

```python
stats_payload = stats.copy()
if isinstance(stats_payload.get("start_time"), datetime):
    stats_payload["start_time"] = stats_payload["start_time"].isoformat()
return {..., "stats": stats_payload}
```

#### Changes Made
- ✅ `/ws` endpoint: WebSocket now properly serializes stats with converted datetime
- ✅ `/api/clients` endpoint: API returns JSON-safe stats dict
- ✅ `/health` endpoint: Health check now properly handles datetime conversion

---

## 🔍 Monitoring & Troubleshooting

### Cek Kesehatan Sistem
```bash
# Health check manual
curl http://localhost:8800/health

# Stats detail
curl http://localhost:8800/api/stats

# Cek log backend
tail -f lab_monitoring.log

# Cek log browser (Console)
# Tekan F12 -> Console
```

### Indikator Masalah

#### 1. Broadcast Failures Tinggi
```json
{"broadcast_failures": 100, "circuit_breaker_state": "OPEN"}
```
**Solusi**: 
- Cek jumlah WebSocket clients
- Cek network latency
- Restart backend jika perlu

#### 2. Failed Messages Tinggi
```json
{"failed_messages": 50, "total_messages": 1000}
```
**Solusi**:
- Cek format payload MQTT
- Validasi data di agent.py
- Cek log untuk error detail

#### 3. MQTT Tidak Connect
```json
{"mqtt_connected": false}
```
**Solusi**:
- Pastikan MQTT broker berjalan
- Cek konfigurasi MQTT_BROKER dan MQTT_PORT
- Cek firewall/port

#### 4. WebSocket disconnect berulang
**Solusi**:
- Cek network connectivity
- Monitor `broadcast_failures` di stats
- Cek jumlah active connections
- Restart backend jika perlu

### Log Patterns

#### Normal Operation
```
✅ Connected to MQTT Broker
📡 Subscribed to: lab/monitoring/+
🔌 WebSocket connected. Total: 1
📥 Received from PC-LAB-01: status=online
📊 Stats - Uptime: 0:05:00, Messages: 150, Failed: 0
```

#### Error Conditions
```
❌ MQTT connection failed. Return code: 1
⚠️ Disconnected from MQTT Broker (rc=1)
❌ Error processing MQTT message: Expecting value
❌ Broadcast failed: Circuit breaker is OPEN
```

### Troubleshooting Guide

#### Problem: Backend crash terus menerus
**Solution**:
1. Cek `lab_monitoring.log` untuk error detail
2. Validasi payload MQTT di agent.py
3. Pastikan format JSON sesuai ekspektasi
4. Test dengan mode demo (`USE_MQTT = False`)

#### Problem: WebSocket disconnect berulang
**Solution**:
1. Cek network connectivity
2. Monitor `broadcast_failures` di stats
3. Cek jumlah active connections
4. Restart backend jika perlu

#### Problem: Health check gagal terus
**Solution**:
1. Pastikan backend berjalan
2. Cek port 8800 tidak diblokir firewall
3. Test manual: `curl http://localhost:8800/health`
4. Cek log backend untuk error

#### Problem: Memory usage tinggi
**Solution**:
1. Cek jumlah clients di stats
2. Kurangi `MAX_CLIENTS` jika perlu
3. Kurangi `MAX_HISTORY_LENGTH`
4. Restart backend secara berkala

#### Agent: "Connection Refused"
**Solusi:**
- Cek apakah Mosquitto running di Device A
- Verifikasi IP address Device A benar
- Cek firewall (port 1883 perlu open)

#### Agent: "Koneksi Timeout"
**Solusi:**
- Network unreachable ke Device A
- Cek routing/connectivity
- Ping test: `ping 192.168.2.2`

#### Dashboard tidak menerima data
**Verifikasi:**
```bash
# Di Device A, test apakah data masuk ke MQTT
mosquitto_sub -h localhost -t "lab/monitoring/+" -v
```

#### Remote Command Issues
**Q: Command tidak tereksekusi**  
A: Pastikan:
- Agent.py running dan subscribe ke command topic
- PC status = "online" di dashboard
- Command ada di whitelist

**Q: Output tidak muncul**  
A: Cek:
- MQTT broker running
- Request ID valid
- Polling masih berjalan (max 30 detik)

**Q: Timeout error**  
A: Command mungkin butuh lebih dari 10 detik
- Increase timeout di `execute_command(timeout=20)`
- Atau optimize command yang dijalankan

### Debug Commands

```bash
# Check MQTT topics
mosquitto_sub -h localhost -v -t '#'

# Check commands.log
tail -f commands.log

# Check MQTT connection
python test_mqtt_connection.py

# Run diagnostic batch
run_diagnostic.bat
```

---

## 🛡️ Troubleshooting

### MQTT Connection Failed
- Pastikan MQTT broker berjalan dan dapat diakses
- Periksa koneksi jaringan ke broker
- Verifikasi IP dan port broker di `main.py`

### No Data Showing
- Pastikan agent.py berjalan di client PCs
- Periksa apakah client mengirim data ke topik yang benar
- Lihat log console untuk error messages

### WebSocket Connection Issues
- Pastikan firewall tidak memblokir port 8800
- Coba akses menggunakan HTTP (bukan HTTPS) untuk development

---

## 📝 Notes

- Dashboard akan otomatis mendeteksi PC baru yang mengirim data
- PC yang offline (tidak mengirim data) akan tetap ditampilkan dengan status offline
- Data history untuk sparkline chart disimpan maksimal 20 poin terakhir
- WebSocket akan otomatis reconnect jika koneksi terputus
- Command hanya bisa dijalankan ke PC dengan status "online"
- Semua command execution tercatat di `commands.log`

---

## 🔄 Update & Maintenance

Untuk update dependencies:
```bash
pip install --upgrade -r requirements.txt
```

Untuk melihat logs:
```bash
# Jika running di background
tail -f monitoring.log

# Log backend
tail -f lab_monitoring.log
```

---

## 📈 Next Steps (Optional)

Fitur tambahan yang bisa dikembangkan:

1. **Command history** - Store recent commands per PC
2. **Custom timeout** - Allow user to set timeout per command
3. **Parallel execution** - Run command di multiple PCs
4. **Scheduled commands** - Run command on schedule
5. **Remote shell** - Interactive command execution
6. **File transfer** - Download files via MQTT
7. **Process management** - GUI untuk kill process dengan pilihan proses
8. **Audit log** - User info + timestamp untuk setiap command

---

## 📝 Changelog

### v2.2.0 (2026-05-29)
- ✅ **Remote Shutdown/Restart PC** - Matikan atau restart PC dari dashboard
- ✅ **Cancel Shutdown** - Batalkan shutdown/restart yang sudah dijadwalkan
- ✅ **Delay 30 detik** - User punya waktu untuk menyimpan pekerjaan
- ✅ **Firewall fix scripts** - Script otomatis buka port firewall
- ✅ **Panduan setup lengkap** - File SETUP_GUIDE.md

### v2.1.0 (2026-05-27)
- ✅ Added robust error handling
- ✅ Implemented circuit breaker pattern
- ✅ Added exponential backoff reconnect
- ✅ Implemented adaptive health check
- ✅ Added comprehensive logging
- ✅ Added statistics monitoring
- ✅ Added memory protection
- ✅ Added timeout protection
- ✅ Enhanced MQTT validation
- ✅ Added global exception handler
- ✅ Remote Command Execution (tasklist, ipconfig, whoami, systeminfo, taskkill)
- ✅ GPU Monitoring (NVIDIA, AMD, Intel)
- ✅ Storage Full Scan (akumulasi semua partisi)
- ✅ Bug fix: datetime serialization error
- ✅ Demo mode (tanpa MQTT)

### v2.0.0 (Previous)
- Basic WebSocket + MQTT functionality
- Demo mode
- Simple reconnect logic

---

## 📄 License

Project ini dibuat untuk tujuan edukasi dan monitoring lab komputer.

---

**Developed with ❤️ for Lab Monitoring System**  
**Version**: 2.1.0 | **Status**: Stable ✅