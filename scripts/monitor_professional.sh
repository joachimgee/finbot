#!/bin/bash
# Monitor Professional Analysis Progress

PID_FILE="/tmp/professional_analysis.pid"
LOG_FILE="/workspaces/finbot/professional_run.log"
OUTPUT_FILE="/workspaces/finbot/professional_analysis_3000.csv"

echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║              📊 PROFESSIONAL ANALYSIS MONITOR                                ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Check process
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if ps -p $PID > /dev/null 2>&1; then
        CPU=$(ps aux | grep "^[^ ]* *$PID " | awk '{print $3}')
        MEM=$(ps aux | grep "^[^ ]* *$PID " | awk '{print $4}')
        TIME=$(ps aux | grep "^[^ ]* *$PID " | awk '{print $10}')
        echo "✅ Processus ACTIF"
        echo "   PID      : $PID"
        echo "   CPU      : ${CPU}%"
        echo "   Mémoire  : ${MEM}%"
        echo "   Temps    : $TIME"
    else
        echo "❌ Processus TERMINÉ (PID: $PID)"
    fi
else
    echo "⚠️  Pas de PID file trouvé"
fi

echo ""
echo "─────────────────────────────────────────────────────────────────────────────"
echo ""

# Log size
if [ -f "$LOG_FILE" ]; then
    LOG_SIZE=$(wc -l < "$LOG_FILE")
    LOG_BYTES=$(du -h "$LOG_FILE" | cut -f1)
    echo "📋 Log : $LOG_SIZE lignes ($LOG_BYTES)"
    
    if [ $LOG_SIZE -gt 10 ]; then
        echo ""
        echo "📊 Dernières lignes du log :"
        echo "─────────────────────────────────────────────────────────────────────────────"
        tail -30 "$LOG_FILE"
    else
        echo "   (Buffer Python - log écrit en fin d'exécution)"
    fi
else
    echo "⚠️  Log pas encore créé"
fi

echo ""
echo "─────────────────────────────────────────────────────────────────────────────"
echo ""

# Output file
if [ -f "$OUTPUT_FILE" ]; then
    OUTPUT_LINES=$(wc -l < "$OUTPUT_FILE")
    OUTPUT_SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
    echo "✅ Rapport CSV : $OUTPUT_LINES lignes ($OUTPUT_SIZE)"
    
    if [ $OUTPUT_LINES -gt 1 ]; then
        echo ""
        echo "📈 Preview rapport :"
        echo "─────────────────────────────────────────────────────────────────────────────"
        head -3 "$OUTPUT_FILE"
        echo "..."
        tail -3 "$OUTPUT_FILE"
    fi
else
    echo "⏳ Rapport CSV pas encore généré"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "💡 Commandes utiles :"
echo "   tail -f $LOG_FILE           # Suivre log temps réel"
echo "   kill $PID                                # Arrêter processus"
echo "   watch -n 10 ./monitor_professional.sh    # Auto-refresh 10s"
echo ""
