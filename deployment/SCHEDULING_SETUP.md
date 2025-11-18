# InsightWeaver Scheduling Setup

This guide explains how to set up automated daily intelligence reports.

## Configuration

Edit your `.env` file to configure scheduling:

```bash
# Scheduling
DAILY_REPORT_ENABLED=True      # Enable/disable daily reports
DAILY_REPORT_HOURS=24          # Look back window (hours)
AUTO_CLEANUP_ENABLED=True      # Enable/disable automatic data cleanup
```

## Option 1: systemd (Recommended for Linux)

### Installation

1. **Edit the service file** to match your system:
   ```bash
   cd deployment/systemd
   # Update the paths in insightweaver-daily.service:
   # - User=<your-username>
   # - WorkingDirectory=<full-path-to-project>
   # - Environment PATH
   # - ExecStart path
   ```

2. **Install the service and timer**:
   ```bash
   # Copy files to systemd user directory
   mkdir -p ~/.config/systemd/user
   cp deployment/systemd/insightweaver-daily.service ~/.config/systemd/user/
   cp deployment/systemd/insightweaver-daily.timer ~/.config/systemd/user/

   # Reload systemd configuration
   systemctl --user daemon-reload

   # Enable and start the timer
   systemctl --user enable insightweaver-daily.timer
   systemctl --user start insightweaver-daily.timer
   ```

3. **Verify it's running**:
   ```bash
   # Check timer status
   systemctl --user status insightweaver-daily.timer

   # List all timers
   systemctl --user list-timers
   ```

### Customizing Schedule

Edit `~/.config/systemd/user/insightweaver-daily.timer` and change the `OnCalendar` line:

```ini
# Daily at 8:00 AM (default)
OnCalendar=*-*-* 08:00:00

# Daily at 6:00 PM
OnCalendar=*-*-* 18:00:00

# Twice daily (8 AM and 8 PM)
OnCalendar=*-*-* 08:00:00
OnCalendar=*-*-* 20:00:00

# Every 12 hours
OnCalendar=*-*-* 00/12:00:00
```

After editing, reload:
```bash
systemctl --user daemon-reload
systemctl --user restart insightweaver-daily.timer
```

### Manual Execution

Test the service manually:
```bash
systemctl --user start insightweaver-daily.service
```

View logs:
```bash
# Real-time logs
journalctl --user -u insightweaver-daily.service -f

# Last 50 lines
journalctl --user -u insightweaver-daily.service -n 50
```

### Stopping/Disabling

```bash
# Stop the timer
systemctl --user stop insightweaver-daily.timer

# Disable auto-start
systemctl --user disable insightweaver-daily.timer
```

## Option 2: Cron (Alternative)

### Installation

1. **Open crontab editor**:
   ```bash
   crontab -e
   ```

2. **Add cron entry**:
   ```bash
   # Daily at 8:00 AM
   0 8 * * * cd /home/saydlette/workspace/InsightWeaver && /home/saydlette/workspace/InsightWeaver/venv/bin/python /home/saydlette/workspace/InsightWeaver/scripts/scheduled_report.py >> /home/saydlette/workspace/InsightWeaver/data/logs/cron.log 2>&1
   ```

### Cron Schedule Examples

```bash
# Daily at 6:00 PM
0 18 * * * <command>

# Twice daily (8 AM and 8 PM)
0 8,20 * * * <command>

# Every 12 hours
0 */12 * * * <command>

# Every Monday at 9 AM
0 9 * * 1 <command>
```

### Viewing Cron Logs

```bash
tail -f /home/saydlette/workspace/InsightWeaver/data/logs/cron.log
```

## Option 3: Manual Execution

You can always run reports manually:

```bash
# Using the scheduler script
python scripts/scheduled_report.py

# Using main.py
python main.py --report --hours 24 --email
```

## Logs

Scheduled reports create daily log files:
```
data/logs/scheduled_report_YYYYMMDD.log
```

View today's log:
```bash
tail -f data/logs/scheduled_report_$(date +%Y%m%d).log
```

## Troubleshooting

### Service won't start
- Check paths in service file match your system
- Verify virtual environment exists: `ls venv/bin/python`
- Check permissions: `ls -l scripts/scheduled_report.py`
- View errors: `journalctl --user -u insightweaver-daily.service -n 50`

### Reports not being emailed
- Verify email settings in `.env`
- Check SMTP credentials are correct
- Review log files for error messages
- Test email manually: `python main.py --report --hours 24 --email`

### Timer not triggering
- Verify timer is enabled: `systemctl --user is-enabled insightweaver-daily.timer`
- Check timer is active: `systemctl --user is-active insightweaver-daily.timer`
- View timer schedule: `systemctl --user list-timers insightweaver-daily.timer`

### Wrong timezone
Systemd uses system timezone. Check with:
```bash
timedatectl
```

Change timezone if needed:
```bash
sudo timedatectl set-timezone America/New_York
```

## Monitoring

### Check last run time
```bash
systemctl --user status insightweaver-daily.service
```

### View recent logs
```bash
journalctl --user -u insightweaver-daily.service --since today
```

### Check next scheduled run
```bash
systemctl --user list-timers insightweaver-daily.timer
```
