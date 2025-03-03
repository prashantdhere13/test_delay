# Video Delay Server

A web application that allows users to add delay to video streams with support for UDP multicast and SRT streams.

## Project Structure
- `frontend/`: React-based web interface
- `backend/`: FastAPI-based server
- `requirements.txt`: Python dependencies
- `package.json`: Frontend dependencies

## Ubuntu Server Installation Guide

### 1. System Requirements
- Ubuntu Server 20.04 LTS or newer
- Python 3.8 or newer
- Node.js 16 or newer
- MariaDB 10.3 or newer

### 2. Install System Dependencies
```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Install Python and development tools
sudo apt install -y python3 python3-pip python3-venv

# Install Node.js and npm
curl -fsSL https://deb.nodesource.com/setup_16.x | sudo -E bash -
sudo apt install -y nodejs

# Install MariaDB
sudo apt install -y mariadb-server mariadb-client

# Install additional dependencies
sudo apt install -y build-essential python3-dev
```

### 3. Configure MariaDB
```bash
# Secure MariaDB installation
sudo mysql_secure_installation

# Create database and user
sudo mysql -e "CREATE DATABASE video_delay;"
sudo mysql -e "CREATE USER 'videouser'@'localhost' IDENTIFIED BY 'your_password';"
sudo mysql -e "GRANT ALL PRIVILEGES ON video_delay.* TO 'videouser'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"
```

### 4. Clone and Setup Backend
```bash
# Clone repository (if using git) or copy files
git clone <repository-url>
cd video-delay-server

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Configure environment variables
cd backend
cat > .env << EOL
DATABASE_URL=mysql+pymysql://videouser:your_password@localhost/video_delay
SECRET_KEY=your-secret-key-keep-it-secret
EOL
```

### 5. Setup Frontend
```bash
# Install frontend dependencies
cd ../frontend
npm install

# Build frontend for production
npm run build
```

### 6. Setup Nginx (Web Server)
```bash
# Install Nginx
sudo apt install -y nginx

# Create Nginx configuration
sudo cat > /etc/nginx/sites-available/video-delay << EOL
server {
    listen 80;
    server_name your_domain.com;

    # Frontend
    location / {
        root /path/to/video-delay-server/frontend/build;
        try_files \$uri \$uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://localhost:8000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOL

# Enable the site
sudo ln -s /etc/nginx/sites-available/video-delay /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 7. Setup Systemd Service for Backend
```bash
# Create systemd service file
sudo cat > /etc/systemd/system/video-delay.service << EOL
[Unit]
Description=Video Delay Server Backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/video-delay-server/backend
Environment="PATH=/path/to/video-delay-server/venv/bin"
ExecStart=/path/to/video-delay-server/venv/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOL

# Start and enable the service
sudo systemctl daemon-reload
sudo systemctl start video-delay
sudo systemctl enable video-delay
```

### 8. Configure Firewall
```bash
# Allow HTTP, HTTPS, and SSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp

# Allow UDP multicast ports (adjust range as needed)
sudo ufw allow 5000:5010/udp

# Enable firewall
sudo ufw enable
```

### 9. Verify Installation
1. Check service status:
```bash
sudo systemctl status video-delay
sudo systemctl status nginx
```

2. Check logs:
```bash
sudo journalctl -u video-delay -f
```

3. Access the web interface:
```
http://your_domain.com
```

## Production Considerations

1. SSL/TLS Certificate:
```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate
sudo certbot --nginx -d your_domain.com
```

2. Regular Backups:
```bash
# Setup automatic database backups
sudo cat > /etc/cron.daily/backup-video-delay << EOL
#!/bin/bash
backup_dir="/path/to/backups"
timestamp=\$(date +%Y%m%d_%H%M%S)
mysqldump -u videouser -p'your_password' video_delay > "\$backup_dir/video_delay_\$timestamp.sql"
EOL

sudo chmod +x /etc/cron.daily/backup-video-delay
```

3. Monitoring:
```bash
# Install monitoring tools
sudo apt install -y prometheus node-exporter
```

## Troubleshooting

1. Check backend logs:
```bash
sudo journalctl -u video-delay -f
```

2. Check Nginx logs:
```bash
sudo tail -f /var/log/nginx/error.log
```

3. Check MariaDB logs:
```bash
sudo tail -f /var/log/mysql/error.log
```

4. Common issues:
- If streams aren't working, check UDP multicast permissions:
```bash
sudo sysctl net.ipv4.ip_forward=1
```
- If database connection fails, verify MariaDB is running:
```bash
sudo systemctl status mariadb
```

## Security Notes

1. Always change default passwords
2. Keep system and packages updated
3. Use strong passwords for MariaDB and user accounts
4. Configure firewall rules appropriately
5. Regularly monitor system logs
6. Keep backups in a secure location

For additional support or issues, please contact the system administrator.
