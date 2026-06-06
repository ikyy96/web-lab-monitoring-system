"""
Lab Monitoring System - Complete Solution with Robust Error Handling
FastAPI + MQTT Subscriber + WebSocket + Demo Mode
Version: 2.2.0 - Google OAuth Edition
"""

import json
import asyncio
import logging
import random
import queue
import time
import traceback
import secrets
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, Set, Optional, Any, List
from dataclasses import dataclass, field
from functools import wraps

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import paho.mqtt.client as mqtt
import uvicorn

# ==================== GOOGLE OAUTH (Opsional) ====================
GOOGLE_AUTH_AVAILABLE = False
try:
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    pass

# ==================== KEAMANAN ====================
# Ubah password ini! Gunakan password yang kuat dan unik.
# Bisa juga via environment variable: set LAB_PASSWORD=passwordkuat
ADMIN_PASSWORD = os.environ.get("LAB_PASSWORD", "admin123")

# Secret key untuk session cookie (ubah ini!)
SECRET_KEY = os.environ.get("LAB_SECRET_KEY", secrets.token_hex(32))

# Token untuk agent.py (harus sama di agent.py)
AGENT_TOKEN = os.environ.get("LAB_AGENT_TOKEN", "lab-token-2024")

# Konfigurasi session
SESSION_MAX_AGE = 3600  # 1 jam auto logout
SESSION_REFRESH_AGE = 600  # Refresh session setiap 10 menit

# Rate limiting
RATE_LIMIT_WINDOW = 60  # Window dalam detik
RATE_LIMIT_MAX = 30     # Max request per window
COMMAND_RATE_LIMIT_MAX = 5  # Max command per window
FAILED_LOGIN_LIMIT = 5  # Max gagal login sebelum diblokir
FAILED_LOGIN_BLOCK = 300  # Blokir 5 menit

# ==================== GOOGLE OAUTH CONFIG ====================
# Client ID dari Google Cloud Console!
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "1024514167323-0pc62a62d85jrjor7tqaeme12lt7pk2n.apps.googleusercontent.com")

# ============ EMAIL WHITELIST MANAGEMENT ============
# File untuk persistensi daftar email yang diizinkan
ALLOWED_EMAILS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allowed_emails.json")

