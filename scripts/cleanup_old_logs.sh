#!/bin/bash
# Script de nettoyage automatique des logs anciens (> 7 jours)
# Usage: ./scripts/cleanup_old_logs.sh

LOG_DIR="/workspaces/finbot/logs"
CSV_DIR="/workspaces/finbot"
RETENTION_DAYS=7

echo "🧹 Nettoyage logs et CSV > ${RETENTION_DAYS} jours..."
echo ""

# Nettoyage logs
if [ -d "$LOG_DIR" ]; then
    echo "📂 Recherche logs > ${RETENTION_DAYS}j dans $LOG_DIR"
    DELETED_LOGS=$(find "$LOG_DIR" -name "*.log" -type f -mtime +${RETENTION_DAYS} -print -delete | wc -l)
    echo "   ✅ Supprimé: $DELETED_LOGS fichiers log"
else
    echo "   ⚠️  Dossier logs non trouvé: $LOG_DIR"
fi

echo ""

# Nettoyage CSV résultats (sauf aggregated qui a retention 30j)
if [ -d "$CSV_DIR" ]; then
    echo "📂 Recherche CSV > ${RETENTION_DAYS}j dans $CSV_DIR"
    DELETED_CSV=$(find "$CSV_DIR" -maxdepth 1 -name "professional_analysis_*.csv" ! -name "*aggregated*" -type f -mtime +${RETENTION_DAYS} -print -delete | wc -l)
    echo "   ✅ Supprimé: $DELETED_CSV fichiers CSV"
else
    echo "   ⚠️  Dossier CSV non trouvé: $CSV_DIR"
fi

echo ""
echo "✅ Nettoyage terminé"
echo ""
echo "Statistiques actuelles:"
echo "  Logs restants: $(find "$LOG_DIR" -name "*.log" -type f 2>/dev/null | wc -l)"
echo "  CSV restants: $(find "$CSV_DIR" -maxdepth 1 -name "professional_analysis_*.csv" -type f 2>/dev/null | wc -l)"
