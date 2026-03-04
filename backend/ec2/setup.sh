#!/bin/bash
# EC2 User Data script — installs and starts the screenshot microservice
# Run on Ubuntu 22.04 LTS (t3.small)

set -e

apt-get update -y
apt-get install -y python3-pip python3-venv

# Create app directory
mkdir -p /opt/screenshot-service
cd /opt/screenshot-service

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install flask playwright gunicorn
playwright install --with-deps chromium

# Copy service file (will be placed by CDK user data)
cat > /opt/screenshot-service/app.py << 'PYEOF'
