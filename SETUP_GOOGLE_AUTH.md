# Setup Google Login (OAuth) untuk Lab Monitoring 🔐

Panduan ini untuk mengaktifkan **Login dengan Gmail** di dashboard Lab Monitoring.
Setelah ini, hanya email yang Anda daftarkan yang bisa login.

---

## 📋 Prasyarat

- Sudah punya **akun Google** (Gmail)
- Server sudah bisa diakses (via ZeroTier)

---

## 🪜 Langkah 1: Buat Project di Google Cloud Console

1. Buka **https://console.cloud.google.com**
2. Login dengan akun Google Anda
3. **Buat Project Baru**:
   - Klik dropdown project (atas kiri) → **New Project**
   - Nama project: `lab-monitoring`
   - Klik **Create**
4. Tunggu sampai project terbuat, lalu pilih project tersebut

## 🪜 Langkah 2: Aktifkan Google OAuth API

1. Di menu kiri → **APIs & Services** → **Library**
2. Cari: **"Google Identity Services API"**
3. Klik **Enable**

## 🪜 Langkah 3: Buat OAuth Consent Screen

1. **APIs & Services** → **OAuth consent screen**
2. Pilih **"External"** → **Create**
3. Isi:
   - **App name**: `Lab Monitoring`
   - **User support email**: (email Anda)
   - **Developer contact**: (email Anda)
   - Klik **Save and Continue**
4. **Scopes**: Klik **Add or Remove Scopes**
   - Centang: `.../auth/userinfo.email`
   - Centang: `.../auth/userinfo.profile`
   - Klik **Update**
   - Klik **Save and Continue**
5. **Test Users**: Klik **Add Users**
   - Masukkan **email Anda** (dan email siapa pun yang boleh login)
   - Klik **Save and Continue**
6. Review, lalu **Back to Dashboard**

> ⚠️ **Catatan**: Karena app status "Testing", hanya email yang di daftarkan di **Test Users** yang bisa login. Nanti jika sudah siap, bisa publish ke **Production**.

## 🪜 Langkah 4: Buat OAuth Credentials (Client ID + Secret)

1. **APIs & Services** → **Credentials**
2. Klik **+ Create Credentials** → **OAuth client ID**
3. **Application type**: Pilih **"Web application"**
4. **Name**: `lab-monitoring-web`
5. **Authorized JavaScript origins**:
   - Klik **Add URI**
   - Masukkan: `http://localhost:8800`
   - Tambah lagi: `http://10.147.1.1:8800`
   - Tambah lagi: `http://[ZEROTIER_IP_SERVER]:8800` (ganti dengan IP ZeroTier server Anda)
   - Tambah lagi: `http://lab.domainanda.com:8800` (ganti dengan domain Anda)
6. **Authorized redirect URIs**:
   - Klik **Add URI**
   - Masukkan: `http://localhost:8800`
   - Masukkan: `http://10.147.1.1:8800`
   - Masukkan: `http://lab.domainanda.com:8800`
7. Klik **Create**

**Akan muncul popup dengan:**
```
Client ID:    123456789-xxxxx.apps.googleusercontent.com  ← COPY INI!
Client Secret: GOCSPX-xxxxxxxxxxxxxxxxxxxx                ← COPY INI!
```

> ⚠️ **SIMPAN Client ID dan Client Secret!** Akan digunakan di main.py

---

## ⚙️ Langkah 5: Update `requirements.txt`

Tambahkan ke `requirements.txt`:
```
google-auth==2.28.1
requests==2.31.0
```

Install:
```bash
# Di server Ubuntu
cd ~/lab-monitoring
source venv/bin/activate
pip install google-auth requests
```

---

## 🔧 Langkah 6: Update `main.py` - Backend

Buka `main.py` dan tambahkan perubahan berikut:

### 6.1 Tambahkan import baru (di bagian atas)
```python
# ==================== GOOGLE AUTH ====================
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
```

### 6.2 Tambahkan konfigurasi Google OAuth
```python
# ==================== GOOGLE OAUTH CONFIG ====================
# Ganti dengan Client ID dari Google Cloud Console!
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "123456789-xxxxx.apps.googleusercontent.com")

# Daftar email yang diizinkan login
# Hanya email dalam daftar ini yang bisa masuk!
ALLOWED_EMAILS = os.environ.get("ALLOWED_EMAILS", "email.anda@gmail.com,email.teman@gmail.com")
ALLOWED_EMAILS_LIST = [e.strip().lower() for e in ALLOWED_EMAILS.split(",")]
```

