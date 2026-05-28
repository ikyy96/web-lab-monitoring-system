#!/usr/bin/env python3
"""
Skrip Diagnostik Koneksi MQTT
Menguji konektivitas ke broker MQTT dan memberikan informasi error terperinci
"""

import socket
import sys
import time
import paho.mqtt.client as mqtt
from typing import Tuple

# Konfigurasi
BROKER_URL = "192.168.2.2"
PORT = 1883

def test_dns_resolution(host: str) -> bool:
    """Test resolusi hostname/IP"""
    print(f"[1] Menguji resolusi DNS untuk {host}...")
    try:
        ip = socket.gethostbyname(host)
        print(f"    ✓ Berhasil di-resolve ke {ip}")
        return True
    except socket.gaierror as e:
        print(f"    ✗ Gagal: {e}")
        print(f"    → Periksa apakah {host} benar dan dapat dijangkau")
        return False

def test_port_connectivity(host: str, port: int, timeout: int = 5) -> bool:
    """Test koneksi TCP ke port"""
    print(f"[2] Menguji koneksi TCP ke {host}:{port}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        print(f"    ✓ Koneksi TCP berhasil")
        sock.close()
        return True
    except socket.timeout:
        print(f"    ✗ Koneksi timeout (tunggu {timeout}s)")
        print(f"    → Broker di {host}:{port} tidak merespons")
        return False
    except ConnectionRefusedError:
        print(f"    ✗ Koneksi ditolak")
        print(f"    → Broker tidak mendengarkan port {port}")
        return False
    except OSError as e:
        print(f"    ✗ Kesalahan jaringan: {e}")
        print(f"    → Periksa konektivitas jaringan dan pengaturan firewall")
        return False
    finally:
        sock.close()

def test_mqtt_connection(host: str, port: int) -> bool:
    """Test koneksi MQTT"""
    print(f"[3] Menguji koneksi MQTT...")
    
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print(f"    ✓ Broker MQTT terhubung dengan sukses")
            client.disconnect()
        else:
            print(f"    ✗ Koneksi gagal dengan kode {rc}")
            if rc == 1:
                print("       Versi protokol salah")
            elif rc == 2:
                print("       ID klien tidak valid")
            elif rc == 3:
                print("       Broker tidak tersedia")
            elif rc == 4:
                print("       Username atau password salah")
            elif rc == 5:
                print("       Tidak diotorisasi")
    
    try:
        from paho.mqtt.enums import CallbackAPIVersion
        client = mqtt.Client(callback_api_version=CallbackAPIVersion.VERSION2)
    except (ImportError, AttributeError):
        client = mqtt.Client()
    
    client.on_connect = on_connect
    
    try:
        client.connect(host, port, keepalive=10)
        client.loop_start()
        time.sleep(2)
        client.loop_stop()
        return True
    except socket.gaierror as e:
        print(f"    ✗ Kesalahan DNS: {e}")
        return False
    except ConnectionRefusedError as e:
        print(f"    ✗ Koneksi ditolak: {e}")
        return False
    except socket.timeout as e:
        print(f"    ✗ Koneksi timeout: {e}")
        return False
    except Exception as e:
        print(f"    ✗ Error: {type(e).__name__}: {e}")
        return False

def main():
    print(f"\n{'='*60}")
    print(f"Diagnostik Broker MQTT")
    print(f"Target: {BROKER_URL}:{PORT}")
    print(f"{'='*60}\n")
    
    results = {
        "DNS": test_dns_resolution(BROKER_URL),
        "TCP": test_port_connectivity(BROKER_URL, PORT),
        "MQTT": False
    }
    
    print()
    
    if results["TCP"]:
        results["MQTT"] = test_mqtt_connection(BROKER_URL, PORT)
    
    print(f"\n{'='*60}")
    print("Ringkasan:")
    print(f"  Resolusi DNS: {'✓ LULUS' if results['DNS'] else '✗ GAGAL'}")
    print(f"  Koneksi TCP: {'✓ LULUS' if results['TCP'] else '✗ GAGAL'}")
    print(f"  Koneksi MQTT: {'✓ LULUS' if results['MQTT'] else '✗ GAGAL'}")
    print(f"{'='*60}\n")
    
    if all(results.values()):
        print("✓ Semua tes berhasil! Broker MQTT dapat dijangkau.")
        return 0
    else:
        print("✗ Beberapa tes gagal. Lihat di atas untuk detail.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
