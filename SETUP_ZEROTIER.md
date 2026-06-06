# Setup ZeroTier + Agent Multi-Platform untuk Lab Monitoring System 🌐

Panduan ini mencakup:
- ✅ ZeroTier: Server **Ubuntu 24.04 LTS** + Client **Windows/Linux/macOS**
- ✅ Agent berjalan di **berbagai OS** (Windows, Linux, macOS)
- ✅ Device dari **jaringan berbeda** (WiFi rumah, kantor, cellular) bisa terhubung ke dashboard
- ✅ **Akses dashboard via DOMAIN** Anda (misal: `http://lab.domainanda.com:8800`)

---

## 📋 Arsitektur Setelah ZeroTier + DNS

```
INTERNET 🌐
     │
     └── ZeroTier Virtual Network 🔷  (contoh: 10.147.x.x)
          │
          ├── [🖥️ SERVER - Ubuntu 24.04]  main.py + Mosquitto
          │    ├── ZeroTier IP: 10.147.1.1  (static)
          │    ├── Dashboard → port 8800  →  http://lab.domainanda.com:8800
          │    └── MQTT Broker → port 1883
          │
          ├── [💻 CLIENT A - Windows 11]  agent.py
          │    ├── ZeroTier IP: 10.147.1.2
          │    └── Browser bisa buka: http://lab.domainanda.com:8800 ✅
          │
          ├── [💻 CLIENT B - Ubuntu 24.04]  agent.py
          │    ├── ZeroTier IP: 10.147.1.3
          │    └── Browser bisa buka: http://lab.domainanda.com:8800 ✅
          │
          └── [📱 HANDPHONE/Device Lain]  (cukup join ZeroTier)
               └── Browser bisa buka: http://lab.domainanda.com:8800 ✅
```

---

## 📦 BAGIAN 1: Setup ZeroTier

### Langkah 1.1: Buat Akun & Jaringan ZeroTier

1. Buka **https://my.zerotier.com**
2. Register / Login dengan email
3. Klik **"Create A Network"**
4. **Network ID** akan muncul (16 karakter, contoh: `8056c2e21c000001`)
   - ⚠️ **CATAT Network ID ini!**
5. Beri nama: `Lab Monitoring`
6. Biarkan **IPv4 Auto-Assign** default (`10.147.0.0/16`)
7. **Enable Broadcast**: ✅ Centang
8. **Flow Rules**: Biarkan `accept` (default)

### Langkah 1.2: Install ZeroTier di Server (Ubuntu 24.04 LTS)

```bash
# Install ZeroTier
curl -s https://install.zerotier.com | sudo bash

# Join network
sudo zerotier-cli join [NETWORK_ID_ANDA]

# Cek status
sudo zerotier-cli listnetworks

# Aktifkan auto-start
sudo systemctl enable zerotier-one
sudo systemctl start zerotier-one
```

**Output yang diharapkan:**
```
200 listnetworks 8056c2e21c000001 10.147.1.1/16 OK PRIVATE ...
```

### Langkah 1.3: Install ZeroTier di Client Windows

1. Download: https://www.zerotier.com/download/
2. Install sebagai **Administrator**
3. Buka ZeroTier di system tray → **Join New Network**
4. Masukkan **Network ID**
5. Atau via CMD (Admin):
   ```cmd
   "C:\Program Files\ZeroTier\One\zerotier-cli.bat" join [NETWORK_ID_ANDA]
   ```

### Langkah 1.4: Install ZeroTier di Client Linux (Ubuntu/Debian)

```bash
curl -s https://install.zerotier.com | sudo bash
sudo zerotier-cli join [NETWORK_ID_ANDA]
```

### Langkah 1.5: Install ZeroTier di HP Android

1. Download **ZeroTier** dari Play Store
2. Masukkan **Network ID**
3. Di ZeroTier Console, authorize device (centang Auth?)

---

## 🌐 BAGIAN 2: Setup Domain via ZeroTier DNS (WAJIB!)

