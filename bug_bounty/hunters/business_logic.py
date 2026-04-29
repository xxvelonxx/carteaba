"""Business Logic hunter — workflow flaws, price manipulation, auth bypass chains."""
import os, sys, json, subprocess, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from anthropic import Anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
client = Anthropic()

SYSTEM = """Eres un especialista en business logic flaws y auth bypass para bug bounty de alto pago.

Te enfocas en bugs que los scanners automáticos NUNCA encuentran:
1. Price manipulation: valores negativos, overflow, descuentos stacking, coupon reuse
2. Workflow bypass: saltar pasos de verificación (pago sin verificar email, upgrade sin cobrar)
3. Auth bypass: tokens expirados aceptados, JWT alg:none, password reset flaws
4. Privilege escalation: cambiar role en perfil, acceder a funciones de admin sin permiso
5. Account takeover chains: IDOR en email change → ATO, XSS → session hijack
6. Rate limiting bypass: IP rotation headers (X-Forwarded-For), account enumeration
7. 2FA bypass: código fijo "000000", skip del paso 2FA, fallback SMS

Técnicas de testing:
- Interceptar y modificar requests con curl
- Probar valores edge: -1, 0, 999999999, null, true/false, arrays en lugar de strings
- Repetir requests con tokens expirados
- Cambiar parámetros de orden/rol en el body

Responde EXECUTE: <curl completo> para testear.
Responde FINDING: Critical/High/Medium | <tipo> | <descripción> | <PoC exacto>
Responde DONE: <resumen> cuando termines."""


def run(cmd):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        out = (r.stdout + r.stderr).strip()
        return out[:3000] if len(out) > 3000 else out or "(sin output)"
    except Exception as e:
        return f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True)
    parser.add_argument("--recon-file", default=None)
    parser.add_argument("--output", default="logic_output.json")
    args = parser.parse_args()

    recon_context = ""
    if args.recon_file and os.path.exists(args.recon_file):
        with open(args.recon_file) as f:
            recon = json.load(f)
            recon_context = f"\nEndpoints descubiertos:\n{json.dumps(recon.get('findings', [])[:20], indent=2)}"

    findings = []
    conv = [{"role": "user", "content": f"""Target: {args.target}{recon_context}

Analiza la lógica de negocio de este target.
Primero visita la web y mapea los flujos principales (registro, login, perfil, pagos, features premium si los hay).
Luego testea cada flujo buscando fallas de lógica que paguen bien en HackerOne/Bugcrowd.
Prioriza bugs que lleven a ATO o acceso no autorizado a recursos de pago."""}]

    print(f"[LOGIC] Iniciando en {args.target}")

    for turn in range(25):
        resp = client.messages.create(model=MODEL, max_tokens=2048, system=SYSTEM, messages=conv)
        text = resp.content[0].text
        conv.append({"role": "assistant", "content": text})

        if "EXECUTE:" in text:
            for line in text.splitlines():
                if line.startswith("EXECUTE:"):
                    cmd = line.replace("EXECUTE:", "").strip()
                    print(f"[LOGIC] > {cmd[:80]}...")
                    out = run(cmd)
                    print(f"[LOGIC] < {out[:150]}...")
                    conv.append({"role": "user", "content": f"Output:\n```\n{out}\n```\nAnaliza y continúa."})
                    break
        elif "FINDING:" in text:
            for line in text.splitlines():
                if line.startswith("FINDING:"):
                    findings.append(line.replace("FINDING:", "").strip())
                    print(f"[LOGIC] !! {findings[-1][:120]}")
            conv.append({"role": "user", "content": "Finding guardado. Continúa buscando."})
        elif "DONE:" in text:
            break
        else:
            conv.append({"role": "user", "content": "Continúa."})

    result = {"target": args.target, "module": "business_logic", "findings": findings, "conversation": conv}
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[LOGIC] {len(findings)} findings → {args.output}")
    return result


if __name__ == "__main__":
    main()
