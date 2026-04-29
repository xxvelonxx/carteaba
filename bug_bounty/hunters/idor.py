"""IDOR + Race Condition hunter — acceso horizontal/vertical, race conditions, BOLA."""
import os, sys, json, subprocess, argparse, time, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from anthropic import Anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
client = Anthropic()

SYSTEM = """Eres un especialista en IDOR, BOLA, acceso horizontal/vertical y race conditions para bug bounty.

Técnicas que usas:
1. IDOR: reemplaza IDs (UUID, integer, slug) en URLs y parámetros con IDs de otro usuario
2. BOLA: testa cada endpoint de API con tokens de diferentes roles (user, admin, viewer)
3. Race conditions: envía 20+ requests simultáneos al mismo endpoint para detectar TOCTOU
4. Mass assignment: envía campos extra en POST/PUT (role, isAdmin, verified)
5. IDOR encadenado: IDOR en un endpoint que da acceso a otro

Para race conditions usa:
EXECUTE: python3 -c "
import threading, requests
url = 'TARGET_URL'
headers = {'Authorization': 'Bearer TOKEN'}
def req(): r = requests.post(url, headers=headers, json={...}); print(r.status_code, r.text[:50])
threads = [threading.Thread(target=req) for _ in range(25)]
[t.start() for t in threads]; [t.join() for t in threads]
"

Para IDOR usa:
EXECUTE: for id in 1 2 3 100 999 1000; do curl -s -o /dev/null -w \"ID $id: %{http_code}\\n\" -H 'Authorization: Bearer TOKEN' https://TARGET/api/users/$id/profile; done

Responde EXECUTE: <comando>, FINDING: <tipo> | <endpoint> | <descripción> | <PoC>
Responde DONE: <resumen> cuando termines."""


def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:4000] if len(out) > 4000 else out or "(sin output)"
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--recon-file", default=None, help="JSON de recon para contexto")
    parser.add_argument("--output", default="idor_output.json")
    args = parser.parse_args()

    recon_context = ""
    if args.recon_file and os.path.exists(args.recon_file):
        with open(args.recon_file) as f:
            recon = json.load(f)
            recon_context = f"\nRecon previo:\n{json.dumps(recon.get('findings', []), indent=2)}"

    findings = []
    conv = [{"role": "user", "content": f"Target: {args.target}{recon_context}\n\nBusca IDORs, BOLA y race conditions. Necesito credenciales de al menos 2 usuarios para testear IDOR (si no las tienes, crea un flujo de prueba hipotético y documenta cómo validarlo). Empieza analizando los endpoints más prometedores."}]

    print(f"[IDOR] Iniciando en {args.target}")

    for turn in range(25):
        resp = client.messages.create(model=MODEL, max_tokens=2048, system=SYSTEM, messages=conv)
        text = resp.content[0].text
        conv.append({"role": "assistant", "content": text})

        if "EXECUTE:" in text:
            for line in text.splitlines():
                if line.startswith("EXECUTE:"):
                    cmd = line.replace("EXECUTE:", "").strip()
                    print(f"[IDOR] > {cmd[:80]}...")
                    out = run(cmd)
                    print(f"[IDOR] < {out[:150]}...")
                    conv.append({"role": "user", "content": f"Output:\n```\n{out}\n```\nAnaliza y continúa."})
                    break
        elif "FINDING:" in text:
            for line in text.splitlines():
                if line.startswith("FINDING:"):
                    findings.append(line.replace("FINDING:", "").strip())
                    print(f"[IDOR] !! FINDING: {findings[-1][:100]}")
            conv.append({"role": "user", "content": "Finding guardado. Busca más."})
        elif "DONE:" in text:
            break
        else:
            conv.append({"role": "user", "content": "Continúa el hunting."})

    result = {"target": args.target, "module": "idor", "findings": findings, "conversation": conv}
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[IDOR] {len(findings)} findings → {args.output}")
    return result


if __name__ == "__main__":
    main()
