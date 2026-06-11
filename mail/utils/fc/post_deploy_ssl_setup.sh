#!/bin/bash
set -e

SERVER="{{ server }}"
HTTPS_PORT="{{ https_port }}"
CONTACT_EMAIL="{{ contact_email }}"
CONTAINER_NAME="{{ container_name }}"
NGINX_CONF_PATH="/etc/nginx/conf.d/${SERVER}.conf"
NGINX_RELOAD_CMD="systemctl reload nginx || docker exec nginx nginx -s reload"

: "${SERVER:?SERVER is required}"
: "${HTTPS_PORT:?HTTPS_PORT is required}"
: "${CONTACT_EMAIL:?CONTACT_EMAIL is required}"
: "${CONTAINER_NAME:?CONTAINER_NAME is required}"

# -------------------------------
# Step 1: Install dependencies
# -------------------------------
echo "Updating packages and installing Certbot..."
sudo apt-get update -y
sudo apt-get install -y certbot python3-certbot-nginx docker-compose nginx

# -------------------------------
# Step 2: Generate or renew certificate
# -------------------------------
if [ ! -d "/etc/letsencrypt/live/$SERVER" ]; then
    echo "Generating new SSL certificate for $SERVER..."
    sudo certbot certonly --standalone \
    -d "$SERVER" \
    --email "$CONTACT_EMAIL" \
    --agree-tos \
    --non-interactive
else
    echo "Certificate already exists for $SERVER, renewing..."
    sudo certbot renew --non-interactive
fi

# -------------------------------
# Step 3: Configure Nginx
# -------------------------------
echo "Setting up Nginx reverse proxy configuration..."

sudo bash -c "cat > $NGINX_CONF_PATH" <<EOF
server {
    listen 443 ssl http2;
    server_name $SERVER;

    ssl_certificate /etc/letsencrypt/live/$SERVER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$SERVER/privkey.pem;

    location / {
        proxy_pass https://127.0.0.1:$HTTPS_PORT;
        proxy_ssl_server_name on;

        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For \$remote_addr;
    }
}
EOF

echo "Testing & Reloading Nginx configuration..."
sudo nginx -t && sudo bash -c "$NGINX_RELOAD_CMD"

# -------------------------------
# Step 4: Restart Docker stack
# -------------------------------
echo "Restarting Docker stack..."
cd "/etc/stalwart/$SERVER"
sudo docker-compose down
sudo docker-compose up -d

echo "Setup complete! SSL enabled for $SERVER."
