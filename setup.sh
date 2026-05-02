#!/bin/bash
# Setup script for Active Directory Behavioral Analysis project

echo "=========================================="
echo "AD Behavioral Analysis - Setup"
echo "=========================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

echo "✓ Python $(python3 --version) found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Install and start Neo4j (see README.md)"
echo "3. Configure Neo4j credentials in src/*.py files"
echo "4. Run: jupyter notebook main.ipynb"
echo ""
echo "Or run step-by-step:"
echo "  python src/preprocess.py"
echo "  python src/neo4j_importer.py"
echo "  python src/anomaly_detection.py"
echo "  python src/analysis.py"
echo ""