def load_allowed_emails():
    """Load daftar email yang diizinkan dari file JSON atau env var.
    Prioritas: file JSON > environment variable > default
    """
    # 1. Coba load dari file JSON
    if os.path.exists(ALLOWED_EMAILS_FILE):
        try:
            with open(ALLOWED_EMAILS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                emails = data.get("emails", [])
                if emails:
                    logger.info(f"📧 Loaded {len(emails)} allowed emails from {ALLOWED_EMAILS_FILE}")
                    return [e.strip().lower() for e in emails if e.strip()]
        except Exception as e:
            logger.warning(f"⚠️ Failed to load allowed_emails.json: {e}")
    
    # 2. Fallback ke environment variable
    env_emails = os.environ.get("ALLOWED_EMAILS", "")
    if env_emails:
        logger.info(f"📧 Loaded allowed emails from environment variable")
        return [e.strip().lower() for e in env_emails.split(",") if e.strip()]
    
    # 3. Default fallback
    logger.info(f"📧 Using default allowed emails")
    return ["rizkyharun122@gmail.com"]

def save_allowed_emails(emails_list):
    """Simpan daftar email ke file JSON."""
    try:
        # Normalize: lowercase, strip, unique
        normalized = sorted(set(e.strip().lower() for e in emails_list if e.strip()))
        data = {
            "emails": normalized,
            "last_updated": datetime.now().isoformat(),
            "total": len(normalized)
        }
        with open(ALLOWED_EMAILS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved {len(normalized)} emails to {ALLOWED_EMAILS_FILE}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to save allowed_emails.json: {e}")
        return False

# Daftar email yang diizinkan login - load setelah logger siap (lihat bawah)


# ==================== KONFIGURASI ====================
MQTT_BROKER = "10.190.143.166"
MQTT_PORT = 1883
MQTT_TOPIC = "lab/monitoring/+"
MQTT_COMMAND_RESULT_TOPIC = "lab/command/result/+"
MQTT_CLIENT_ID = f"monitoring_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
SERVER_PORT = 8800
USE_MQTT = True

# Error handling config
MAX_RECONNECT_DELAY = 300
INITIAL_RECONNECT_DELAY = 5
MAX_BROADCAST_RETRIES = 3
BROADCAST_TIMEOUT = 5
MAX_CLIENTS = 1000
MAX_HISTORY_LENGTH = 50
OFFLINE_TIMEOUT = 15

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

# Command berbahaya yang butuh konfirmasi password
DANGEROUS_COMMANDS = ['shutdown', 'restart', 'taskkill']

COMMAND_PARAMS = {
    'taskkill': ['process_name'],
}

# Setup command logger
command_logger = logging.getLogger('commands')
command_handler = logging.FileHandler('commands.log', encoding='utf-8')
command_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
command_logger.addHandler(command_handler)
command_logger.setLevel(logging.INFO)

# Setup audit logger
audit_logger = logging.getLogger('audit')
audit_handler = logging.FileHandler('audit.log', encoding='utf-8')
audit_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
audit_logger.addHandler(audit_handler)
audit_logger.setLevel(logging.INFO)

# Demo PC data
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

# Daftar email yang diizinkan login - load dari file/env/default
ALLOWED_EMAILS_LIST = load_allowed_emails()
print(f"[OK] [EMAIL WHITELIST] {len(ALLOWED_EMAILS_LIST)} email(s) terdaftar: {', '.join(ALLOWED_EMAILS_LIST)}")

# ==================== SECURITY UTILITIES ====================
class RateLimiter:
    """Rate limiter untuk mencegah brute force dan spam"""
    def __init__(self, window=60, max_requests=30):
        self.window = window
        self.max_requests = max_requests
        self.requests: Dict[str, list] = {}
    
    def is_allowed(self, key: str) -> bool:
        now = time.time()
        if key not in self.requests:
            self.requests[key] = []
        
        # Bersihkan request lama
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        
        if len(self.requests[key]) >= self.max_requests:
            return False
        
        self.requests[key].append(now)
        return True
    
    def get_remaining(self, key: str) -> int:
        now = time.time()
        if key not in self.requests:
            return self.max_requests
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window]
        return max(0, self.max_requests - len(self.requests[key]))


class FailedLoginTracker:
    """Tracker untuk gagal login"""
    def __init__(self, max_attempts=5, block_time=300):
        self.max_attempts = max_attempts
        self.block_time = block_time
        self.attempts: Dict[str, dict] = {}
    
    def record_failure(self, ip: str):
        if ip not in self.attempts:
            self.attempts[ip] = {"count": 0, "blocked_until": 0}
        self.attempts[ip]["count"] += 1
        if self.attempts[ip]["count"] >= self.max_attempts:
            self.attempts[ip]["blocked_until"] = time.time() + self.block_time
    
    def is_blocked(self, ip: str) -> bool:
        if ip not in self.attempts:
            return False
        if time.time() < self.attempts[ip]["blocked_until"]:
            return True
        if self.attempts[ip]["blocked_until"] > 0 and time.time() > self.attempts[ip]["blocked_until"]:
            self.attempts[ip] = {"count": 0, "blocked_until": 0}
        return False
    
    def reset(self, ip: str):
        if ip in self.attempts:
            self.attempts[ip] = {"count": 0, "blocked_until": 0}


# Rate limiter instances
api_rate_limiter = RateLimiter(window=60, max_requests=RATE_LIMIT_MAX)
command_rate_limiter = RateLimiter(window=60, max_requests=COMMAND_RATE_LIMIT_MAX)
login_tracker = FailedLoginTracker(max_attempts=FAILED_LOGIN_LIMIT, block_time=FAILED_LOGIN_BLOCK)


def verify_password(password: str) -> bool:
    """Verifikasi password admin"""
    # Support plain text (backward compatibility) dan hashed
    if password == ADMIN_PASSWORD:
        return True
    # Optional: support SHA256 hash
    if len(ADMIN_PASSWORD) == 64 and hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASSWORD:
        return True
    return False


def hash_session_token() -> str:
    """Generate session token"""
    return secrets.token_hex(32)


# ==================== ERROR HANDLING ====================
class CircuitBreaker:
    """Circuit breaker pattern untuk mencegah cascade failure"""
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
            else:
                raise Exception(f"Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
            raise

broadcast_circuit_breaker = CircuitBreaker(failure_threshold=10, recovery_timeout=60)

# ==================== COMMAND HANDLING ====================
pending_commands: Dict[str, asyncio.Event] = {}
command_results: Dict[str, dict] = {}

# ==================== SESSION MANAGEMENT ====================
sessions: Dict[str, dict] = {}

def create_session() -> str:
    """Buat session baru"""
    token = hash_session_token()
    sessions[token] = {
        "created_at": time.time(),
        "last_active": time.time(),
        "ip": "",
        "user_agent": ""
    }
    return token

def validate_session(token: str) -> bool:
    """Validasi session token"""
    if token not in sessions:
        return False
    session = sessions[token]
    # Cek session timeout
    if time.time() - session["last_active"] > SESSION_MAX_AGE:
        del sessions[token]
        return False
    # Refresh last active time
    session["last_active"] = time.time()
    return True

def refresh_session(token: str) -> bool:
    """Refresh session jika dalam waktu refresh window"""
    if token not in sessions:
        return False
    session = sessions[token]
    if time.time() - session["last_active"] > SESSION_REFRESH_AGE:
        session["last_active"] = time.time()
    return True

def cleanup_sessions():
    """Bersihkan session expired"""
    now = time.time()
    expired = [t for t, s in sessions.items() if now - s["last_active"] > SESSION_MAX_AGE]
    for t in expired:
        del sessions[t]

# ==================== FASTAPI APP ====================
app = FastAPI(title="Lab Monitoring System", version="2.1.0 Secure")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session middleware untuk cookie-based sessions
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_MAX_AGE)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "type": type(exc).__name__}
    )


