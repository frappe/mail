#!/bin/bash
set -e

SERVER="{{ server }}"
CONTACT_EMAIL="{{ contact_email }}"
CONTAINER_NAME="{{ container_name }}"
NGINX_CONF_PATH="/etc/nginx/conf.d/mail.conf"
NGINX_RELOAD_CMD="systemctl reload nginx || docker exec nginx nginx -s reload"

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
    listen 443 ssl;
    server_name $SERVER;

    ssl_certificate /etc/letsencrypt/live/$SERVER/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$SERVER/privkey.pem;

    location / {
        proxy_pass https://127.0.0.1:8443;
        proxy_set_header Host \$host;
    }
}
EOF

echo "Testing Nginx configuration..."
sudo nginx -t

echo "Reloading Nginx service..."
sudo bash -c "$NGINX_RELOAD_CMD"

# -------------------------------
# Step 4: Restart Docker stack
# -------------------------------
echo "Restarting Docker stack..."
cd "/opt/stalwart/$SERVER"
sudo docker-compose down
sudo docker-compose up -d

echo "Setup complete! SSL enabled for $SERVER."
