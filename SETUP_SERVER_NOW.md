# Setup Server Sekarang (Windows - Sementara)

Panduan ini untuk menjalankan dashboard di **laptop Windows** Anda sekarang sembari menunggu migrasi ke Ubuntu.

---

## ✅ Progres ZeroTier yang sudah selesai:

| Step | Status |
|------|--------|
| Network ID `08752e18b163012d` dibuat | ✅ |
| Laptop Windows join ZeroTier | ✅ |
| Device di-Auth & IP static `10.147.1.1` | ✅ |
| DNS `ikyypantau.my.id` → `10.147.1.1` | TUNGGU KONFIRMASI |

---

## 🪜 Langkah 1: Verifikasi DNS (CEK DULU)

Buka CMD di laptop Windows, ketik:
```cmd
nslookup ikyypantau.my.id
```

Jika muncul:
```
Address: 10.147.1.1
```
→ ✅ DNS berhasil

Jika gagal, restart ZeroTier dulu:
```cmd
net stop "ZeroTier One" && net start "ZeroTier One"
```

---

## 🪜 Langkah 2: Install Python (Jika Belum)

Buka CMD, cek Python:
```cmd
python --version
```

Jika belum ada, download: https://www.python.org/downloads/windows/
- Centang **"Add Python to PATH"** saat install

---

## 🪜 Langkah 3: Install Mosquitto MQTT (Untuk Agent)

1. Download Mosquitto: https://mosquitto.org/download/
2. Install (pilih folder `C:\Program Files\mosquitto`)
3. Buka CMD **Admin**, jalankan:
```cmd
net start mosquitto
```

Konfigurasi `C:\Program Files\mosquitto\mosquitto.conf`:
```
listener 1883 0.0.0.0
allow_anonymous true
```

Restart Mosquitto:
```cmd
net stop mosquitto && net start mosquitto
```

---

## 🪜 Langkah 4: Setup Project Dashboard

```cmd
cd C:\Users\LENOVO\OneDrive\Desktop\JARKOM

# Install dependencies
pip install -r requirements.txt
```

---

## 🪜 Langkah 5: Update main.py untuk ZeroTier

Edit `main.py` → cari bagian:
```python
MQTT_BROKER = "localhost"  # Ubah jadi:
MQTT_BROKER = "10.147.1.1"
```

---

## 🪜 Langkah 6: Jalankan Server

```cmd
cd C:\Users\LENOVO\OneDrive\Desktop\JARKOM
python main.py
```

Akses dashboard:
- Dari laptop sendiri: `http://localhost:8800`
- Dari device lain yang join ZeroTier: `http://ikyypantau.my.id:8800`

---

## ⚠️ Firewall Windows

Buka port agar bisa diakses dari ZeroTier:
```cmd
netsh advfirewall firewall add rule name="Dashboard 8800" dir=in action=allow protocol=TCP localport=8800
netsh advfirewall firewall add rule name="MQTT 1883" dir=in action=allow protocol=TCP localport=1883
```

---

## 📋 Checklist Status

| No | Item | Status |
|----|------|--------|
| 1 | ZeroTier Network `08752e18b163012d` | ✅ Dibuat |
| 2 | Laptop Windows join ZeroTier | ✅ Join |
| 3 | Device di-Auth + IP `10.147.1.1` | ✅ Authorized |
| 4 | DNS `ikyypantau.my.id` di ZeroTier | ⏳ **Set sekarang** |
| 5 | Python terinstall | ⏳ Cek |
| 6 | Mosquitto MQTT | ⏳ Cek |
| 7 | Dashboard running | ⏳ Nanti |

---

> 💡 **Katakan "sudah" atau "selesai"** jika Anda sudah setting DNS di ZeroTier Console, lalu kita lanjut ke step berikutnya! 😊