# ==================== AUTH MIDDLEWARE ====================
async def check_auth(request: Request):
    """Auth check for API endpoints"""
    # Cek session token dari header
    auth_header = request.headers.get("Authorization", "")
    session_token = ""
    
    if auth_header.startswith("Bearer "):
        session_token = auth_header[7:]
    elif "session" in request.session:
        session_token = request.session.get("session", "")
    
    if not session_token or not validate_session(session_token):
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Unauthorized access attempt from {client_ip}: {request.url.path}")
        raise HTTPException(status_code=401, detail="Unauthorized. Silakan login terlebih dahulu.")
    
    return session_token


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Rate limiting per IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Skip rate limit untuk static files dan login
    path = request.url.path
    if not path.startswith("/static") and path != "/" and path != "/login" and path != "/api/login":
        if not api_rate_limiter.is_allowed(f"api:{client_ip}"):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Silakan tunggu beberapa saat."}
            )
    
    # Security headers
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    return response


# ==================== AUTH ENDPOINTS ====================
@app.get("/login")
async def login_page():
    """Halaman login"""
    return HTMLResponse(content=open("static/index.html", "r", encoding="utf-8").read())


@app.post("/api/login")
async def api_login(request: Request):
    """API login"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Cek apakah IP diblokir
    if login_tracker.is_blocked(client_ip):
        remaining = int(login_tracker.attempts[client_ip]["blocked_until"] - time.time())
        return JSONResponse(
            status_code=429,
            content={"detail": f"Terlalu banyak percobaan login. Coba lagi dalam {remaining} detik."}
        )
    
    try:
        data = await request.json()
        password = data.get("password", "")
        
        if not verify_password(password):
            login_tracker.record_failure(client_ip)
            remaining = COMMAND_RATE_LIMIT_MAX - login_tracker.attempts[client_ip]["count"] if client_ip in login_tracker.attempts else COMMAND_RATE_LIMIT_MAX
            logger.warning(f"[SECURITY] Login gagal dari IP {client_ip}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Password salah!", "remaining": max(0, FAILED_LOGIN_LIMIT - login_tracker.attempts.get(client_ip, {}).get("count", 0))}
            )
        
        # Login berhasil - buat session
        login_tracker.reset(client_ip)
        session_token = create_session()
        session = sessions[session_token]
        session["ip"] = client_ip
        session["user_agent"] = request.headers.get("User-Agent", "")
        
        # Simpan di cookie session juga
        request.session["session"] = session_token
        
        logger.info(f"[AUDIT] Login berhasil dari {client_ip}")
        audit_logger.info(f"LOGIN_SUCCESS | IP: {client_ip}")
        
        return JSONResponse({
            "status": "success",
            "session": session_token,
            "message": "Login berhasil!"
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return JSONResponse(status_code=400, content={"detail": "Request tidak valid"})


@app.post("/api/logout")
async def api_logout(request: Request):
    """API logout"""
    session_token = request.session.get("session", "")
    if session_token in sessions:
        client_ip = request.client.host if request.client else "unknown"
        logger.info(f"[AUDIT] Logout dari {client_ip}")
        audit_logger.info(f"LOGOUT | IP: {client_ip}")
        del sessions[session_token]
    request.session.clear()
    return JSONResponse({"status": "success", "message": "Logout berhasil!"})


@app.get("/api/auth/check")
async def check_auth_status(request: Request):
    """Cek status autentikasi"""
    session_token = request.session.get("session", "")
    if session_token and validate_session(session_token):
        remaining = int(sessions[session_token]["last_active"] + SESSION_MAX_AGE - time.time())
        return JSONResponse({
            "authenticated": True,
            "session_remaining": max(0, remaining)
        })
    return JSONResponse({"authenticated": False})


# ==================== GOOGLE OAUTH ENDPOINT ====================
@app.post("/api/auth/google")
async def google_auth(request: Request):
    """Login dengan Google"""
    client_ip = request.client.host if request.client else "unknown"
    
    # Cek apakah Google OAuth sudah dikonfigurasi
    if not GOOGLE_CLIENT_ID:
        return JSONResponse(status_code=400, content={
            "detail": "Google OAuth belum dikonfigurasi. Set GOOGLE_CLIENT_ID dan ALLOWED_EMAILS."
        })
    
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
        if ALLOWED_EMAILS_LIST and user_email not in ALLOWED_EMAILS_LIST:
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


# ==================== EMAIL WHITELIST MANAGEMENT (ADMIN) ====================
def is_valid_email(email: str) -> bool:
    """Validasi format email sederhana."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email.strip()) is not None


