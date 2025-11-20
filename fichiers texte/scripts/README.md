# Live Trading Scripts

This directory contains scripts for running FinBot live trading operations.

## Scripts

### `run_live_trading.py`

Main CLI tool for executing the live trading pipeline.

**Features:**
- YAML-based configuration
- Scheduled execution (cron-compatible)
- Console and file logging
- Signal handling (graceful shutdown)
- Dry-run mode for testing
- Force execution override

**Usage:**

```bash
# Basic execution with config
python scripts/run_live_trading.py --config config/live_trading.yaml

# Dry run (test without executing orders)
python scripts/run_live_trading.py --config config/live_trading.yaml --dry-run

# Force execution (ignore schedule and market hours)
python scripts/run_live_trading.py --config config/live_trading.yaml --force

# Verbose logging
python scripts/run_live_trading.py --config config/live_trading.yaml --verbose

# Custom log file
python scripts/run_live_trading.py --config config/live_trading.yaml --log-file logs/custom.log
```

## Setup

### 1. Configure API Credentials

Set Alpaca API credentials as environment variables:

```bash
export ALPACA_API_KEY="your_api_key_here"
export ALPACA_SECRET_KEY="your_secret_key_here"
```

Or add to `.env` file:

```
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
```

### 2. Create Configuration

Copy and modify a configuration template:

```bash
cp config/live_trading_conservative.yaml config/my_strategy.yaml
```

Edit `config/my_strategy.yaml`:
- Set tickers (your trading universe)
- Configure risk limits
- Set execution schedule
- Choose strategy type

### 3. Test with Dry Run

Always test first with dry-run mode:

```bash
python scripts/run_live_trading.py \
    --config config/my_strategy.yaml \
    --dry-run \
    --verbose
```

### 4. Run Manual Execution

Test with a forced manual execution:

```bash
python scripts/run_live_trading.py \
    --config config/my_strategy.yaml \
    --force
```

Check logs for:
- ✓ Broker connection successful
- ✓ Pipeline initialized
- ✓ Orders generated and executed
- ⚠️ Any risk guard rejections
- ✗ Any errors

### 5. Set Up Automated Execution

#### Option A: Cron Job (Linux/Mac)

Edit crontab:
```bash
crontab -e
```

Add entry (example: daily at 9:35 AM ET):
```cron
# FinBot Live Trading - Daily execution at 9:35 AM ET
35 9 * * 1-5 cd /path/to/finbot && python scripts/run_live_trading.py --config config/my_strategy.yaml >> logs/cron.log 2>&1
```

Cron schedule syntax:
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
│ │ │ │ │
* * * * *
```

Examples:
```cron
# Daily at 9:35 AM (weekdays only)
35 9 * * 1-5 cd /path/to/finbot && python scripts/run_live_trading.py --config config/daily.yaml

# Weekly on Monday at 9:35 AM
35 9 * * 1 cd /path/to/finbot && python scripts/run_live_trading.py --config config/weekly.yaml

# Monthly on 1st at 9:35 AM
35 9 1 * * cd /path/to/finbot && python scripts/run_live_trading.py --config config/monthly.yaml
```

#### Option B: Systemd Timer (Linux)

Create service file `/etc/systemd/system/finbot-trading.service`:

```ini
[Unit]
Description=FinBot Live Trading
After=network.target

[Service]
Type=oneshot
User=your_username
WorkingDirectory=/path/to/finbot
Environment="ALPACA_API_KEY=your_key"
Environment="ALPACA_SECRET_KEY=your_secret"
ExecStart=/usr/bin/python3 scripts/run_live_trading.py --config config/my_strategy.yaml
StandardOutput=append:/path/to/finbot/logs/systemd.log
StandardError=append:/path/to/finbot/logs/systemd_error.log

[Install]
WantedBy=multi-user.target
```

Create timer file `/etc/systemd/system/finbot-trading.timer`:

```ini
[Unit]
Description=FinBot Live Trading Timer
Requires=finbot-trading.service

[Timer]
OnCalendar=Mon-Fri 09:35:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable finbot-trading.timer
sudo systemctl start finbot-trading.timer

# Check status
sudo systemctl status finbot-trading.timer
sudo systemctl list-timers
```

#### Option C: Task Scheduler (Windows)

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger (daily at 9:35 AM)
4. Set action: Run program
   - Program: `python`
   - Arguments: `scripts\run_live_trading.py --config config\my_strategy.yaml`
   - Start in: `C:\path\to\finbot`
5. Set conditions:
   - Run only if network is available
   - Wake computer to run task

## Monitoring

### View Live Logs

```bash
# Follow log file in real-time
tail -f logs/live_trading_$(date +%Y%m%d).log

