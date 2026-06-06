# Setup Hosts File untuk Domain `ikyypantau.my.id`

## 🎯 Tujuan
Agar laptop Windows Anda bisa akses dashboard via:
```
http://ikyypantau.my.id:8800
```
(bukan pakai IP `10.147.1.1`)

---

## ✅ Langkah Edit Hosts File di Windows

### Step 1: Buka Notepad sebagai Administrator
1. Klik **Start** (logo Windows)
2. Ketik: **notepad**
3. Klik kanan **Notepad** → pilih **"Run as administrator"**
4. Klik **Yes** jika ada UAC prompt

### Step 2: Buka File Hosts
1. Di Notepad, klik **File** → **Open** (atau Ctrl+O)
2. Paste path ini ke kolom alamat:
```
C:\Windows\System32\drivers\etc\hosts
```
3. Klik **Open**
4. Jika tidak terlihat filenya, di sebelah kanan bawah ubah dari "Text Documents (*.txt)" menjadi **"All Files (*.*)"**

### Step 3: Tambahkan Baris Domain
1. Scroll ke bagian **paling bawah** file
2. Tambahkan baris baru:
```
10.147.1.1 ikyypantau.my.id
```
3. Klik **File** → **Save** (Ctrl+S)

**Isi file hosts Anda akan seperti ini:**
```
# Copyright (c) 1993-2009 Microsoft Corp.
#
# This is a sample HOSTS file...
# ...

127.0.0.1       localhost
::1             localhost

# --- Tambahkan ini di paling bawah! ---
10.147.1.1 ikyypantau.my.id
```

### Step 4: Test
1. Buka CMD:
```cmd
ping ikyypantau.my.id
```
Sekarang harus muncul: `Reply from 10.147.1.1` ✅

2. Buka browser, ketik:
```
http://ikyypantau.my.id:8800
```

---

## 📝 Cara untuk Device Lain (Client Windows)

Lakukan hal yang SAMA di setiap PC client yang akan akses dashboard:
```
C:\Windows\System32\drivers\etc\hosts
```
Tambahkan:
```
10.147.1.1 ikyypantau.my.id
```

---

## 🐧 Cara untuk Client Linux / Ubuntu (Nanti)

```bash
sudo nano /etc/hosts
```
Tambahkan:
```
10.147.1.1 ikyypantau.my.id
```
Simpan dengan Ctrl+X → Y → Enter.

---

> ✅ **Katakan "sudah"** jika Anda sudah selesai edit hosts file dan `ping ikyypantau.my.id` berhasil!