@app.get("/api/admin/emails")
async def get_allowed_emails(request: Request, session=Depends(check_auth)):
    """
    List semua email yang diizinkan untuk Google login.
    Auth: hanya user yang sudah login yang bisa akses.
    """
    client_ip = request.client.host if request.client else "unknown"
    try:
        last_updated = None
        if os.path.exists(ALLOWED_EMAILS_FILE):
            with open(ALLOWED_EMAILS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                last_updated = data.get("last_updated")

        return JSONResponse({
            "status": "success",
            "emails": ALLOWED_EMAILS_LIST,
            "total": len(ALLOWED_EMAILS_LIST),
            "last_updated": last_updated,
            "source": "file" if os.path.exists(ALLOWED_EMAILS_FILE) else "env_or_default",
            "file_path": ALLOWED_EMAILS_FILE
        })
    except Exception as e:
        logger.error(f"Error getting allowed emails from {client_ip}: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Error: {str(e)}"})


@app.post("/api/admin/emails")
async def add_allowed_email(request: Request, session=Depends(check_auth)):
    """
    Tambahkan email baru ke whitelist.
    Body: {"email": "user@gmail.com"} atau {"emails": ["a@x.com", "b@y.com"]}
    """
    global ALLOWED_EMAILS_LIST
    client_ip = request.client.host if request.client else "unknown"
    try:
        data = await request.json()
        # Support single email atau multiple
        new_emails = []
        if 'email' in data:
            new_emails.append(data['email'])
        elif 'emails' in data:
            new_emails = data['emails']
        else:
            return JSONResponse(status_code=400, content={"detail": "Body harus berisi 'email' atau 'emails'"})

        # Validasi format
        valid_emails = []
        invalid_emails = []
        for email in new_emails:
            email = email.strip().lower()
            if is_valid_email(email):
                if email not in ALLOWED_EMAILS_LIST:
                    valid_emails.append(email)
                else:
                    invalid_emails.append(f"{email} (sudah ada)")
            else:
                invalid_emails.append(f"{email} (format invalid)")

        if not valid_emails:
            return JSONResponse(status_code=400, content={
                "detail": "Tidak ada email valid untuk ditambahkan",
                "invalid": invalid_emails
            })

        # Tambahkan ke list
        ALLOWED_EMAILS_LIST.extend(valid_emails)
        # Save ke file
        if save_allowed_emails(ALLOWED_EMAILS_LIST):
            logger.info(f"[AUDIT] {len(valid_emails)} email(s) ditambahkan oleh {client_ip}: {valid_emails}")
            audit_logger.info(f"EMAILS_ADDED | IP: {client_ip} | Emails: {', '.join(valid_emails)}")
            return JSONResponse({
                "status": "success",
                "message": f"{len(valid_emails)} email berhasil ditambahkan",
                "added": valid_emails,
                "invalid": invalid_emails if invalid_emails else None,
                "total": len(ALLOWED_EMAILS_LIST)
            })
        else:
            return JSONResponse(status_code=500, content={"detail": "Gagal menyimpan ke file"})

    except Exception as e:
        logger.error(f"Error adding allowed email from {client_ip}: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Error: {str(e)}"})


@app.delete("/api/admin/emails/{email}")
async def remove_allowed_email(email: str, request: Request, session=Depends(check_auth)):
    """
    Hapus email dari whitelist.
    URL: /api/admin/emails/{email}
    """
    global ALLOWED_EMAILS_LIST
    client_ip = request.client.host if request.client else "unknown"
    try:
        email_lower = email.strip().lower()

        if email_lower not in ALLOWED_EMAILS_LIST:
            return JSONResponse(status_code=404, content={
                "detail": f"Email '{email_lower}' tidak ditemukan di whitelist"
            })

        # Jangan izinkan hapus semua email (minimal 1)
        if len(ALLOWED_EMAILS_LIST) <= 1:
            return JSONResponse(status_code=400, content={
                "detail": "Tidak bisa hapus email terakhir! Minimal harus ada 1 email terdaftar."
            })

        # Hapus dari list
        ALLOWED_EMAILS_LIST.remove(email_lower)

        # Save ke file
        if save_allowed_emails(ALLOWED_EMAILS_LIST):
            logger.info(f"[AUDIT] Email {email_lower} dihapus oleh {client_ip}")
            audit_logger.info(f"EMAIL_REMOVED | IP: {client_ip} | Email: {email_lower}")
            return JSONResponse({
                "status": "success",
                "message": f"Email '{email_lower}' berhasil dihapus",
                "removed": email_lower,
                "total": len(ALLOWED_EMAILS_LIST)
            })
        else:
            return JSONResponse(status_code=500, content={"detail": "Gagal menyimpan ke file"})

    except Exception as e:
        logger.error(f"Error removing allowed email from {client_ip}: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Error: {str(e)}"})