Bagian ini yang membuat domain Anda bisa dipakai untuk akses dashboard.

### Langkah 2.1: Set IP Static Server di ZeroTier Console

1. Buka **https://my.zerotier.com** → Klik Network Anda
2. Tab **"Members"** → Cari server Ubuntu Anda
3. **Centang "Auth?"**
4. **Klik IP address** server → Ganti ke `10.147.1.1` → Simpan (enter)
5. Beri Name: `Server-Ubuntu`

> ⚠️ **PENTING**: Server harus punya IP static agar konfigurasi DNS bisa konsisten!

### Langkah 2.2: Konfigurasi ZeroTier DNS

1. Di ZeroTier Console (network Anda), klik tab **"Advanced"** atau **"DNS"**
2. Cari bagian **"DNS Configuration"**
3. Isi:

```
| Field               | Isi                            |
|---------------------|--------------------------------|
| Domain              | lab.domainanda.com             |
| Server (Server IP)  | 10.147.1.1                     |
```

> **Contoh**: Jika domain Anda adalah `labmonitoring.my.id`, maka isi:
> - Domain: `lab.labmonitoring.my.id`
> - Server: `10.147.1.1`

4. Centang **"Auto-assign from range"** / **"Auto-assign"** agar semua device otomatis dapat konfigurasi DNS
5. **Klik Save**

**Tampilan di ZeroTier Console (kurang lebih):**
```
┌─────────────────────────────────────────────┐
│ 🖥️ DNS                                      │
│                                              │
│ Domain: lab.domainanda.com                   │
│ Server: 10.147.1.1                          │
│                                              │
│ ☑ Auto-assign domain to managed routes       │
│                                              │
│ [SAVE]                                       │
└─────────────────────────────────────────────┘
```

### Langkah 2.3: Restart ZeroTier di Semua Device

Agar konfigurasi DNS langsung terapply:

**Di Server Ubuntu:**
```bash
sudo systemctl restart zerotier-one
```

**Di Windows:**
- System tray → ZeroTier → Kanan klik → **Restart**
- Atau: Run `services.msc` → cari "ZeroTier One" → Restart

**Di HP Android:**
- Buka app ZeroTier → Matikan toggle → Nyalakan lagi

### Langkah 2.4: Verifikasi DNS Berfungsi

**Di Server Ubuntu:**
```bash
# Cek apakah ZeroTier DNS sudah aktif
resolvectl status | grep -A5 "zt"

# Test resolve domain
nslookup lab.domainanda.com
# Harusnya muncul: Name: lab.domainanda.com, Address: 10.147.1.1

# Atau pakai ping
ping lab.domainanda.com
# Harusnya reply dari 10.147.1.1 ✅
```

**Di Windows (CMD):**
```cmd
nslookup lab.domainanda.com
# Harusnya muncul: Address: 10.147.1.1
```

**Di HP Android:**
- Buka Chrome/Firefox
- Ketik `http://lab.domainanda.com:8800` di URL
- Harusnya dashboard muncul ✅

> 💡 **Catatan**: Jika `nslookup` belum resolve, coba restart ZeroTier atau restart browser.

---

## 🔧 BAGIAN 3: Setup Server di Ubuntu 24.04 LTS

### Langkah 3.1: Install Python & Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3 + pip + tools
sudo apt install -y python3 python3-pip python3-venv git

# Buat project directory
cd ~
mkdir lab-monitoring && cd lab-monitoring

# Buat virtual environment
python3 -m venv venv
source venv/bin/activate

# Clone project (atau copy file dari repo)
# git clone https://github.com/ikyy96/web-lab-monitoring-system.git .
# Atau copy manual main.py, requirements.txt, static/

# Install Python dependencies
pip install -r requirements.txt
```

### Langkah 3.2: Install & Konfigurasi Mosquitto MQTT Broker

```bash
# Install Mosquitto
sudo apt install -y mosquitto mosquitto-clients

