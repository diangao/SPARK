# S.P.A.R.K. VPS Deployment

## Quick Start

### 1. Create VPS
- Go to [DigitalOcean](https://digitalocean.com)
- Create Droplet: Ubuntu 24.04, $4/month (Basic, Regular SSD)
- Add your SSH key

### 2. SSH into VPS
```bash
ssh root@<your-vps-ip>
```

### 3. Install Docker
```bash
curl -fsSL https://get.docker.com | sh
apt-get install -y docker-compose-plugin
```

### 4. Clone Repos
```bash
# S.P.A.R.K.
git clone https://github.com/<you>/spark.git /opt/spark

# Think OS (private repo - need deploy key or token)
git clone https://github.com/<you>/think-os.git /root/think-os
```

### 5. Configure
```bash
cd /opt/spark
cp config/.env.example config/.env
nano config/.env  # Add your API keys
```

### 6. Run
```bash
docker compose up -d
docker compose logs -f  # View logs
```

### 7. Setup Git Sync (cron)
```bash
chmod +x /opt/spark/deploy/sync-think-os.sh
crontab -e
# Add: */5 * * * * /opt/spark/deploy/sync-think-os.sh >> /var/log/think-os-sync.log 2>&1
```

## Commands

```bash
# View logs
docker compose logs -f

# Restart
docker compose restart

# Stop
docker compose down

# Update code
git pull && docker compose up -d --build
```

## Think OS Sync

The `sync-think-os.sh` script runs every 5 minutes:
1. Pulls latest changes from GitHub
2. Pushes any changes Spark made

For the sync to work, set up SSH key or use GitHub token:
```bash
# Generate SSH key on VPS
ssh-keygen -t ed25519 -C "spark-bot"
cat ~/.ssh/id_ed25519.pub
# Add to GitHub repo as Deploy Key (with write access)
```