@app.post("/api/admin/emails/reload")
async def reload_allowed_emails(request: Request, session=Depends(check_auth)):
    """
    Reload daftar email dari file (jika diedit manual di server).
    """
    global ALLOWED_EMAILS_LIST
    client_ip = request.client.host if request.client else "unknown"
    try:
        ALLOWED_EMAILS_LIST = load_allowed_emails()
        logger.info(f"[AUDIT] Email whitelist direload oleh {client_ip}: {len(ALLOWED_EMAILS_LIST)} email(s)")
        return JSONResponse({
            "status": "success",
            "message": f"Berhasil reload {len(ALLOWED_EMAILS_LIST)} email dari file",
            "emails": ALLOWED_EMAILS_LIST
        })
    except Exception as e:
        logger.error(f"Error reloading emails: {e}")
        return JSONResponse(status_code=500, content={"detail": f"Error: {str(e)}"})


# ==================== CLIENT STATE ====================
clients: Dict[str, dict] = {}
active_connections: Set[WebSocket] = set()
authenticated_ws: Set[WebSocket] = set()

stats = {
    "total_messages": 0,
    "failed_messages": 0,
    "broadcast_failures": 0,
    "mqtt_reconnects": 0,
    "start_time": datetime.now()
}


def get_safe_stats():
    """Return stats dict with datetime converted to ISO string for JSON safety."""
    s = stats.copy()
    if isinstance(s.get("start_time"), datetime):
        s["start_time"] = s["start_time"].isoformat()
    return s


@dataclass
class ClientState:
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
    try:
        if not isinstance(payload, dict):
            return False
        if 'metrics' in payload:
            metrics = payload['metrics']
            if not isinstance(metrics, dict):
                return False
            if 'cpu' in metrics:
                cpu = metrics['cpu']
                if not isinstance(cpu, dict):
                    return False
                if 'percent' in cpu and not isinstance(cpu['percent'], (int, float)):
                    return False
            if 'ram_percent' in metrics and not isinstance(metrics['ram_percent'], (int, float)):
                return False
        return True
    except Exception as e:
        logger.error(f"Error validating payload: {e}")
        return False


def safe_update_client_state(client_id: str, data: dict):
    try:
        if client_id not in clients and len(clients) >= MAX_CLIENTS:
            logger.warning(f"Maximum clients ({MAX_CLIENTS}) reached. Ignoring new client: {client_id}")
            return
        if client_id not in clients:
            clients[client_id] = ClientState(id=client_id)
        client = clients[client_id]
        client.status = str(data.get("status", client.status))
        client.user = str(data.get("user", client.user))
        client.time = str(data.get("time", client.time))
        client.last_seen = datetime.now().strftime("%H:%M:%S")
        client.last_seen_ts = time.time()
        network = data.get("network", {})
        if isinstance(network, dict):
            client.ip = str(network.get("ip", client.ip))
            client.mac = str(network.get("mac", client.mac))
            client.iface = str(network.get("iface", client.iface))
            try:
                client.down_mbps = float(network.get("down_mbps", client.down_mbps))
                client.traffic_in_gb = float(network.get("traffic_in_gb", client.traffic_in_gb))
                client.latency_ms = float(network.get("latency_ms", client.latency_ms))
            except (ValueError, TypeError):
                pass
        info = data.get("info", {})
        if isinstance(info, dict):
            client.uptime = str(info.get("uptime", client.uptime))
            client.os = str(info.get("os", client.os))
            client.cpu_name = str(info.get("cpu_name", client.cpu_name))
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
                except (ValueError, TypeError):
                    pass
            try:
                client.ram_percent = float(metrics.get("ram_percent", client.ram_percent))
            except (ValueError, TypeError):
                pass
            ram = metrics.get("ram", {})
            if isinstance(ram, dict):
                try:
                    client.ram_used_gb = float(ram.get("used_gb", client.ram_used_gb))
                    client.ram_total_gb = float(ram.get("total_gb", client.ram_total_gb))
                except (ValueError, TypeError):
                    pass
            storage = metrics.get("storage", {})
            if isinstance(storage, dict):
                try:
                    client.storage_total_gb = float(storage.get("total_gb", client.storage_total_gb))
                    client.storage_used_gb = float(storage.get("used_gb", client.storage_used_gb))
                    client.storage_free_gb = float(storage.get("free_gb", client.storage_free_gb))
                    client.storage_percent = float(storage.get("percent", client.storage_percent))
                except (ValueError, TypeError):
                    pass
            top_processes = metrics.get("top_processes", client.top_processes)
            if isinstance(top_processes, list):
                client.top_processes = top_processes[:10]
            top_files = metrics.get("top_files", client.top_files)
            if isinstance(top_files, list):
                client.top_files = top_files[:10]
            gpu = metrics.get("gpu", client.gpu)
            if isinstance(gpu, list):
                client.gpu = gpu[:5]
        client.cpu_history.append(client.cpu_percent)
        client.ram_history.append(client.ram_percent)
        if len(client.cpu_history) > MAX_HISTORY_LENGTH:
            client.cpu_history = client.cpu_history[-MAX_HISTORY_LENGTH:]
        if len(client.ram_history) > MAX_HISTORY_LENGTH:
            client.ram_history = client.ram_history[-MAX_HISTORY_LENGTH:]
        stats["total_messages"] += 1
    except Exception as e:
        logger.error(f"Error updating client state for {client_id}: {e}")
        stats["failed_messages"] += 1