# Edit konfigurasi
sudo nano /etc/mosquitto/mosquitto.conf
```

Tambahkan/edit isinya:
```
# Port listener (bisa dari semua interface, termasuk ZeroTier)
listener 1883 0.0.0.0

# Allow anonymous connections (untuk lab internal)
allow_anonymous true

# Optional: Persistence
persistence true
persistence_location /var/lib/mosquitto/

# Logging
log_dest file /var/log/mosquitto/mosquitto.log
log_type all
```

```bash
# Restart Mosquitto
sudo systemctl restart mosquitto

# Enable auto-start
sudo systemctl enable mosquitto

# Cek status
sudo systemctl status mosquitto

# Verifikasi port 1883
sudo netstat -tulpn | grep 1883
```

### Langkah 3.3: Firewall untuk Ubuntu

```bash
# Buka port untuk ZeroTier
sudo ufw allow from 10.147.0.0/16 to any port 1883 proto tcp
sudo ufw allow from 10.147.0.0/16 to any port 8800 proto tcp

# Jika pakai ufw, pastikan enable
sudo ufw enable
sudo ufw status
```

### Langkah 3.4: Update main.py

Edit `~/lab-monitoring/main.py`:

```python
# Cari bagian KONFIGURASI:
MQTT_BROKER = "10.147.1.1"  # ✅ Ganti localhost dengan ZeroTier IP server
```

Pastikan bagian bawah main.py:
```python
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8800)  # 0.0.0.0 agar bisa diakses dari ZeroTier
```

### Langkah 3.5: Jalankan Server

```bash
cd ~/lab-monitoring
source venv/bin/activate

# Mode development
python3 main.py

# Atau production dengan uvicorn langsung:
uvicorn main:app --host 0.0.0.0 --port 8800 --workers 4
```

---

## 🤖 BAGIAN 4: Setup Agent di Berbagai OS

### 4.1 Agent di Ubuntu 24.04 (Client)

```bash
# Install Python
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git

# Buat directory
mkdir ~/lab-agent && cd ~/lab-agent
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install psutil paho-mqtt pynvml  # pynvml optional (hanya jika ada GPU NVIDIA)

# Copy agent.py ke sini
# Atau clone repo:
# git clone https://github.com/ikyy96/web-lab-monitoring-system.git .
```

Edit `agent.py`:
```python
# Cari bagian konfigurasi, ubah BROKER_URL:
BROKER_URL = "10.147.1.1"  # ✅ ZeroTier IP server (static)
```

Jalankan agent:
```bash
cd ~/lab-agent
source venv/bin/activate
python3 agent.py
```

**Auto-start agent setiap boot (systemd service):**
```bash
sudo nano /etc/systemd/system/lab-agent.service
```

Isi:
```ini
[Unit]
Description=Lab Monitoring Agent
After=network.target zerotier-one.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/lab-agent
ExecStart=/home/YOUR_USERNAME/lab-agent/venv/bin/python3 /home/YOUR_USERNAME/lab-agent/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable lab-agent
sudo systemctl start lab-agent
sudo systemctl status lab-agent
```

### 4.2 Agent di Windows (Client)

```cmd
# Install Python dari python.org (centang "Add to PATH")

# Buka CMD / PowerShell
pip install psutil paho-mqtt pynvml
```

Edit `agent.py` → ubah `BROKER_URL = "10.147.1.1"`

Jalankan:
```cmd
python agent.py
```

**Auto-start via Windows Task Scheduler:**
1. Buka `taskschd.msc`
2. Create Task → Trigger: "At startup"
3. Action: Start program → `python` → Arguments: `agent.py` → Start in: `C:\path\to\lab-agent`

### 4.3 Agent di macOS (Client)

```bash
# Install Python jika belum
brew install python3

