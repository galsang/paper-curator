#!/bin/bash
# Setup daily cron job for paper curator
# Runs every weekday at 9:00 AM KST

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_PATH="$(which python3)"
LOG_FILE="${SCRIPT_DIR}/output/cron.log"

# Create output directory
mkdir -p "${SCRIPT_DIR}/output"

# Cron expression: 9 AM KST (0 AM UTC) on weekdays (Mon-Fri)
CRON_EXPR="0 0 * * 1-5"

# Build the cron command
CRON_CMD="${CRON_EXPR} cd ${SCRIPT_DIR} && ${PYTHON_PATH} main.py --save --slack --notion >> ${LOG_FILE} 2>&1"

echo "=== Paper Curator Cron Setup ==="
echo ""
echo "Script directory: ${SCRIPT_DIR}"
echo "Python path: ${PYTHON_PATH}"
echo "Schedule: Weekdays at 9:00 AM KST"
echo ""
echo "Cron entry to add:"
echo "  ${CRON_CMD}"
echo ""

read -p "Add to crontab? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Add to crontab (preserve existing entries)
    (crontab -l 2>/dev/null | grep -v "paper-curator"; echo "${CRON_CMD}") | crontab -
    echo "Cron job added! Verify with: crontab -l"
else
    echo "Skipped. You can manually add the cron entry above."
    echo "  crontab -e"
fi