async def safe_broadcast_update():
    if not active_connections:
        return
    try:
        message_obj = {
            "type": "update",
            "clients": [c.to_dict() if isinstance(c, ClientState) else c for c in clients.values()],
            "timestamp": datetime.now().isoformat(),
            "stats": get_safe_stats(),
        }
        message = broadcast_circuit_breaker.call(json.dumps, message_obj)
        disconnected = set()
        for conn in active_connections:
            try:
                await asyncio.wait_for(conn.send_text(message), timeout=BROADCAST_TIMEOUT)
            except:
                disconnected.add(conn)
        if disconnected:
            active_connections.difference_update(disconnected)
    except Exception as e:
        logger.error(f"Broadcast failed: {e}")
        stats["broadcast_failures"] += 1


# ==================== MQTT SETUP ====================
mqtt_message_queue = queue.Queue()
mqtt_client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
mqtt_reconnect_delay = INITIAL_RECONNECT_DELAY


def on_mqtt_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"✅ Connected to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        client.subscribe(MQTT_COMMAND_RESULT_TOPIC)
        logger.info(f"📡 Subscribed to: {MQTT_TOPIC} dan {MQTT_COMMAND_RESULT_TOPIC}")
        global mqtt_reconnect_delay
        mqtt_reconnect_delay = INITIAL_RECONNECT_DELAY
    else:
        logger.error(f"❌ MQTT connection failed. Return code: {rc}")


def handle_command_result(msg):
    try:
        payload = json.loads(msg.payload.decode('utf-8'))
        request_id = payload.get('request_id')
        hostname = payload.get('hostname')
        command = payload.get('command')
        result = payload.get('result', {})
        command_logger.info(f"Command: {command} | Host: {hostname} | Status: {result.get('status')} | Output: {result.get('output', '')[:100]}...")
        command_results[request_id] = {
            'hostname': hostname, 'command': command, 'result': result,
            'timestamp': datetime.now().isoformat()
        }
        if request_id in pending_commands:
            pending_commands[request_id].set()
        logger.info(f"[✓] Command result diterima: {command} dari {hostname}")
    except Exception as e:
        logger.error(f"Error handling command result: {e}")


def on_mqtt_message(client, userdata, msg):
    try:
        try:
            payload_str = msg.payload.decode('utf-8')
        except UnicodeDecodeError:
            return
        
        try:
            payload = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in MQTT message from {msg.topic}: {e}")
            return
        
        if msg.topic.startswith("lab/command/result/"):
            handle_command_result(msg)
            return
        
        if not validate_payload_structure(payload):
            return
        
        client_id = payload.get("id", msg.topic.split('/')[-1])
        if not client_id or not isinstance(client_id, str):
            return
        
        logger.debug(f"📥 Received from {client_id}: status={payload.get('status')}")
        mqtt_message_queue.put((client_id, payload))
        
    except Exception as e:
        logger.error(f"Error processing MQTT message: {e}")


def on_mqtt_disconnect(client, userdata, rc):
    logger.warning(f"⚠️ Disconnected from MQTT Broker (rc={rc})")


def on_mqtt_connect_failure(client, userdata, rc):
    global mqtt_reconnect_delay
    mqtt_reconnect_delay = min(mqtt_reconnect_delay * 2, MAX_RECONNECT_DELAY)


mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
mqtt_client.on_disconnect = on_mqtt_disconnect
mqtt_client.on_connect_fail = on_mqtt_connect_failure


async def process_mqtt_messages():
    while True:
        try:
            batch_size = 0
            while not mqtt_message_queue.empty() and batch_size < 100:
                try:
                    client_id, payload = mqtt_message_queue.get_nowait()
                    safe_update_client_state(client_id, payload)
                    batch_size += 1
                except queue.Empty:
                    break
            if batch_size > 0:
                await safe_broadcast_update()
        except Exception as e:
            logger.error(f"Error in process_mqtt_messages: {e}")
        await asyncio.sleep(0.1)


