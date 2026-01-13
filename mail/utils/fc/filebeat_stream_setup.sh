#!/bin/bash
set -e

SERVER="{{ server }}"
FILEBEAT_INPUT_PATH="/etc/filebeat/inputs.d/${SERVER}.yml"
FILEBEAT_RESTART_CMD="systemctl restart filebeat"

echo "Setting up Filebeat filestream for Stalwart logs..."

sudo bash -c "cat > $FILEBEAT_INPUT_PATH" <<EOF
- type: filestream
  enabled: true
  pipeline: "stalwart-log"
  paths:
    - /opt/stalwart/$SERVER/logs/stalwart.log.*
EOF

echo "Restarting Filebeat service..."
sudo bash -c "$FILEBEAT_RESTART_CMD"

echo "Filebeat filestream setup complete for Stalwart logs on $SERVER."