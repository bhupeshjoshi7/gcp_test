#!/usr/bin/env bash
# ==============================================================================
# Setup script for GCP VM (Ubuntu / Debian / Rocky / CentOS)
# ==============================================================================
set -e

echo "=== [1/4] Checking Python & Virtualenv ==="
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed. Installing python3 and python3-venv..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update -y && sudo apt-get install -y python3 python3-venv python3-pip
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y python3 python3-pip
    elif command -v yum &> /dev/null; then
        sudo yum install -y python3 python3-pip
    fi
fi

echo "=== [2/4] Setting up Virtual Environment ==="
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created at ./venv"
fi

echo "=== [3/4] Installing Python Dependencies ==="
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [4/4] Checking Environment Configuration ==="
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "Created .env from .env.example."
    echo "--> Please edit .env with your SFTP credentials and GCS bucket name: nano .env"
    echo ""
else
    echo ".env file already exists."
fi

echo "=== Setup complete! ==="
echo "To activate environment: source venv/bin/activate"
echo "To run transfer:         python main.py"