# ==================== DEMO MODE ====================
def generate_demo_data(pc_info):
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
        "top_processes": [{"name": random.choice(PROCESS_NAMES), "cpu": round(random.uniform(1,30), 1), "mem": round(random.uniform(0.5,4), 2)} for _ in range(5)],
        "top_files": [{"name": random.choice(FILE_NAMES), "path": f"C:/Users/{pc_info['user']}/Documents", "size_mb": round(random.uniform(100,2000), 1)} for _ in range(5)],
        "cpu_history": [], "ram_history": []
    }


async def update_demo_data():
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
        logger.error(f"Error in update_demo_data: {e}")


async def demo_loop():
    while True:
        try:
            await update_demo_data()
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error in demo_loop: {e}")
            await asyncio.sleep(5)


# ==================== FASTAPI EVENTS ====================
async def check_offline_clients():
    while True:
        try:
            now = time.time()
            changed = False
            for client_id, client in clients.items():
                if client.status == "online":
                    elapsed = now - client.last_seen_ts
                    if elapsed > OFFLINE_TIMEOUT:
                        client.status = "offline"
                        logger.warning(f"[TIMEOUT] {client_id} marked offline")
                        changed = True
            if changed:
                await safe_broadcast_update()
        except Exception as e:
            logger.error(f"Error in check_offline_clients: {e}")
        await asyncio.sleep(5)


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Starting Lab Monitoring System v2.1.0 (Secure Edition)")
    logger.info(f"Configuration: USE_MQTT={USE_MQTT}, SERVER_PORT={SERVER_PORT}")
    
    if ADMIN_PASSWORD == "admin123":
        logger.warning("⚠️  PASSWORD DEFAULT! Ubah password ADMIN_PASSWORD di main.py atau set environment variable LAB_PASSWORD!")
    
    if USE_MQTT:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_start()
            logger.info("🚀 MQTT client started")
            asyncio.create_task(process_mqtt_messages())
        except Exception as e:
            logger.error(f"Failed to connect MQTT: {e}")
            logger.warning("⚠️ Running in offline mode")
    else:
        logger.info("🎭 Running in DEMO MODE")
        asyncio.create_task(demo_loop())

    asyncio.create_task(check_offline_clients())
    asyncio.create_task(log_stats())
    asyncio.create_task(session_cleanup_task())


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
    while True:
        try:
            await asyncio.sleep(60)
            uptime = datetime.now() - stats["start_time"]
            logger.info(f"📊 Stats - Uptime: {uptime}, Messages: {stats['total_messages']}, Failed: {stats['failed_messages']}, Clients: {len(clients)}, WS: {len(active_connections)}, Sessions: {len(sessions)}")
        except Exception as e:
            logger.error(f"Error logging stats: {e}")


async def session_cleanup_task():
    while True:
        try:
            cleanup_sessions()
        except Exception as e:
            logger.error(f"Error cleaning sessions: {e}")
        await asyncio.sleep(300)  # Bersihkan setiap 5 menit


# ==================== API ENDPOINTS ====================
@app.get("/")
async def get_index():
    return HTMLResponse(content=open("static/index.html", "r", encoding="utf-8").read())


@app.get("/api/clients")
async def get_clients(request: Request, session=Depends(check_auth)):
    return {
        "clients": [c.to_dict() if isinstance(c, ClientState) else c for c in clients.values()],
        "count": len(clients),
        "stats": get_safe_stats()
    }


@app.get("/api/stats")
async def get_stats(request: Request, session=Depends(check_auth)):
    uptime = datetime.now() - stats["start_time"]
    return {
        "uptime": str(uptime),
        "total_messages": stats["total_messages"],
        "failed_messages": stats["failed_messages"],
        "broadcast_failures": stats["broadcast_failures"],
        "mqtt_reconnects": stats["mqtt_reconnects"],
        "active_clients": len(clients),
        "websocket_connections": len(active_connections),
        "circuit_breaker_state": broadcast_circuit_breaker.state,
        "active_sessions": len(sessions)
    }


