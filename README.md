# Lab Monitoring System - Secure Edition 🔒

Sistem monitoring real-time untuk lab komputer berbasis LAN dengan dashboard Cyberpunk. Fitur **keamanan multi-layer**, **remote command execution**, **efek hacker** di PC target, dan **Matrix Rain animation**.

## Fitur Utama

### 🖥️ Monitoring
- **Real-time** via WebSocket
- **MQTT Integration** untuk data dari agent PC
- **Grid View** semua PC dalam card informatif
- **Detail Modal** dengan info lengkap (CPU, RAM, Storage, GPU, Network, Processes, Files)
- **GPU Monitoring** (NVIDIA via pynvml, AMD/Intel via WMI)
- **Storage Full Scan** (akumulasi semua partisi/mount)
- **Sparkline Charts** untuk history CPU

### 🔒 Keamanan (Baru!)
| Fitur | Keterangan |
|---|---|
| **Login Page** | Password-protected dashboard, session 1 jam |
| **Dual Password** | Shutdown/restart/taskkill butuh password lagi |
| **Brute Force Protection** | Rate limiting + IP blocking (5 gagal = blok 5 menit) |
| **Session Management** | Auto logout + countdown timer di header |
| **Audit Log** | Semua aktivitas tercatat di `audit.log` |
| **Security Headers** | XSS, Clickjacking, nosniff protection |

### 💀 Hacker Effects (PC Target!)
Saat **Shutdown** atau **Restart** dijalankan, terminal **PC target** menampilkan:
1. **ASCII Skull** 💀 - Tengkorak merah besar
2. **Pesan Hacker** ⚠️ - "Sistem telah diakses pihak ketiga!"
3. **🌧️ MATRIX RAIN FULL SCREEN** - 80 frame animasi:
   - Setiap kolom terminal karakter jatuh
   - **Bright leading character** (putih/emas)
   - **Fade trail** (hijau terang → gelap)
   - **Random speed & trail length**
   - Cursor otomatis sembunyi/tampil
4. **ACCESS GRANTED** 🔓 - Detail koneksi berhasil
5. **Countdown Progress Bar** ⏳ `[█████░░░] 30 detik`
6. **Windows Popup** 🪟 - DENGAN IP address hacker!

### 🎯 Remote Command Execution
| Command | Deskripsi | Keamanan |
|---|---|---|
| `tasklist` | List proses | Normal |
| `ipconfig` | Network config | Normal |
| `whoami` | Current user | Normal |
| `systeminfo` | System info | Normal |
| `taskkill` | Kill process | 🔐 Butuh password! |
| `shutdown` | Matikan PC (30s) | 🔐 Butuh password! + 💀 Efek hacker |
| `restart` | Restart PC (30s) | 🔐 Butuh password! + 💀 Efek hacker |
| `cancel_shutdown` | Batal shutdown | Normal |

## Arsitektur

```
Device A (Server - 192.168.2.2)
├── Mosquitto MQTT Broker (port 1883)
└── main.py (Dashboard Server, port 8800)
    ├── 🔒 Login required
    ├── 🔐 Dual password untuk command berbahaya
    └── 📝 Audit log

Device B, C, D... (Client)
└── agent.py
    ├── Publish: lab/monitoring/{HOSTNAME}
    └── Subscribe: lab/command/{HOSTNAME}
    └── 💀 Efek hacker di terminal saat shutdown/restart
```

## Instalasi

```bash
pip install -r requirements.txt
```

## Konfigurasi

### Ubah Password Admin!
```python
# Di main.py - cari baris ini:
ADMIN_PASSWORD = os.environ.get("LAB_PASSWORD", "admin123")
# ^^^^ UBAH "admin123" dengan password kuat!
```
Atau via environment variable (lebih aman):
```bash
set LAB_PASSWORD=passwordkuatbanget123
```

### Konfigurasi IP
**Device A (Server):** `MQTT_BROKER = "localhost"` di `main.py`
**Device B (Client):** `BROKER_URL = "192.168.2.2"` di `agent.py`

## Cara Menjalankan

```bash
python main.py                    # Development mode
uvicorn main:app --host 0.0.0.0 --port 8800 --workers 4  # Production
```

**Demo mode (tanpa MQTT):** set `USE_MQTT = False` di `main.py`

## API Endpoints

| Endpoint | Method | Auth | Deskripsi |
|---|---|---|---|
| `/` | GET | ❌ | Dashboard |
| `/login` | GET | ❌ | Halaman login |
| `/api/login` | POST | ❌ | Login |
| `/api/logout` | POST | ✅ | Logout |
| `/api/auth/check` | GET | ❌ | Cek status login |
| `/ws` | WS | ❌ | WebSocket real-time |
| `/api/clients` | GET | ✅ | Data semua client |
| `/api/stats` | GET | ✅ | Statistics |
| `/api/command` | POST | ✅ | Execute remote command |
| `/api/command/result/{id}` | GET | ✅ | Hasil command |
| `/api/commands/whitelist` | GET | ✅ | Available commands |
| `/health` | GET | ❌ | Health check |

## Struktur File

```
├── main.py              # Backend FastAPI + MQTT + WebSocket + 🔒 Keamanan
├── agent.py             # Agent client PC + 💀 Efek hacker
├── requirements.txt     # Dependencies
├── static/index.html    # Frontend dashboard + 🔒 Login page
├── commands.log         # Log remote commands
├── audit.log            # 🔒 Log keamanan ( baru )
├── lab_monitoring.log   # Log backend
└── run_diagnostic.bat   # Diagnostic MQTT
```

## Keamanan Detail

### 🔐 Dual Password System
1. **Login** dengan password admin (session 1 jam)
2. Pilih command **shutdown / restart / taskkill**
3. Muncul input **password lagi** untuk verifikasi
4. Password dikirim terpisah, tervalidasi di backend
5. Dicatat di `audit.log` jika gagal

### 🛡️ Brute Force Protection
- **Rate Limiter**: 30 request/menit per IP
- **Command Limiter**: 5 command/menit per IP
- **Login Blocker**: 5x gagal → IP diblokir 5 menit
- **Session Timeout**: Auto logout setelah 1 jam

### 📝 Audit Trail
File `audit.log` mencatat:
```
LOGIN_SUCCESS | IP: 192.168.x.x
COMMAND | IP: ... | Target: PC-LAB-01 | Command: shutdown
DANGEROUS_CMD_NO_PASS | IP: ... | Command: restart
LOGOUT | IP: ...
UNAUTHORIZED_CMD | IP: ... | Command: format
```

## Troubleshooting

| Masalah | Solusi |
|---|---|
| Login gagal "Password salah" | Cek `ADMIN_PASSWORD` di main.py |
| IP diblokir 5 menit | Tunggu atau restart server |
| Session expired | Login ulang |
| MQTT connection failed | Pastikan Mosquitto running, cek firewall port 1883 |
| Tidak ada data di dashboard | Pastikan agent.py berjalan |
| Agent "Connection Refused" | Verifikasi IP broker |

## Changelog

**v2.1.0 Secure** - 🔒 Login + Dual Password + Rate Limiter + Audit Log + 💀 Matrix Rain + Hacker Effects
**v2.0.0** - Basic WebSocket + MQTT + Demo mode

> ⚠️ **Peringatan**: Efek hacker hanya visual di terminal. Tidak ada yang di-hack sungguhan.
> Sistem ini untuk edukasi monitoring lab komputer.