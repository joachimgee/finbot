#!/bin/bash
# Daily Portfolio Management - Exécution automatique
# Lance chaque jour à 09:30 ET

cd "$(dirname "$0")/.."
source .env 2>/dev/null || true

LOG_FILE="logs/daily_$(date +%Y%m%d).log"

echo "$(date): Starting daily portfolio management" >> "$LOG_FILE"

python scripts/run_daily_portfolio_management.py \
  --limit 12000 \
  --max-positions 200 \
  --max-investment 1000 \
  --hold-threshold 0.0 \
  --execute \
  --mode paper \
  >> "$LOG_FILE" 2>&1

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date): Daily portfolio management completed successfully" >> "$LOG_FILE"
else
    echo "$(date): Daily portfolio management failed with code $EXIT_CODE" >> "$LOG_FILE"
fi

exit $EXIT_CODE