### 6.3 Tambahkan endpoint Google login
Tambahkan endpoint baru setelah `/api/login` atau di mana saja:

```python
@app.post("/api/auth/google")
async def google_auth(request: Request):
    """Login dengan Google"""
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        data = await request.json()
        id_token_str = data.get("id_token", "")
        
        if not id_token_str:
            return JSONResponse(status_code=400, content={"detail": "Token tidak ditemukan"})
        
        # Verifikasi token dengan Google
        try:
            token_info = id_token.verify_oauth2_token(
                id_token_str, 
                google_requests.Request(), 
                GOOGLE_CLIENT_ID
            )
        except ValueError as e:
            logger.warning(f"[SECURITY] Token Google tidak valid dari {client_ip}: {e}")
            return JSONResponse(status_code=401, content={"detail": "Token Google tidak valid"})
        
        # Ambil email dari token
        user_email = token_info.get("email", "").lower()
        user_name = token_info.get("name", user_email)
        
        # Cek apakah email diizinkan
        if user_email not in ALLOWED_EMAILS_LIST:
            logger.warning(f"[SECURITY] Email tidak terdaftar: {user_email} dari {client_ip}")
            audit_logger.info(f"GOOGLE_LOGIN_DENIED | Email: {user_email} | IP: {client_ip}")
            return JSONResponse(status_code=403, content={
                "detail": f"Akses ditolak. Email {user_email} tidak terdaftar. Hubungi admin."
            })
        
        # Buat session
        session_token = create_session()
        session = sessions[session_token]
        session["ip"] = client_ip
        session["user_agent"] = request.headers.get("User-Agent", "")
        session["email"] = user_email
        session["login_type"] = "google"
        
        # Simpan di cookie
        request.session["session"] = session_token
        
        logger.info(f"[AUDIT] Google Login berhasil: {user_email} dari {client_ip}")
        audit_logger.info(f"GOOGLE_LOGIN_SUCCESS | Email: {user_email} | IP: {client_ip}")
        
        return JSONResponse({
            "status": "success",
            "session": session_token,
            "email": user_email,
            "name": user_name,
            "message": f"Selamat datang, {user_name}!"
        })
        
    except Exception as e:
        logger.error(f"Google Auth error: {e}")
        return JSONResponse(status_code=400, content={"detail": "Gagal autentikasi dengan Google"})
```

---

## 🎨 Langkah 7: Update `static/index.html` - Frontend

### 7.1 Tambahkan library Google Identity Services di `<head>`
```html
<!-- Google Identity Services -->
<script src="https://accounts.google.com/gsi/client" async defer></script>
```

### 7.2 Ubah login screen menjadi tampilan dengan tombol Google
Cari bagian `<!-- Login Screen -->` dan ubah menjadi:

```html
<!-- Login Screen -->
<div id="login-screen">
    <div class="login-box animate-slide-in">
        <div class="text-center mb-8">
            <div class="w-4 h-4 bg-cyber-green rounded-full mx-auto mb-4 animate-glow"></div>
            <h1 class="text-2xl font-orbitron font-bold text-cyber-cyan neon-text mb-2">SECURE ACCESS</h1>
            <p class="text-xs text-cyber-border">Lab Monitoring System v1.4</p>
        </div>
        <div class="space-y-6">
            <!-- Google Sign-In Button -->
            <div id="g_id_onload"
                 data-client_id="123456789-xxxxx.apps.googleusercontent.com"
                 data-context="signin"
                 data-ux_mode="popup"
                 data-callback="handleGoogleCredential"
                 data-auto_prompt="false">
            </div>
            <div class="g_id_signin"
                 data-type="standard"
                 data-shape="rectangular"
                 data-theme="outline"
                 data-text="signin_with"
                 data-size="large"
                 data-logo_alignment="left">
            </div>
            
            <!-- Atau login manual dengan password -->
            <div class="relative">
                <div class="absolute inset-0 flex items-center">
                    <div class="w-full border-t border-cyber-border"></div>
                </div>
                <div class="relative flex justify-center text-xs">
                    <span class="bg-cyber-dark px-2 text-cyber-border">ATAU LOGIN DENGAN PASSWORD</span>
                </div>
            </div>
            
            <div>
                <label class="text-xs text-cyber-blue block mb-2">ADMIN PASSWORD</label>
                <input id="login-password" type="password" placeholder="Masukkan password admin..." 
                       onkeydown="if(event.key==='Enter') login()">
            </div>
            <div id="login-error" class="login-error"></div>
            <button id="login-btn" class="login-btn" onclick="login()">
                ⚡ AUTHENTICATE
            </button>
            <div class="text-center text-cyber-border text-[10px]">
                Unauthorized access is prohibited
            </div>
        </div>
    </div>
</div>
```

