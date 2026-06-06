# Panduan Setting DNS ZeroTier - `ikyypantau.my.id`

## 🎯 Tujuan
Agar semua device yang join ZeroTier network `08752e18b163012d` bisa akses dashboard via:
```
http://ikyypantau.my.id:8800
```
(bukan pakai IP `10.147.1.1`)

---

## 📸 Panduan Langkah demi Langkah

### Langkah 1: Buka ZeroTier Console
1. Buka browser Chrome/Edge
2. Ketik: **https://my.zerotier.com**
3. Login dengan akun Anda

### Langkah 2: Klik Network
Di halaman utama, akan terlihat daftar network.
Klik **`08752e18b163012d`**

### Langkah 3: Cari Tab Advanced / DNS
Setelah masuk ke halaman network, lihat bagian **atas** ada beberapa tab:

```
[ 🏠 Summary ] [ 🔗 Members ] [ ⚙️ Advanced ] [ 📊 ... ]
```

Klik **"Advanced"**

### Langkah 4: Isi DNS Configuration
Scroll ke bawah sampai menemukan tulisan **"DNS Configuration"**

Isi seperti ini PERSIS:

```
Domain:  ikyypantau.my.id
Server:  10.147.1.1
```

**Contoh visual:**
```
┌──────────────────────────────────────────────────┐
│ 📋 DNS Configuration                             │
│                                                  │
│ Domain:  ikyypantau.my.id                       │
│ Server (IP):  10.147.1.1                        │
│                                                  │
│ ☐ Auto-assign domain to managed routes           │
│                                                  │
│ [ 💾 SAVE ]                                      │
└──────────────────────────────────────────────────┘
```

### Langkah 5: Klik SAVE
Klik tombol **Save** (atau centang hijau)

### Langkah 6: Restart ZeroTier di Laptop
Buka CMD **sebagai Administrator**, ketik:
```cmd
net stop "ZeroTier One" && net start "ZeroTier One"
```

### Langkah 7: Verifikasi
Buka browser, ketik:
```
http://ikyypantau.my.id:8800
```

---

## 🖼️ Ilustrasi (Simulasi)

**Ini yang akan Anda lihat di ZeroTier Console:**

```
█████████████████████████████████████████████████████████████
█                                                            █
█   ZeroTier Central                                         █
█                                                            █
█   Network: 08752e18b163012d                                 █
█                                                            █
█   [ Summary ] [ Members ] [ Advanced ]                     █
█                                                            █
█   ──────────────────────────────────────────────────        █
█                                                            █
█   ⚙️ ADVANCED SETTINGS                                     █
█                                                            █
█   ┌──────────────────────────────────────────┐              █
█   │ 📋 DNS Configuration                     │              █
█   │                                          │              █
█   │ Domain: [ikyypantau.my.id           ]    │  ← ISI INI   █
█   │ Server:  [10.147.1.1               ]     │  ← ISI INI   █
█   │                                          │              █
█   │ ☑ Auto-assign                            │              █
█   │                                          │              █
█   │ [ 💾 SAVE ]                              │              █
█   └──────────────────────────────────────────┘              █
█                                                            █
█████████████████████████████████████████████████████████████
```

---

## ⚠️ Catatan Penting:

- **Domain `ikyypantau.my.id` ini hanya bisa diakses** oleh device yang JOIN ZeroTier network Anda
- Orang lain di internet **tidak bisa** membuka `ikyypantau.my.id:8800` (karena DNS ZeroTier bersifat private)
- Setelah setting, **Restart ZeroTier** di laptop Windows agar DNS langsung aktif
- Nanti `nslookup ikyypantau.my.id` dari CMD **masih** akan menunjuk ke IP Cloudflare — itu NORMAL karena CMD tidak menggunakan DNS ZeroTier
- **Cara test yang benar**: buka langsung di browser `http://ikyypantau.my.id:8800`

---

**✅ Katakan "sudah selesai" jika Anda sudah mengisi dan menyimpan DNS di ZeroTier Console!**