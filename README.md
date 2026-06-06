# 🔒 Lab Monitoring System - Secure Edition v2.1

Sistem monitoring real-time untuk lab komputer dengan dashboard **Cyberpunk theme**, fitur keamanan multi-layer, remote command execution, efek hacker, dan dukungan **Google Login** (OAuth 2.0). Bisa diakses dari **HP via ZeroTier**.

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-green)
![License](https://img.shields.io/badge/license-MIT-yellow)

---

## 📑 Daftar Isi

- [✨ Fitur Utama](#-fitur-utama)
- [🖥️ Monitoring](#️-monitoring)
- [🔐 Autentikasi & Keamanan](#-autentikasi--keamanan)
- [📱 Akses Mobile & ZeroTier](#-akses-mobile--zerotier)
- [💀 Hacker Effects](#-hacker-effects-pc-target)
- [🎯 Remote Command](#-remote-command-execution)
- [🚀 Instalasi](#-instalasi)
- [⚙️ Konfigurasi](#️-konfigurasi)
- [📖 Cara Menjalankan](#-cara-menjalankan)
- [🌐 API Endpoints](#-api-endpoints)
- [🐛 Troubleshooting](#-troubleshooting)
- [📁 Struktur File](#-struktur-file)
- [📝 Changelog](#-changelog)

---

## ✨ Fitur Utama

### 🖥️ Monitoring
| Fitur | Deskripsi |
|---|---|
| **Real-time** | Update data via WebSocket setiap 1 detik |
| **MQTT Integration** | Data dari agent PC via broker MQTT |
| **Grid View** | Semua PC dalam card informatif (1/2/3/4 kolom responsive) |
| **Detail Modal** | Info lengkap: OS, CPU, RAM, Storage, GPU, Network, Processes, Files |
| **GPU Monitoring** | NVIDIA (pynvml), AMD/Intel (WMI) dengan temperature & VRAM |
| **Storage Full Scan** | Akumulasi semua partisi/mount di PC |
| **Sparkline Charts** | History CPU real-time per PC |
| **Live Stats** | Total systems, online, avg CPU, avg RAM |

### 🔐 Autentikasi & Keamanan
| Fitur | Deskripsi |
|---|---|
| **🔑 Dual Login Method** | Login dengan **password admin** ATAU **Google OAuth** (Gmail) |
| **🔒 Login Page** | Password-protected dashboard, session 1 jam |
| **🛡️ Google OAuth 2.0** | Login via Gmail dengan whitelist email yang diizinkan |
| **🔐 Dual Password** | Shutdown/restart/taskkill butuh password lagi |
| **🚫 Brute Force Protection** | Rate limiting + IP blocking (5 gagal = blok 5 menit) |
| **⏱️ Session Management** | Auto logout + countdown timer di header |
| **📝 Audit Log** | Semua login (password & Google) tercatat di `audit.log` |
| **🔒 Security Headers** | XSS, Clickjacking, nosniff protection |
| **📧 Whitelist Email** | Hanya email yang didaftarkan yang bisa Google-login |

### 💀 Hacker Effects (PC Target!)
Saat **Shutdown** atau **Restart** dijalankan, terminal **PC target** menampilkan:
1. **ASCII Skull** 💀 - Tengkorak merah besar
2. **Pesan Hacker** ⚠️ - "Sistem telah diakses pihak ketiga!"
3. **🌧️ MATRIX RAIN FULL SCREEN** - 80 frame animasi
4. **ACCESS GRANTED** 🔓 - Detail koneksi berhasil
5. **Countdown Progress Bar** ⏳ `[█████░░░] 30 detik`
6. **Windows Popup** 🪟 - DENGAN IP address hacker

### 🎯 Remote Command Execution
| Command | Deskripsi | Keamanan |
|---|---|---|
| `tasklist` | List proses | Normal |
| `ipconfig` | Network config | Normal |
| `whoami` | Current user | Normal |
| `systeminfo` | System info | Normal |
| `taskkill` | Kill process | 🔐 Butuh password! |
| `shutdown` | Matikan PC (30s) | 🔐 + 💀 Efek hacker |
| `restart` | Restart PC (30s) | 🔐 + 💀 Efek hacker |
| `cancel_shutdown` | Batal shutdown | Normal |

---

## 📱 Akses Mobile & ZeroTier

Dashboard **fully responsive** untuk HP. Ada 2 mode tampilan:

### 🖥️ Desktop (≥ 768px)
- Header menampilkan: MQTT status, WebSocket status, Time, PC count, Session timer, Theme toggle, Logout button
- Stats: 4 kolom
- PC grid: 2/3/4 kolom (md/lg/xl)
- Modal: max-width 5xl (terbatas di tengah)

### 📱 Mobile (< 768px) - Hamburger Menu
- **Header kiri atas tetap**: 🟢 status dot + "LAB MONITORING"
- **Header kanan atas**: Tombol **Hamburger (☰)** yang jadi **X** saat aktif
- **Tap hamburger** → slide-in drawer dari kanan berisi:
  - 📊 Connection Status (MQTT, WebSocket)
  - ⏰ System Info (Time, PCs Online, Session)
  - 🌙 Theme Toggle
  - ⏻ Logout
- Stats: 2 kolom
- PC grid: 1 kolom
- Modal: full-screen
- Tap target: minimum 44x44px
- Font size: 16px (mencegah iOS zoom)

### 🌐 Setup Akses HP via ZeroTier

**1. Install ZeroTier di HP** (Play Store / App Store)
- Join Network ID: `08752e18b163012d`
- Authorize HP di `https://my.zerotier.com`

**2. Akses Dashboard**
- IP server ZeroTier (misal): `http://10.190.143.33:8800`
- Atau via DNS: `http://ikyypantau.my.id:8800` (kalau sudah setup DNS)

**3. Login**
- Pilih **Sign in with Google** (recommended) atau login password

Detail lengkap di: [`SETUP_HP_ACCESS.md`](SETUP_HP_ACCESS.md), [`SETUP_ZEROTIER.md`](SETUP_ZEROTIER.md)

---

## 🚀 Instalasi

```bash
# 1. Clone repository
git clone https://github.com/ikyy96/web-lab-monitoring-system.git
cd web-lab-monitoring-system

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Opsional) Setup Google Login
# Lihat: SETUP_GOOGLE_AUTH.md
```

### Requirements
- Python 3.8+
- Mosquitto MQTT Broker
- Modern browser (Chrome/Edge/Firefox/Safari)
- (Opsional) ZeroTier untuk akses HP

---

## ⚙️ Konfigurasi

### 🔐 1. Ubah Password Admin
```python
# Di main.py - cari baris ini:
ADMIN_PASSWORD = os.environ.get("LAB_PASSWORD", "admin123")
# ^^^^ UBAH "admin123" dengan password kuat!
```
Atau via environment variable (lebih aman):
```bash
# Windows
set LAB_PASSWORD=passwordkuatbanget123

# Linux/Mac
export LAB_PASSWORD=passwordkuatbanget123
```

### 📧 2. Setup Google OAuth Login
Lihat panduan lengkap di [`SETUP_GOOGLE_AUTH.md`](SETUP_GOOGLE_AUTH.md)

Ringkasan:
1. Buat OAuth Client ID di [Google Cloud Console](https://console.cloud.google.com)
2. Aktifkan Google Identity Services API
3. Tambahkan Authorized JavaScript origins (URL dashboard)
4. Set di `main.py`:
```python
GOOGLE_CLIENT_ID = "123456789-xxxxx.apps.googleusercontent.com"
ALLOWED_EMAILS = "email.anda@gmail.com,email.teman@gmail.com"
```

### 🌐 3. Konfigurasi IP
**Device A (Server):** `MQTT_BROKER = "localhost"` di `main.py`  
**Device B (Client):** `BROKER_URL = "192.168.2.2"` di `agent.py`

---

## 📖 Cara Menjalankan

```bash
# Development mode
python main.py

# Production (recommended)
uvicorn main:app --host 0.0.0.0 --port 8800 --workers 4

# Demo mode (tanpa MQTT, untuk testing)
# Set USE_MQTT = False di main.py
```

### 📱 Akses dari HP
```bash
# 1. Pastikan server sudah running
# 2. Install ZeroTier di HP, join network
# 3. Authorize HP di my.zerotier.com
# 4. Buka browser HP: http://[ZEROTIER_IP_SERVER]:8800
```

---

## 🌐 API Endpoints

| Endpoint | Method | Auth | Deskripsi |
|---|---|---|---|
| `/` | GET | ❌ | Dashboard (HTML) |
| `/login` | GET | ❌ | Halaman login |
| `/api/login` | POST | ❌ | Login dengan password |
| `/api/auth/google` | POST | ❌ | Login dengan Google OAuth |
| `/api/auth/check` | GET | ❌ | Cek status auth |
| `/api/logout` | POST | ✅ | Logout |
| `/ws` | WS | ✅ | WebSocket real-time updates |
| `/api/clients` | GET | ✅ | Data semua client |
| `/api/stats` | GET | ✅ | Statistics |
| `/api/command` | POST | ✅ | Execute remote command |
| `/api/command/result/{id}` | GET | ✅ | Hasil command |
| `/api/commands/whitelist` | GET | ✅ | Available commands |
| `/health` | GET | ❌ | Health check (MQTT status) |

---

## 🐛 Troubleshooting

| Masalah | Solusi |
|---|---|
| Login gagal "Password salah" | Cek `LAB_PASSWORD` di main.py atau environment variable |
| IP diblokir 5 menit | Tunggu atau restart server |
| Session expired | Login ulang (session 1 jam) |
| Google Sign-In button tidak muncul | Cek koneksi internet, atau `GOOGLE_CLIENT_ID` di main.py |
| "Email tidak terdaftar" | Tambahkan email ke `ALLOWED_EMAILS_LIST` di main.py |
| Google login popup error 400 | Cek **Authorized JavaScript origins** di Google Console |
| Login gagal di HP | Pastikan URL di HP sama dengan yang didaftarkan di Google Console |
| Dashboard tidak responsive di HP | Refresh browser, clear cache |
| Hamburger menu tidak muncul | Resize browser ke < 768px, atau cek DevTools mobile mode |
| MQTT connection failed | Pastikan Mosquitto running, cek firewall port 1883 |
| Tidak ada data di dashboard | Pastikan agent.py berjalan di PC client |
| Agent "Connection Refused" | Verifikasi IP broker di agent.py |

---

## 📁 Struktur File

```
├── main.py              # Backend FastAPI + MQTT + WebSocket + Auth (Password & Google)
├── agent.py             # Agent client PC + 💀 Efek hacker
├── requirements.txt     # Python dependencies
├── static/
│   └── index.html       # Frontend dashboard (responsive + Google Login + Hamburger Menu)
├── commands.log         # Log remote commands
├── audit.log            # Log keamanan (login, Google auth, dll)
├── lab_monitoring.log   # Log backend
├── README.md            # Dokumentasi ini
├── SETUP_HP_ACCESS.md   # Panduan setup HP
├── SETUP_ZEROTIER.md    # Panduan ZeroTier
├── SETUP_GOOGLE_AUTH.md # Panduan Google OAuth
├── SETUP_SERVER_NOW.md  # Quick start server
├── SETUP_ZEROTIER_DNS_GUIDE.md  # Setup DNS custom
├── SETUP_HOSTS_FILE.md  # Setup hosts file
├── IMPLEMENTATION_SUMMARY.txt   # Catatan implementasi
├── run_diagnostic.bat   # Diagnostic script
└── lab_monitoring.log   # Log file utama
```

---

## 🔒 Keamanan Detail

### 🔐 Password Login
1. User memasukkan password
2. Rate limiter: max 5x gagal → IP diblokir 5 menit
3. Session token di-generate, expire 1 jam
4. Token disimpan di localStorage + dikirim via header

### 📧 Google OAuth Login
1. User klik "Sign in with Google"
2. Popup Google muncul (atau One Tap)
3. User pilih akun Google mereka
4. ID Token dikirim ke backend `/api/auth/google`
5. Backend verify token dengan Google
6. Backend cek apakah email ada di `ALLOWED_EMAILS_LIST`
7. Jika ya → session dibuat, jika tidak → 403 Forbidden
8. Semua percobaan login tercatat di `audit.log`

### 🔐 Dual Password System (untuk command berbahaya)
1. User pilih **shutdown / restart / taskkill**
2. Muncul input **password admin** untuk verifikasi
3. Password dikirim terpisah, tervalidasi di backend
4. Gagal → tercatat di `audit.log` sebagai `DANGEROUS_CMD_NO_PASS`

### 🛡️ Brute Force Protection
- **Rate Limiter**: 30 request/menit per IP
- **Command Limiter**: 5 command/menit per IP
- **Login Blocker**: 5x gagal → IP diblokir 5 menit
- **Session Timeout**: Auto logout setelah 1 jam

### 📝 Audit Trail
File `audit.log` mencatat:
```
LOGIN_SUCCESS | IP: 192.168.x.x
GOOGLE_LOGIN_SUCCESS | Email: user@gmail.com | IP: 192.168.x.x
GOOGLE_LOGIN_DENIED | Email: hacker@evil.com | IP: 10.x.x.x
COMMAND | IP: ... | Target: PC-LAB-01 | Command: shutdown
DANGEROUS_CMD_NO_PASS | IP: ... | Command: restart
LOGOUT | IP: ...
UNAUTHORIZED_CMD | IP: ... | Command: format
```

---

## 📝 Changelog

### v2.1.0 (Current) - 2024
- 🔑 **Login dengan Google OAuth** (whitelist email)
- 🔔 **Notification system** (toast animasi success/error)
- 📱 **Hamburger Menu** untuk HP (drawer slide-in)
- 🎨 **Login page redesign** dengan Google button + divider
- ⚡ **Mobile responsive** lengkap (header, stats, modal, form, table)
- 🌓 **Touch-friendly tap targets** (min 44x44px)
- 💾 **CSS variables** untuk light/dark theme

### v2.0.0 - Secure Edition
- 🔒 Login password + session 1 jam
- 🔐 Dual password untuk command berbahaya
- 🛡️ Brute force protection + rate limiter
- 📝 Audit log
- 💀 Matrix Rain + Hacker Effects
- 🎯 Remote command execution (8 commands)
- 🌐 WebSocket real-time updates
- 🌓 Light/Dark theme toggle

### v1.0.0
- Basic WebSocket + MQTT + Demo mode

---

## 🤝 Kontribusi

Kontribusi welcome! Silakan:
1. Fork repo
2. Buat branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Buat Pull Request

---

## 📄 Lisensi

MIT License - Bebas digunakan untuk edukasi, penelitian, dan pengembangan.

---

> ⚠️ **Peringatan**: Efek hacker hanya visual di terminal. Tidak ada yang di-hack sungguhan. Sistem ini untuk **edukasi monitoring lab komputer**.

> 🔒 **Keamanan**: Selalu ubah `ADMIN_PASSWORD` default dan setup whitelist Google email sebelum production!

---

**Repository**: [github.com/ikyy96/web-lab-monitoring-system](https://github.com/ikyy96/web-lab-monitoring-system)  
**Issues**: [GitHub Issues](https://github.com/ikyy96/web-lab-monitoring-system/issues)  
**Dokumentasi Lengkap**: Lihat file `SETUP_*.md` di repository