# Search for errors
grep "ERROR" logs/live_trading_*.log

# Count successful executions
grep "Execution SUCCESSFUL" logs/live_trading_*.log | wc -l
```

### Check Pipeline Status

Use the Python REPL or create a status script:

```python
from financial_analyzer.trading import create_demo_pipeline

pipeline = create_demo_pipeline()
status = pipeline.get_status()

print(f"Portfolio Value: ${status['portfolio']['portfolio_value']:,.2f}")
print(f"Daily P&L: ${status['portfolio']['daily_pnl']:+,.2f}")
print(f"Positions: {status['portfolio']['num_positions']}")
print(f"Circuit Breaker: {'ACTIVE' if status['circuit_breaker_active'] else 'OK'}")
```

## Troubleshooting

### Issue: "Alpaca API credentials not found"

**Solution:** Set environment variables or create `.env` file:
```bash
export ALPACA_API_KEY="your_key"
export ALPACA_SECRET_KEY="your_secret"
```

### Issue: "Failed to connect to broker"

**Solutions:**
1. Check API credentials are correct
2. Verify network connection
3. Check Alpaca API status: https://status.alpaca.markets/
4. Ensure API keys have correct permissions

### Issue: "Execution SKIPPED: Market is closed"

**Solutions:**
1. Pipeline respects market hours by default
2. Use `--force` flag to test during off-hours
3. Check schedule configuration matches market hours
4. Verify timezone (Alpaca uses US/Eastern)

### Issue: "Orders rejected by RiskGuard"

**Solutions:**
1. Review risk configuration in YAML
2. Check if circuit breaker is active
3. Verify portfolio hasn't exceeded limits
4. Review logs for specific rejection reasons
5. Adjust risk limits if too conservative

### Issue: Cron job not running

**Solutions:**
1. Check cron service is running: `systemctl status cron`
2. Verify cron syntax: https://crontab.guru/
3. Check cron logs: `grep CRON /var/log/syslog`
4. Ensure script has execute permissions: `chmod +x scripts/run_live_trading.py`
5. Use absolute paths in crontab
6. Redirect output to log file to capture errors

## Safety Recommendations

### Paper Trading Period

**ALWAYS start with paper trading for at least 30 days:**

1. Set `paper: true` in config
2. Monitor daily for 2-4 weeks
3. Verify:
   - Orders execute correctly
   - Risk guards work as expected
   - No unexpected errors
   - Performance meets expectations

### Progressive Rollout

When moving to live trading:

1. **Week 1:** Small capital ($1,000 - $5,000)
2. **Week 2-4:** Monitor performance, adjust if needed
3. **Month 2:** Increase capital gradually
4. **Month 3+:** Full capital allocation

### Risk Management Checklist

Before going live:
- ✓ Paper trading validated (30+ days)
- ✓ Risk limits configured conservatively
- ✓ Circuit breaker enabled
- ✓ Position size limits set
- ✓ Daily loss limits set
- ✓ Maximum positions capped
- ✓ Leverage controlled
- ✓ Monitoring/alerts configured
- ✓ Backup plan documented

### Emergency Procedures

**If something goes wrong:**

1. **Stop automated execution:**
   ```bash
   # Disable cron job
   crontab -e  # Comment out the line
   
   # Or stop systemd timer
   sudo systemctl stop finbot-trading.timer
   ```

2. **Close all positions manually:**
   - Log into Alpaca dashboard
   - Review open positions
   - Close positions as needed

3. **Review logs:**
   ```bash
   grep "ERROR\|WARNING" logs/live_trading_*.log
   ```

4. **Contact support if needed:**
   - Alpaca Support: support@alpaca.markets
   - Check status: https://status.alpaca.markets/

## Next Steps

1. **Complete Phase 6.3 Testing:**
   - Run comprehensive test suite
   - Validate E2E with Alpaca Paper
   - Test all risk scenarios

2. **Integrate ML Models (Phase 5):**
   - Replace placeholder signal generation
   - Add trained LSTM models
   - Integrate FinBERT sentiment

3. **Add Portfolio Optimization (Phase 4):**
   - Replace proportional weights
   - Integrate Riskfolio-Lib
   - Add constraints (sector limits, etc.)

4. **Production Monitoring (Phase 7):**
   - Add dashboard (Streamlit/Grafana)
   - Set up email/Slack notifications
   - Create performance reports
   - Add automated alerts

## Resources

- **Alpaca API Docs:** https://alpaca.markets/docs/
- **Paper Trading:** https://alpaca.markets/docs/trading/paper-trading/
- **Market Hours:** https://www.nasdaq.com/market-activity/trading-hours
- **Cron Syntax:** https://crontab.guru/
- **FinBot Docs:** `/workspaces/finbot/docs/`