@app.post("/api/command")
async def execute_remote_command(request: Request, session=Depends(check_auth)):
    client_ip = request.client.host if request.client else "unknown"
    
    # Rate limit untuk command
    if not command_rate_limiter.is_allowed(f"cmd:{client_ip}"):
        logger.warning(f"[SECURITY] Command rate limit exceeded from {client_ip}")
        return JSONResponse(status_code=429, content={"error": "Terlalu banyak command! Tunggu beberapa saat."})
    
    try:
        data = await request.json()
        hostname = data.get('hostname')
        command = data.get('command')
        process_name = data.get('process_name', '').strip()
        admin_password = data.get('admin_password', '')  # Password untuk command berbahaya

        if not hostname or not command:
            return JSONResponse(status_code=400, content={"error": "hostname dan command harus diisi"})

        if command not in COMMAND_WHITELIST:
            logger.warning(f"[SECURITY] Unauthorized command attempt: {command} from {client_ip}")
            audit_logger.info(f"UNAUTHORIZED_CMD | IP: {client_ip} | Command: {command}")
            return JSONResponse(status_code=403, content={"error": f"Command '{command}' tidak diizinkan"})
        
        # Command berbahaya butuh password lagi!
        if command in DANGEROUS_COMMANDS:
            if not admin_password or not verify_password(admin_password):
                logger.warning(f"[SECURITY] Dangerous command without password: {command} from {client_ip}")
                audit_logger.info(f"DANGEROUS_CMD_NO_PASS | IP: {client_ip} | Command: {command}")
                return JSONResponse(status_code=403, content={
                    "error": "Command ini memerlukan verifikasi password admin!",
                    "need_password": True,
                    "message": "Masukkan password admin untuk melanjutkan"
                })

        if command in COMMAND_PARAMS:
            required_params = COMMAND_PARAMS[command]
            for param in required_params:
                if param == 'process_name' and not process_name:
                    return JSONResponse(status_code=400, content={"error": f"Parameter 'process_name' diperlukan untuk command '{command}'"})

        if hostname not in clients or clients[hostname].status != "online":
            return JSONResponse(status_code=404, content={"error": f"PC '{hostname}' tidak online"})

        request_id = f"{hostname}_{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

        params = {}
        if command in COMMAND_PARAMS:
            for param in COMMAND_PARAMS[command]:
                if param == 'process_name':
                    params['process_name'] = process_name

        payload = {"command": command, "request_id": request_id, "timestamp": datetime.now().isoformat(), "params": params}
        topic = f"lab/command/{hostname}"
        mqtt_client.publish(topic, json.dumps(payload))
        
        logger.info(f"[AUDIT] Command: {command} ke {hostname} dari {client_ip}")
        audit_logger.info(f"COMMAND | IP: {client_ip} | Target: {hostname} | Command: {command} | ID: {request_id}")

        pending_commands[request_id] = asyncio.Event()

        return JSONResponse({
            "status": "pending", "request_id": request_id,
            "message": f"Command '{command}' dikirim ke {hostname}",
            "command": command, "hostname": hostname, "params": params
        })

    except Exception as e:
        logger.error(f"Error executing remote command: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/command/result/{request_id}")
async def get_command_result(request_id: str, request: Request, session=Depends(check_auth)):
    if request_id in command_results:
        result = command_results[request_id]
        if request_id in pending_commands:
            del pending_commands[request_id]
        return JSONResponse({"status": "completed", "result": result})
    elif request_id in pending_commands:
        return JSONResponse({"status": "pending", "message": "Menunggu hasil dari agent..."})
    else:
        return JSONResponse(status_code=404, content={"status": "notfound", "error": "Request ID tidak ditemukan"})


@app.get("/api/commands/whitelist")
async def get_command_whitelist(request: Request, session=Depends(check_auth)):
    return JSONResponse({"commands": COMMAND_WHITELIST, "dangerous": DANGEROUS_COMMANDS})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    logger.info(f"🔌 WebSocket connected. Total: {len(active_connections)}")

    try:
        initial = json.dumps({
            "type": "initial",
            "clients": [c.to_dict() if isinstance(c, ClientState) else c for c in clients.values()],
            "timestamp": datetime.now().isoformat(),
            "stats": get_safe_stats()
        })
        await websocket.send_text(initial)

        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data:
                    await websocket.send_text(json.dumps({"type": "ack", "timestamp": datetime.now().isoformat()}))
            except asyncio.TimeoutError:
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
        logger.error(f"WebSocket error: {e}")
    finally:
        active_connections.discard(websocket)
        logger.info(f"🔌 WebSocket connection removed. Remaining: {len(active_connections)}")


@app.get("/health")
async def health_check():
    uptime = datetime.now() - stats["start_time"]
    return {
        "status": "healthy",
        "mode": "demo" if not USE_MQTT else "mqtt",
        "mqtt_connected": mqtt_client.is_connected() if USE_MQTT else False,
        "active_clients": len(clients),
        "websocket_connections": len(active_connections),
        "active_sessions": len(sessions),
        "uptime": str(uptime),
        "stats": get_safe_stats(),
        "circuit_breaker_state": broadcast_circuit_breaker.state,
        "timestamp": datetime.now().isoformat()
    }


# ==================== MAIN ====================
if __name__ == "__main__":
    mode = "DEMO MODE" if not USE_MQTT else "MQTT MODE"
    print("=" * 60)
    print(f"  Lab Monitoring System v2.1.0 Secure - {mode}")
    print("=" * 60)
    if USE_MQTT:
        print(f"  MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print(f"  Topic: {MQTT_TOPIC}")
    else:
        print("  🎭 Demo Mode: Generating fake data for 8 PCs")
    print(f"  Dashboard: http://localhost:{SERVER_PORT}")
    print(f"  🔒 Login password: {ADMIN_PASSWORD}")
    print(f"  ⚠️  Ubah password di main.py atau set env LAB_PASSWORD!")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="info")