#!/bin/bash
# MONITORING DAEMON - Professional Analysis
# ==========================================
# Ce script affiche le statut du daemon d'analyse professionnelle

set -e

LOG_DIR="/workspaces/finbot/logs"
DAEMON_PATTERN="professional_analysis_daemon"

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║         📊 MONITORING DAEMON - Professional Analysis Status                 ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 1. Vérifier si le daemon tourne
echo "🔍 État du processus daemon..."
if ps aux | grep -v grep | grep "$DAEMON_PATTERN" > /dev/null; then
    PID=$(ps aux | grep -v grep | grep "$DAEMON_PATTERN" | awk '{print $2}')
    ELAPSED=$(ps -p $PID -o etime= | tr -d ' ')
    MEM=$(ps -p $PID -o %mem= | tr -d ' ')
    CPU=$(ps -p $PID -o %cpu= | tr -d ' ')
    
    echo "  ✅ Daemon ACTIF"
    echo "  • PID       : $PID"
    echo "  • Durée     : $ELAPSED"
    echo "  • Mémoire   : ${MEM}%"
    echo "  • CPU       : ${CPU}%"
else
    echo "  ❌ Daemon INACTIF"
    echo ""
    echo "Pour lancer le daemon:"
    echo "  python -u scripts/professional_analysis_daemon.py \\"
    echo "    --limit 10000 \\"
    echo "    --top 150 \\"
    echo "    --regions \"United States,United Kingdom,Germany,Japan,Canada\" \\"
    echo "    --schedule-time \"09:35\" \\"
    echo "    > logs/professional_daemon_\$(date +%Y%m%d_%H%M).log 2>&1 &"
    exit 1
fi

echo ""

# 2. Logs récents
echo "📄 Logs récents (dernières 10 lignes)..."
LATEST_LOG=$(ls -t $LOG_DIR/professional_daemon_*.log 2>/dev/null | head -1)
if [ -n "$LATEST_LOG" ]; then
    echo "  Fichier: $LATEST_LOG"
    tail -10 "$LATEST_LOG" | sed 's/^/  /'
else
    echo "  ⚠️  Aucun log trouvé"
fi

echo ""

# 3. Résultats d'analyse récents
echo "📈 Résultats récents..."
if ls /workspaces/finbot/professional_analysis_daemon_*.csv 1> /dev/null 2>&1; then
    LATEST_CSV=$(ls -t /workspaces/finbot/professional_analysis_daemon_*.csv 2>/dev/null | head -1)
    if [ -n "$LATEST_CSV" ]; then
        FILE_SIZE=$(du -h "$LATEST_CSV" | cut -f1)
        LINE_COUNT=$(wc -l < "$LATEST_CSV")
        MODIFIED=$(stat -c %y "$LATEST_CSV" | cut -d'.' -f1)
        
        echo "  ✅ Dernière analyse: $LATEST_CSV"
        echo "  • Taille    : $FILE_SIZE"
        echo "  • Lignes    : $LINE_COUNT symboles"
        echo "  • Modifié   : $MODIFIED"
        
        # Top 5 scores
        if [ $LINE_COUNT -gt 1 ]; then
            echo ""
            echo "  🎯 Top 5 symboles (score décroissant):"
            head -6 "$LATEST_CSV" | tail -5 | awk -F',' '{print "     " NR ". " $1 " (score: " $2 ")"}' || true
        fi
    fi
else
    echo "  ⚠️  Aucun résultat trouvé"
fi

echo ""

# 4. Compte Alpaca
echo "💰 Compte Alpaca Paper Trading..."
if command -v curl &> /dev/null; then
    source /workspaces/finbot/.env 2>/dev/null || true
    
    # Strip quotes from env vars
    APCA_API_BASE_URL=$(echo "$APCA_API_BASE_URL" | tr -d '"' | tr -d "'")
    APCA_API_KEY_ID=$(echo "$APCA_API_KEY_ID" | tr -d '"' | tr -d "'")
    APCA_API_SECRET_KEY=$(echo "$APCA_API_SECRET_KEY" | tr -d '"' | tr -d "'")
    
    ACCOUNT_INFO=$(curl -s \
        -H "APCA-API-KEY-ID: $APCA_API_KEY_ID" \
        -H "APCA-API-SECRET-KEY: $APCA_API_SECRET_KEY" \
        "$APCA_API_BASE_URL/v2/account" 2>/dev/null)
    
    if [ -n "$ACCOUNT_INFO" ]; then
        EQUITY=$(echo "$ACCOUNT_INFO" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{float(data.get('equity', 0)):,.2f}\")" 2>/dev/null || echo "N/A")
        CASH=$(echo "$ACCOUNT_INFO" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{float(data.get('cash', 0)):,.2f}\")" 2>/dev/null || echo "N/A")
        BUYING_POWER=$(echo "$ACCOUNT_INFO" | python3 -c "import sys, json; data=json.load(sys.stdin); print(f\"{float(data.get('buying_power', 0)):,.2f}\")" 2>/dev/null || echo "N/A")
        
        echo "  ✅ Compte connecté"
        echo "  • Equity       : \$$EQUITY"
        echo "  • Cash         : \$$CASH"
        echo "  • Buying Power : \$$BUYING_POWER"
    else
        echo "  ⚠️  Impossible de récupérer les infos compte"
    fi
else
    echo "  ⚠️  curl non disponible"
fi

echo ""

# 5. Prochaine exécution
echo "⏰ Prochaine exécution planifiée..."
if [ -n "$LATEST_LOG" ]; then
    NEXT_RUN=$(grep "Prochaine exécution:" "$LATEST_LOG" | tail -1 | sed 's/.*Prochaine exécution: //' | sed 's/ (.*//')
    if [ -n "$NEXT_RUN" ]; then
        echo "  📅 $NEXT_RUN"
    else
        echo "  ⚠️  Non trouvé dans les logs"
    fi
else
    echo "  ⚠️  Pas de logs disponibles"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════════════════════╗"
echo "║  Pour arrêter le daemon: kill $PID                                          ║"
echo "║  Pour voir les logs en temps réel: tail -f $LATEST_LOG                      ║"
echo "╚══════════════════════════════════════════════════════════════════════════════╝"
echo ""
