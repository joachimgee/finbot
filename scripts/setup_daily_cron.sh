#!/bin/bash
# Daily Portfolio Management - Cron Setup Script

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🤖 Configuration du Portfolio Management Quotidien"
echo "=================================================="
echo ""

# Créer le script d'exécution quotidienne
cat > "$PROJECT_ROOT/scripts/daily_cron_job.sh" << 'EOF'
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
EOF

chmod +x "$PROJECT_ROOT/scripts/daily_cron_job.sh"

echo "✅ Script quotidien créé: scripts/daily_cron_job.sh"
echo ""

# Afficher les options de cron
echo "📅 Options de programmation:"
echo ""
echo "OPTION 1: GitHub Actions (RECOMMANDÉ)"
echo "-------------------------------------"
echo "✅ Déjà configuré dans:"
echo "   .github/workflows/daily_professional_analysis_global_12k.yml"
echo ""
echo "✅ Horaire: Chaque jour à 09:30 ET (14:30 UTC)"
echo "✅ Jours: Lundi-Vendredi"
echo "✅ Automatique: Oui (si secrets configurés)"
echo ""
echo "📝 Action requise:"
echo "   1. Configurez les secrets GitHub:"
echo "      https://github.com/joachimgee/finbot/settings/secrets/actions"
echo "   2. Les 6 secrets requis sont dans: GITHUB_SECRETS_SETUP.md"
echo ""

echo "OPTION 2: Cron local (pour testing/backup)"
echo "-------------------------------------------"
echo "Pour ajouter au crontab:"
echo ""
echo "# Ouvrir crontab"
echo "crontab -e"
echo ""
echo "# Ajouter cette ligne (09:30 ET = 14:30 UTC)"
echo "30 14 * * 1-5 $PROJECT_ROOT/scripts/daily_cron_job.sh"
echo ""
echo "# Ou pour 09:00 ET (14:00 UTC)"
echo "0 14 * * 1-5 $PROJECT_ROOT/scripts/daily_cron_job.sh"
echo ""

echo "OPTION 3: Systemd timer (Linux production)"
echo "--------------------------------------------"
cat > "$PROJECT_ROOT/finbot-daily.service" << EOF
[Unit]
Description=FinBot Daily Portfolio Management
After=network.target

[Service]
Type=oneshot
User=$(whoami)
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PROJECT_ROOT/scripts/daily_cron_job.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

cat > "$PROJECT_ROOT/finbot-daily.timer" << EOF
[Unit]
Description=FinBot Daily Portfolio Management Timer
Requires=finbot-daily.service

[Timer]
OnCalendar=Mon-Fri 14:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "✅ Fichiers systemd créés:"
echo "   - finbot-daily.service"
echo "   - finbot-daily.timer"
echo ""
echo "Pour activer:"
echo "  sudo cp finbot-daily.* /etc/systemd/system/"
echo "  sudo systemctl daemon-reload"
echo "  sudo systemctl enable finbot-daily.timer"
echo "  sudo systemctl start finbot-daily.timer"
echo ""

echo "=================================================="
echo "✅ CONFIGURATION TERMINÉE"
echo "=================================================="
echo ""
echo "📊 Status actuel:"
echo "  • Workflow GitHub Actions: ✅ Configuré"
echo "  • Script quotidien local: ✅ Créé"
echo "  • Systemd timer: ✅ Fichiers prêts"
echo ""
echo "🚀 Recommandation:"
echo "  1. Utilisez GitHub Actions (Option 1) pour production"
echo "  2. Gardez cron local (Option 2) comme backup"
echo ""
echo "📝 Next steps:"
echo "  1. Configurez les secrets GitHub (voir GITHUB_SECRETS_SETUP.md)"
echo "  2. Testez manuellement le workflow GitHub"
echo "  3. Vérifiez l'exécution du $(date -d 'next day 09:30' '+%Y-%m-%d %H:%M')"
echo ""
