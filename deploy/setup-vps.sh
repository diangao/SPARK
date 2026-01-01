#!/bin/bash
# VPS Setup Script for S.P.A.R.K.
# Run on a fresh Ubuntu VPS

set -e

echo "=== S.P.A.R.K. VPS Setup ==="

# Update system
echo "Updating system..."
apt-get update && apt-get upgrade -y

# Install Docker
echo "Installing Docker..."
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
echo "Installing Docker Compose..."
apt-get install -y docker-compose-plugin

# Create app directory
mkdir -p /opt/spark
cd /opt/spark

# Clone S.P.A.R.K. repo (you'll need to set this up)
echo "Clone your S.P.A.R.K. repo to /opt/spark"
echo "  git clone <your-spark-repo> ."

# Clone Think OS repo
echo "Clone your Think OS repo to /root/think-os"
echo "  git clone <your-think-os-repo> /root/think-os"

# Create .env file
echo "Create config/.env with your credentials"
echo "  cp config/.env.example config/.env"
echo "  nano config/.env"

echo ""
echo "=== After setup, run: ==="
echo "  cd /opt/spark"
echo "  docker compose up -d"
echo ""
echo "=== To view logs: ==="
echo "  docker compose logs -f"
