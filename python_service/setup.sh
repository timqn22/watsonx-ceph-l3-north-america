#!/bin/bash

# Python Service Setup Script

echo "=========================================="
echo "Ceph Tracker Linker - Python Service Setup"
echo "=========================================="
echo

# Check Python version
echo "Checking Python version..."
python_version=$(python3 --version 2>&1)
echo "✓ $python_version"
echo

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install Python 3 and pip3."
    exit 1
else
    echo "✓ pip3 is installed"
fi
echo

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip
echo

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"
echo

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p tests
mkdir -p embeddings
mkdir -p cache
echo "✓ Directories created"
echo

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ Created .env file"
    echo "  ⚠️  Please edit .env and add your API keys!"
else
    echo "✓ .env file already exists"
fi
echo

# Make test script executable
chmod +x test_scrapers.py
echo "✓ Made test_scrapers.py executable"
echo

echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo
echo "2. Configure your credentials in .env file"
echo
echo "3. Test the scrapers:"
echo "   python test_scrapers.py"
echo
echo "4. Run unit tests (when available):"
echo "   pytest tests/"
echo
echo "5. Start the Flask service (when ready):"
echo "   python app.py"
echo
echo "=========================================="

# Made with Bob
