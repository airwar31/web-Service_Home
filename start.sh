#!/usr/bin/env bash
set -e

if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required. Please install Python 3."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing / verifying dependencies..."
pip install -r requirements.txt

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "Generating .env configuration..."
    cp .env.example .env
fi

echo "Starting SmartHome OS (MVC Server)..."
python main.py "$@"
