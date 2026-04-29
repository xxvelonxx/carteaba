#!/bin/bash
# Modo overnight — lanzas esto antes de dormir, te levantas con el reporte
# Uso: ./overnight.sh target.com [--scope sub1.target.com sub2.target.com]
# No hace preguntas. No para. Corre hasta agotar el scope.

set -e

TARGET=${1:?"Uso: ./overnight.sh target.com"}
shift
SCOPE_ARGS="$@"

export PATH="$PATH:$HOME/go/bin"

SESSION_DIR="sessions/${TARGET}_$(date +%Y%m%d_%H%M)"
LOG_FILE="${SESSION_DIR}_overnight.log"

mkdir -p "$(dirname $SESSION_DIR)"

echo "============================================"
echo "  BUG BOUNTY SWARM — OVERNIGHT MODE"
echo "  Target: $TARGET"
echo "  Inicio: $(date)"
echo "  Log: $LOG_FILE"
echo "  Ya te puedes ir a dormir."
echo "============================================"

# Correr swarm con modo overnight
python3 "$(dirname "$0")/swarm.py" \
    --target "$TARGET" \
    --overnight \
    ${SCOPE_ARGS:+--scope $SCOPE_ARGS} \
    2>&1 | tee "$LOG_FILE"

echo ""
echo "============================================"
echo "  OVERNIGHT COMPLETADO: $(date)"
echo "  Ver reporte en: sessions/$TARGET*/"
echo "============================================"
