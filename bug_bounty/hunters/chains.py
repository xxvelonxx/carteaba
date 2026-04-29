"""Chain hunter — combina findings de otros módulos para escalar severidad."""
import os, sys, json, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from anthropic import Anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
client = Anthropic()

SYSTEM = """Eres un experto en exploit chaining para bug bounty de alto pago (10k-50k+).

Dado un conjunto de findings individuales, tu trabajo es:
1. Identificar qué bugs se pueden combinar
2. Construir la cadena de explotación paso a paso
3. Calcular el CVSS final de la cadena (siempre mayor que las partes individuales)
4. Escribir el PoC completo de la cadena

Cadenas clásicas de alto pago:
- IDOR → email change → ATO (Account Takeover) → Critical
- Open Redirect → OAuth code theft → ATO → Critical
- XSS stored → session hijack → ATO → High/Critical
- SSRF → cloud metadata → credentials → RCE → Critical
- IDOR → PII exposure → password hash → crack → ATO → Critical
- Race condition en payment → precio gratis + doble cobro evadido → Critical
- Business logic (skip verification) + IDOR → acceso a cuenta verificada → High
- JWT alg:none + IDOR → admin impersonation → Critical

Responde con:
CHAIN: <bug A> + <bug B> → <resultado> | CVSS: X.X | PoC: <pasos>
SINGLE_ESCALATION: <finding original> → <impacto real más alto> | Razón: <por qué>
ANALYSIS_DONE: <resumen de chains encontradas>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings-files", nargs="+", required=True, help="JSONs de otros módulos")
    parser.add_argument("--output", default="chains_output.json")
    args = parser.parse_args()

    all_findings = []
    for ffile in args.findings_files:
        if os.path.exists(ffile):
            with open(ffile) as f:
                data = json.load(f)
                all_findings.extend(data.get("findings", []))

    if not all_findings:
        print("[CHAIN] No hay findings para analizar")
        return

    findings_str = "\n".join(f"- {f}" for f in all_findings)
    conv = [{"role": "user", "content": f"""Analiza estos findings y construye exploit chains:

{findings_str}

Para cada chain posible, dame el PoC completo paso a paso y el CVSS de la cadena combinada.
Luego identifica si algún finding individual tiene impacto mayor al que parece a primera vista."""}]

    print(f"[CHAIN] Analizando {len(all_findings)} findings para chaining...")

    chains = []
    for turn in range(10):
        resp = client.messages.create(model=MODEL, max_tokens=4096, system=SYSTEM, messages=conv)
        text = resp.content[0].text
        conv.append({"role": "assistant", "content": text})

        for line in text.splitlines():
            if line.startswith("CHAIN:") or line.startswith("SINGLE_ESCALATION:"):
                chains.append(line.strip())
                print(f"[CHAIN] ++ {line.strip()[:120]}")

        if "ANALYSIS_DONE:" in text:
            break
        else:
            conv.append({"role": "user", "content": "Continúa buscando más chains."})

    result = {"findings_analyzed": len(all_findings), "chains": chains, "conversation": conv}
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[CHAIN] {len(chains)} chains encontradas → {args.output}")
    return result


if __name__ == "__main__":
    main()
