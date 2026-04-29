"""
Swarm orchestrator — 4 agentes paralelos atacando simultáneamente.
Uso:
  python swarm.py --target example.com
  python swarm.py --target example.com --overnight   # modo sin interrupciones
"""
import os, sys, json, argparse, threading, time
from datetime import datetime
from pathlib import Path
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).parent))

MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
client = Anthropic()


def run_module(module_path, args_list, output_file, results_dict, key):
    """Corre un módulo hunter en su propio hilo."""
    import subprocess
    cmd = [sys.executable, module_path] + args_list
    print(f"[SWARM] Lanzando {key}: {' '.join(cmd[-3:])}")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if os.path.exists(output_file):
            with open(output_file) as f:
                results_dict[key] = json.load(f)
        else:
            results_dict[key] = {"error": r.stderr[-500:] if r.stderr else "sin output"}
    except subprocess.TimeoutExpired:
        results_dict[key] = {"error": "TIMEOUT (1h)"}
    except Exception as e:
        results_dict[key] = {"error": str(e)}
    print(f"[SWARM] {key} terminado → {len(results_dict[key].get('findings', []))} findings")


def generate_final_report(target, all_findings, chains, overnight=False):
    """Genera el reporte final de toda la sesión del swarm."""
    findings_text = "\n".join(f"- {f}" for f in all_findings) if all_findings else "Ninguno confirmado."
    chains_text = "\n".join(f"- {c}" for c in chains) if chains else "Ninguna chain identificada."

    prompt = f"""Genera un reporte profesional completo para HackerOne/Bugcrowd/Immunefi.

Target: {target}
Fecha: {datetime.now().strftime('%Y-%m-%d')}
Modo: {'Overnight autonomous' if overnight else 'Standard swarm'}

Findings individuales:
{findings_text}

Exploit chains:
{chains_text}

Formato requerido:
# Bug Bounty Report — {target}

## Executive Summary
[Resumen de alto impacto, 2-3 párrafos]

## Vulnerabilities Found
[Para cada finding: severidad, descripción, pasos para reproducir, impacto, PoC, CVSS 3.1, remediación]

## Exploit Chains
[Para cada chain: componentes, PoC completo paso a paso, impacto combinado, CVSS]

## Attack Surface Mapped
[Subdominios, endpoints, tecnologías, vectores probados]

## Conclusion
[Próximos pasos recomendados]

Escribe en tono profesional pero humano. Los reportes que suenan a IA son rechazados."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=8096,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.content[0].text


def main():
    parser = argparse.ArgumentParser(description="Bug Bounty Swarm — 4 agentes paralelos")
    parser.add_argument("--target", required=True)
    parser.add_argument("--scope", nargs="*", help="Dominios adicionales en scope")
    parser.add_argument("--overnight", action="store_true", help="Modo sin interrupciones, máxima profundidad")
    parser.add_argument("--output-dir", default="sessions")
    args = parser.parse_args()

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ERROR: export ANTHROPIC_API_KEY=tu-key")
        sys.exit(1)

    session_id = datetime.now().strftime("%Y%m%d_%H%M")
    session_dir = Path(args.output_dir) / f"{args.target}_{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)

    hunters_dir = Path(__file__).parent / "hunters"

    print(f"\n{'='*60}")
    print(f"  BUG BOUNTY SWARM")
    print(f"  Target: {args.target}")
    print(f"  Modo: {'OVERNIGHT (sin interrupciones)' if args.overnight else 'Standard'}")
    print(f"  Session: {session_dir}")
    print(f"  Agentes: recon + IDOR + business_logic lanzados en paralelo")
    print(f"{'='*60}\n")

    if args.overnight:
        print("[SWARM] OVERNIGHT MODE: vete a dormir. No te voy a preguntar nada.")
        print("[SWARM] El swarm corre hasta agotar el scope o encontrar PoCs válidos.")
        print("[SWARM] Reporte final en:", session_dir / "FINAL_REPORT.md")
        print()

    results = {}
    threads = []

    # Fase 1: Recon + IDOR + Business Logic en paralelo
    phase1_modules = [
        (str(hunters_dir / "recon.py"), ["--target", args.target, "--output", str(session_dir / "recon.json")], str(session_dir / "recon.json"), "recon"),
        (str(hunters_dir / "idor.py"), ["--target", args.target, "--output", str(session_dir / "idor.json")], str(session_dir / "idor.json"), "idor"),
        (str(hunters_dir / "business_logic.py"), ["--target", args.target, "--output", str(session_dir / "logic.json")], str(session_dir / "logic.json"), "logic"),
    ]

    for module_path, module_args, output_file, key in phase1_modules:
        t = threading.Thread(target=run_module, args=(module_path, module_args, output_file, results, key), daemon=True)
        threads.append(t)
        t.start()
        time.sleep(2)  # Escalonado para no saturar la API

    print(f"[SWARM] 3 agentes corriendo en paralelo...")

    for t in threads:
        t.join()

    print("\n[SWARM] Fase 1 completa. Iniciando chaining...")

    # Fase 2: Chain hunter con los findings de fase 1
    all_findings = []
    for key in ["recon", "idor", "logic"]:
        if key in results:
            all_findings.extend(results[key].get("findings", []))

    chains = []
    if all_findings:
        chain_results = {}
        chain_files = [str(session_dir / f"{k}.json") for k in ["idor", "logic"] if (session_dir / f"{k}.json").exists()]
        if chain_files:
            run_module(
                str(hunters_dir / "chains.py"),
                ["--findings-files"] + chain_files + ["--output", str(session_dir / "chains.json")],
                str(session_dir / "chains.json"),
                chain_results,
                "chains"
            )
            chains = chain_results.get("chains", {}).get("chains", [])

    # Fase 3: Reporte final
    print("\n[SWARM] Generando reporte final...")
    report = generate_final_report(args.target, all_findings, chains, args.overnight)

    report_path = session_dir / "FINAL_REPORT.md"
    with open(report_path, "w") as f:
        f.write(report)

    # Resumen de sesión
    summary = {
        "target": args.target,
        "session": session_id,
        "total_findings": len(all_findings),
        "total_chains": len(chains),
        "findings": all_findings,
        "chains": chains,
        "report": str(report_path),
    }

    with open(session_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'='*60}")
    print(f"  SWARM COMPLETADO")
    print(f"  Findings: {len(all_findings)}")
    print(f"  Exploit chains: {len(chains)}")
    print(f"  Reporte: {report_path}")
    print(f"{'='*60}")

    if all_findings:
        print("\nFindings encontrados:")
        for f in all_findings[:10]:
            print(f"  - {f[:100]}")
        if len(all_findings) > 10:
            print(f"  ... y {len(all_findings) - 10} más")

    return summary


if __name__ == "__main__":
    main()
