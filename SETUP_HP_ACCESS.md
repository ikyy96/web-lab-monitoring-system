# Akses Dashboard dari HP Android

## 📱 Cara Akses Dashboard dari HP

Karena HP Android **tidak bisa edit hosts file** (tanpa root), ada 2 cara:

### 🟢 Cara 1: Pakai IP Langsung (Termudah ✅)

Cukup buka browser HP, ketik:
```
http://10.190.143.33:8800
```

**Syarat:** HP harus install **ZeroTier** dan join network `08752e18b163012d`

### 🟢 Cara 2: Pakai Domain (Jika Ingin `ikyypantau.my.id`)

Di HP, install **ZeroTier** dulu, lalu:
1. Buka **Play Store** → Install **ZeroTier**
2. Buka app → Join Network: `08752e18b163012d`
3. Buka ZeroTier Console → Authorize HP
4. Buka Chrome/Opera → ketik:
```
http://10.190.143.33:8800
```

---

## 📱 Install ZeroTier di HP

1. Buka **Play Store**
2. Cari **"ZeroTier"**
3. Install
4. Buka app → **Join Network**
5. Masukkan: `08752e18b163012d`
6. Buka **https://my.zerotier.com** → Authorize HP di tab Members

---

## ✅ Dashboard Responsive untuk HP

Dashboard sudah saya update agar **responsive** di HP:
- ✅ Login box otomatis mengecil
- ✅ Statistik jadi 2 kolom (bukan 4)
- ✅ Tulisan otomatis mengecil
- ✅ Tombol dan dropdown menyesuaikan layar HP
- ✅ Card PC menyesuaikan ukuran

**Tinggal copy `static/index.html` yang sudah diupdate ke server!**