# Install dependencies
pip3 install psutil paho-mqtt pynvml
```

Edit `agent.py` → ubah `BROKER_URL = "10.147.1.1"`

Jalankan:
```bash
python3 agent.py
```

---

## ✅ BAGIAN 5: Verifikasi & Testing

### Test 1: Dashboard via Domain (Yang Anda Inginkan!)
Dari browser **PC / Laptop / HP manapun** yang terhubung ke ZeroTier:
```
http://lab.domainanda.com:8800
```
Login dengan password admin.

> 🎉 **SELAMAT!** Sekarang dashboard bisa diakses via domain Anda, bukan lagi pakai IP!

### Test 2: Client Online
Di dashboard akan muncul semua client yang menjalankan agent.py.

### Test 3: Remote Command
Coba jalankan command ke client (tasklist/ipconfig/whoami).

### Test 4: Test MQTT Langsung
```bash
mosquitto_sub -h 10.147.1.1 -t "lab/monitoring/#" -v
```

---

## 🔍 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| ❌ `lab.domainanda.com` tidak bisa diakses | Pastikan device sudah join ZeroTier ✅ |
| ❌ Domain tidak resolve ke IP | Restart ZeroTier di device, atau cek DNS config di ZeroTier Console |
| ❌ `nslookup` gagal | Di Windows: `ipconfig /flushdns` lalu restart ZeroTier |
| ❌ Dashboard tidak muncul di browser | Cek apakah server sudah jalan: `python3 main.py` |
| ❌ Port 8800 tidak bisa diakses | Pastikan main.py bind ke `0.0.0.0` |
| ❌ HP Android tidak bisa akses | Install ZeroTier dari Play Store, join network, authorize di Console |
| ❌ Agent "Connection Refused" ke MQTT | Pastikan Mosquitto running dan listen di `0.0.0.0:1883` |
| ❌ Ping gagal antar ZeroTier | Di ZeroTier Console, pastikan "Auth?" sudah dicentang |
| ❌ ZeroTier IP berubah setelah restart | Set IP manual di ZeroTier Console (tab Members → klik IP) |
| ❌ `zerotier-cli: command not found` | Setelah install, logout/login dulu, atau jalankan: `/usr/sbin/zerotier-cli` |

---

## 📝 Perbedaan Agent di Linux vs Windows

| Fitur | Windows | Linux (Ubuntu) | macOS |
|-------|---------|----------------|-------|
| CPU Monitoring | ✅ | ✅ | ✅ |
| RAM | ✅ | ✅ | ✅ |
| Storage | ✅ | ✅ (mount `/`) | ✅ |
| GPU NVIDIA | ✅ (pynvml) | ✅ (pynvml) | ✅ (pynvml) |
| GPU AMD/Intel | ✅ (WMI) | ❌ (tidak ada WMI) | ❌ |
| Network Traffic | ✅ | ✅ | ✅ |
| Top Processes | ✅ | ✅ | ✅ |
| Top Files | ✅ (Desktop/Docs/Downloads) | ✅ (Desktop/Docs/Downloads) | ✅ |
| Hacker Effects Matrix Rain | ✅ | ✅ (ANSI terminal) | ✅ |
| Windows Popup (`msg *`) | ✅ | ❌ (tidak relevan) | ❌ |
| Remote Shutdown | ✅ (`shutdown /s`) | ✅ (`shutdown -h`) | ✅ |
| Remote Restart | ✅ (`shutdown /r`) | ✅ (`shutdown -r`) | ✅ |
| Remote Taskkill | ✅ (`taskkill /IM`) | ✅ (`killall`) | ✅ |

---

> 💡 **Tips Penting**: 
> - **Domain** yang sudah diset di ZeroTier DNS hanya bisa diakses oleh device yang JOIN ZeroTier
> - Gunakan **ZeroTier IP static** untuk server (`10.147.1.1`) agar DNS tidak perlu diubah
> - Agent Linux bisa di-`systemd service` agar jalan otomatis setelah boot
> - Pastikan **Mosquitto** bind ke `0.0.0.0` (bukan hanya localhost) agar bisa menerima koneksi dari ZeroTier
> - Untuk akses dari browser HP: install **ZeroTier** dulu dari Play Store, baru buka `http://lab.domainanda.com:8800`