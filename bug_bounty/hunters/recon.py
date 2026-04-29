"""Recon agent — subdomain enum, live hosts, endpoint discovery, tech fingerprint."""
import os, sys, json, subprocess, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from anthropic import Anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
client = Anthropic()

SYSTEM = """Eres un experto en recon ofensivo para bug bounty.
Tu objetivo: mapear la superficie de ataque más completa posible del target.

Comandos disponibles en el sistema:
- subfinder -d DOMAIN -silent -all → subdominios
- httpx -l FILE -status-code -title -tech-detect -silent → hosts vivos
- nmap -sV -p 80,443,8080,8443,3000,4000,5000,9000 HOST → puertos/servicios
- gau DOMAIN → URLs históricas de wayback/alien vault
- nuclei -u URL -t exposures/ -t misconfigurations/ -silent → misconfigs
- curl -sI URL → headers HTTP

Responde con EXECUTE: <comando> para correr herramientas.
Responde con FINDING: <tipo> | <asset> | <detalle> para guardar hallazgos.
Responde con RECON_DONE: <resumen> cuando hayas mapeado todo."""


def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=90)
        out = (r.stdout + r.stderr).strip()
        return out[:4000] if len(out) > 4000 else out or "(sin output)"
    except subprocess.TimeoutExpired:
        return "TIMEOUT (90s)"
    except Exception as e:
        return f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", default="recon_output.json")
    args = parser.parse_args()

    findings = []
    conv = [{"role": "user", "content": f"Target: {args.target}\nEjecuta recon completo. Empieza con subfinder para subdominios."}]

    print(f"[RECON] Iniciando en {args.target}")

    for turn in range(20):
        resp = client.messages.create(model=MODEL, max_tokens=2048, system=SYSTEM, messages=conv)
        text = resp.content[0].text
        conv.append({"role": "assistant", "content": text})

        if "EXECUTE:" in text:
            for line in text.splitlines():
                if line.startswith("EXECUTE:"):
                    cmd = line.replace("EXECUTE:", "").strip()
                    print(f"[RECON] > {cmd}")
                    out = run(cmd)
                    print(f"[RECON] < {out[:200]}...")
                    conv.append({"role": "user", "content": f"Output:\n```\n{out}\n```\nContinúa el recon."})
                    break
        elif "FINDING:" in text:
            for line in text.splitlines():
                if line.startswith("FINDING:"):
                    findings.append(line.replace("FINDING:", "").strip())
                    print(f"[RECON] FINDING: {findings[-1]}")
            conv.append({"role": "user", "content": "Finding guardado. Continúa mapeando."})
        elif "RECON_DONE:" in text:
            print(f"[RECON] Completado. {len(findings)} findings.")
            break
        else:
            conv.append({"role": "user", "content": "Continúa el recon."})

    result = {"target": args.target, "findings": findings, "conversation": conv}
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[RECON] Guardado en {args.output}")
    return result


if __name__ == "__main__":
    main()