### 7.3 Tambahkan fungsi JavaScript untuk handle Google login
Tambahkan di bagian script (setelah fungsi login yang sudah ada):

```javascript
// ==================== GOOGLE LOGIN ====================
function handleGoogleCredential(response) {
    // Dapatkan ID token dari Google
    const idToken = response.credential;
    
    // Kirim ke backend
    fetch('/api/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token: idToken })
    })
    .then(res => res.json())
    .then(data => {
        if (data.status === 'success') {
            sessionToken = data.session;
            localStorage.setItem('session', sessionToken);
            document.getElementById('login-screen').classList.add('hidden');
            document.getElementById('main-header').style.display = 'block';
            document.getElementById('main-content').style.display = 'block';
            initDashboard();
            showNotification('success', `✅ Selamat datang, ${data.name || data.email}!`);
        } else {
            showNotification('error', '❌ ' + (data.detail || 'Gagal login dengan Google'));
        }
    })
    .catch(err => {
        showNotification('error', '❌ Gagal terhubung ke server');
        console.error('Google login error:', err);
    });
}
```

---

## 🚀 Langkah 8: Jalankan Server

```bash
cd ~/lab-monitoring
source venv/bin/activate

# Set environment variables (isi sesuai data Anda!)
export GOOGLE_CLIENT_ID="123456789-xxxxx.apps.googleusercontent.com"
export ALLOWED_EMAILS="email.anda@gmail.com,email.teman@gmail.com"

# Jalankan
python3 main.py
```

---

## ✅ Verifikasi

1. Buka dashboard: `http://lab.domainanda.com:8800` (atau via ZeroTier IP)
2. Akan muncul tombol **"Sign in with Google"**
3. Klik → pilih akun Google Anda
4. Jika email ada di `ALLOWED_EMAILS` → Dashboard terbuka ✅
5. Jika email tidak terdaftar → Muncul error "Akses ditolak" ❌

---

## 👥 Cara Menambah/Mengubah Email yang Diizinkan

### Via Environment Variable (Rekomendasi)
```bash
# Di server Ubuntu, stop dulu servernya (Ctrl+C)
export ALLOWED_EMAILS="anda@gmail.com,asisten1@gmail.com,asisten2@gmail.com"
python3 main.py
```

### Via Langsung di main.py
```python
# Edit baris ini di main.py:
ALLOWED_EMAILS_LIST = ["anda@gmail.com", "asisten1@gmail.com", "asisten2@gmail.com"]
```

---

## 🔍 Troubleshooting

| Masalah | Solusi |
|---------|--------|
| ❌ Tombol Google tidak muncul | Cek koneksi internet, atau cek apakah script Google blocked oleh adblocker |
| ❌ "Token Google tidak valid" | Pastikan GOOGLE_CLIENT_ID di main.py sama persis dengan di Google Console |
| ❌ "Email tidak terdaftar" | Tambahkan email tersebut ke ALLOWED_EMAILS_LIST |
| ❌ Popup Google "Error 400" | Cek **Authorized JavaScript origins** di Google Console (harus cocok dengan URL dashboard) |
| ❌ Login gagal di HP | Pastikan URL di HP sama dengan yang didaftarkan di Google Console |
| ❌ Error 403: redirect_uri_mismatch | Di Google Console → Credentials → edit OAuth client → tambahkan redirect URI yang benar |
| ❌ Login berhasil tapi dashboard kosong | Refresh halaman atau cek koneksi WebSocket |

---

> 💡 **Tips**: Semua email yang login tercatat di `audit.log`. Anda bisa cek siapa saja yang login dan dari IP mana.