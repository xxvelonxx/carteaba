"""
Bug Bounty Agent — Claude Sonnet 4.6 como cerebro principal
Metodología: Recon → Hunt → Validate → Report
Uso: python agent.py --target example.com --mode autopilot
"""
import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from anthropic import Anthropic

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
client = Anthropic()

SYSTEM_PROMPT = """Eres un experto en bug bounty y seguridad ofensiva. Tu objetivo es encontrar
vulnerabilidades reales en el target asignado siguiendo metodología OWASP Top 10 y técnicas
avanzadas de pentesting.

Tienes acceso a herramientas del sistema (nmap, curl, whatweb, gobuster, nuclei, etc.).
Cuando necesites ejecutar un comando, responde SOLO con:
EXECUTE: <comando>

Cuando hayas encontrado una vulnerabilidad, responde con:
FINDING: <severidad> | <tipo> | <descripción> | <PoC>

Cuando el recon esté completo:
RECON_DONE: <resumen de superficie de ataque>

Cuando la validación esté completa:
VALIDATED: <lista de findings confirmados>

Reglas:
- Solo atacar el target especificado y dentro del scope
- No hacer DoS ni destruir datos
- Documentar todo para el reporte final
- Priorizar severidad: Critical > High > Medium > Low"""


def run_command(cmd: str) -> str:
    """Ejecuta un comando del sistema y devuelve el output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=60
        )
        output = result.stdout + result.stderr
        return output[:3000] if len(output) > 3000 else output
    except subprocess.TimeoutExpired:
        return "TIMEOUT: comando tardó más de 60 segundos"
    except Exception as e:
        return f"ERROR: {e}"


def agent_loop(target: str, mode: str, scope: list = None):
    """Loop principal del agente."""
    findings = []
    conversation = []
    scope_str = ", ".join(scope) if scope else target

    initial_message = f"""Target: {target}
Scope autorizado: {scope_str}
Modo: {mode}
Fecha: {datetime.now().isoformat()}

{"Ejecuta recon completo: subdominios, puertos abiertos, tecnologías, endpoints." if mode == "recon" else ""}
{"Busca vulnerabilidades OWASP Top 10, CVEs conocidos, misconfigurations." if mode == "hunt" else ""}
{"Ejecuta recon completo + hunting + validación automática de todos los findings." if mode == "autopilot" else ""}
{"Valida los findings encontrados y confirma los PoCs reales." if mode == "validate" else ""}

Comienza ahora."""

    conversation.append({"role": "user", "content": initial_message})
    print(f"\n[+] Iniciando agente en modo {mode.upper()} para {target}")
    print(f"[+] Modelo: {MODEL}\n")

    max_turns = 30 if mode == "autopilot" else 15

    for turn in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=conversation,
        )

        assistant_text = response.content[0].text
        conversation.append({"role": "assistant", "content": assistant_text})

        print(f"\n--- Turno {turn + 1} ---")
        print(assistant_text)

        # Detectar comandos a ejecutar
        if "EXECUTE:" in assistant_text:
            for line in assistant_text.split("\n"):
                if line.startswith("EXECUTE:"):
                    cmd = line.replace("EXECUTE:", "").strip()
                    print(f"\n[>] Ejecutando: {cmd}")
                    output = run_command(cmd)
                    print(f"[<] Output:\n{output}")
                    conversation.append({
                        "role": "user",
                        "content": f"Resultado del comando `{cmd}`:\n```\n{output}\n```\nContinúa el análisis."
                    })
                    break

        # Detectar findings
        elif "FINDING:" in assistant_text:
            for line in assistant_text.split("\n"):
                if line.startswith("FINDING:"):
                    findings.append(line.replace("FINDING:", "").strip())
                    print(f"\n[!] FINDING: {line}")

            conversation.append({
                "role": "user",
                "content": "Finding registrado. Continúa buscando más vulnerabilidades."
            })

        # Detectar fin de fase
        elif any(tag in assistant_text for tag in ["RECON_DONE:", "VALIDATED:"]):
            if mode in ["recon", "validate"]:
                break
            # En autopilot, pasar a la siguiente fase
            conversation.append({
                "role": "user",
                "content": "Fase completada. Continúa con la siguiente fase del autopilot."
            })

        # Si no hay acción clara, pedir que continúe
        else:
            if response.stop_reason == "end_turn":
                if turn < max_turns - 1:
                    conversation.append({
                        "role": "user",
                        "content": "Continúa. ¿Qué más puedes analizar?"
                    })
                else:
                    break

    return findings, conversation


def generate_report(target: str, findings: list, conversation: list) -> str:
    """Genera reporte final en formato HackerOne/Bugcrowd."""
    findings_text = "\n".join(f"- {f}" for f in findings) if findings else "No se encontraron vulnerabilidades confirmadas."

    report_prompt = f"""Basándote en toda la conversación de análisis, genera un reporte profesional de bug bounty
con el siguiente formato:

# Bug Bounty Report — {target}
**Fecha:** {datetime.now().strftime('%Y-%m-%d')}
**Investigador:** [Tu nombre]
**Severidad total:** [Critical/High/Medium/Low]

## Resumen ejecutivo
[2-3 párrafos describiendo los hallazgos más importantes]

## Vulnerabilidades encontradas
[Para cada una:]
### [Nombre de la vulnerabilidad]
- **Severidad:** Critical/High/Medium/Low
- **CVSS Score:** X.X
- **CWE:** CWE-XXX
- **Descripción:** [Qué es y por qué importa]
- **Pasos para reproducir:**
  1. [Paso a paso]
- **Impacto:** [Qué puede hacer un atacante]
- **Recomendación:** [Cómo arreglarlo]
- **PoC:** [Código o comando que demuestra el bug]

## Superficie de ataque analizada
[Subdominios, endpoints, tecnologías encontradas]

## Conclusión
[Resumen de riesgos y próximos pasos]

Findings registrados durante el análisis:
{findings_text}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=8096,
        messages=[
            {"role": "user", "content": report_prompt}
        ] + conversation[-10:],  # últimos 10 turnos como contexto
    )

    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Bug Bounty Agent con Claude")
    parser.add_argument("--target", required=True, help="Dominio del target (ej: example.com)")
    parser.add_argument("--scope", nargs="*", help="Dominios en scope (default: target)")
    parser.add_argument(
        "--mode",
        choices=["recon", "hunt", "validate", "autopilot", "report"],
        default="autopilot",
        help="Modo de operación"
    )
    parser.add_argument("--output", default="report.md", help="Archivo de reporte de salida")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: Necesitas ANTHROPIC_API_KEY en el entorno")
        print("  export ANTHROPIC_API_KEY=tu-key-aqui")
        sys.exit(1)

    findings, conversation = agent_loop(
        target=args.target,
        mode=args.mode,
        scope=args.scope,
    )

    # Guardar conversación completa
    conv_file = f"session_{args.target}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(conv_file, "w") as f:
        json.dump({"target": args.target, "findings": findings, "conversation": conversation}, f, indent=2)
    print(f"\n[+] Sesión guardada en {conv_file}")

    # Generar reporte si hay findings o si el modo lo pide
    if findings or args.mode in ["autopilot", "report"]:
        print("\n[+] Generando reporte...")
        report = generate_report(args.target, findings, conversation)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"[+] Reporte guardado en {args.output}")
        print(f"\n[+] Total findings: {len(findings)}")
        for f in findings:
            print(f"    - {f}")


if __name__ == "__main__":
    main()
