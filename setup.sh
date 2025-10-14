#!/bin/bash

echo "�� Setting up ACAT Correction Service..."

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env and add your Anthropic API key!"
else
    echo "✅ .env file already exists"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To run the service:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Add your Anthropic API key to .env file"
echo "3. Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo "4. Open http://localhost:8000 in your browser"
echo ""
