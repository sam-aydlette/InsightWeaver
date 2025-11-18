#!/bin/bash
# Install InsightWeaver systemd scheduler
# This script installs the daily report timer for the current user

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
USER_SYSTEMD_DIR="$HOME/.config/systemd/user"

echo "========================================"
echo "InsightWeaver Scheduler Installation"
echo "========================================"
echo ""
echo "Project directory: $PROJECT_DIR"
echo "Installing for user: $USER"
echo ""

# Verify we're in the right directory
if [ ! -f "$PROJECT_DIR/scripts/scheduled_report.py" ]; then
    echo "Error: Cannot find scripts/scheduled_report.py"
    echo "Please run this script from the deployment directory"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo "Error: Virtual environment not found at $PROJECT_DIR/venv"
    echo "Please create it first: python -m venv venv"
    exit 1
fi

# Create systemd user directory if it doesn't exist
mkdir -p "$USER_SYSTEMD_DIR"

# Update service file with correct paths
echo "Creating service file..."
cat > "$USER_SYSTEMD_DIR/insightweaver-daily.service" <<EOF
[Unit]
Description=InsightWeaver Daily Intelligence Report
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python $PROJECT_DIR/scripts/scheduled_report.py

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=insightweaver-daily

# Security hardening
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

# Copy timer file
echo "Creating timer file..."
cp "$SCRIPT_DIR/systemd/insightweaver-daily.timer" "$USER_SYSTEMD_DIR/"

# Reload systemd
echo "Reloading systemd configuration..."
systemctl --user daemon-reload

# Enable timer
echo "Enabling timer..."
systemctl --user enable insightweaver-daily.timer

# Start timer
echo "Starting timer..."
systemctl --user start insightweaver-daily.timer

echo ""
echo "========================================"
echo "Installation Complete!"
echo "========================================"
echo ""
echo "The daily report will run at 8:00 AM every day."
echo ""
echo "Useful commands:"
echo "  Check timer status:    systemctl --user status insightweaver-daily.timer"
echo "  View next run time:    systemctl --user list-timers insightweaver-daily.timer"
echo "  Run manually now:      systemctl --user start insightweaver-daily.service"
echo "  View logs:             journalctl --user -u insightweaver-daily.service -f"
echo "  Stop timer:            systemctl --user stop insightweaver-daily.timer"
echo "  Disable timer:         systemctl --user disable insightweaver-daily.timer"
echo ""
echo "To customize the schedule, edit:"
echo "  $USER_SYSTEMD_DIR/insightweaver-daily.timer"
echo "Then run: systemctl --user daemon-reload && systemctl --user restart insightweaver-daily.timer"
echo ""

# Show timer status
echo "Current timer status:"
systemctl --user list-timers insightweaver-daily.timer
