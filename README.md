# ACAT Correction Service with Claude AI

A FastAPI-based service that helps operators validate ACAT (Automated Customer Account Transfer) data using Claude AI to suggest corrections and prevent DTCC rejections.

## Features

- Interactive web dashboard for ACAT data entry and review
- AI-powered validation and correction suggestions using Claude
- Real-time feedback on common DTCC rejection patterns
- Operator control over accepting/modifying AI suggestions

## Setup

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your Anthropic API key
   ```

4. **Run the service:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

5. **Access the dashboard:**
   Open http://localhost:8000 in your browser

## API Endpoints

- `POST /api/validate-acat` - Validate ACAT data and get AI suggestions
- `GET /api/health` - Health check endpoint
- `GET /` - Web dashboard interface

## ACAT Data Fields

The service validates standard ACAT fields including:
- Account numbers (delivering/receiving)
- Contra firm (DTCC participant number)
- Transfer type (full/partial)
- Securities (CUSIP, quantity, asset type)
- Customer information
- Special handling instructions
