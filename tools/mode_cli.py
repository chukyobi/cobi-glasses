"""
tools/mode_cli.py

Small CLI to toggle /set_mode/{mode} and display /get_mode

Usage:
    python mode_cli.py status
    python mode_cli.py set offline
    python mode_cli.py set online

Set SERVER to your transcriber svc base URL (where /set_mode is served).
"""

import sys
import requests

SERVER = "http://127.0.0.1:8002"  # change to your Pi transcriber endpoint

def status():
    try:
        r = requests.get(f"{SERVER}/get_mode", timeout=3)
        r.raise_for_status()
        print("Mode:", r.json().get("mode"))
    except Exception as e:
        print("Error getting mode:", e)

def set_mode(mode):
    mode = mode.lower()
    try:
        r = requests.post(f"{SERVER}/set_mode/{mode}", timeout=3)
        r.raise_for_status()
        print("Set mode ->", r.json().get("mode"))
    except Exception as e:
        print("Error setting mode:", e)

def usage():
    print("Usage:")
    print("  python mode_cli.py status")
    print("  python mode_cli.py set offline")
    print("  python mode_cli.py set online")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        usage()
    elif sys.argv[1] == "status":
        status()
    elif sys.argv[1] == "set" and len(sys.argv) >= 3:
        set_mode(sys.argv[2])
    else:
        usage()
