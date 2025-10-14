# ACAT Correction Service - Project Structure

```
acat-correction-service/
├── main.py                          # FastAPI application entry point
├── requirements.txt                 # Python dependencies
├── .env.example                    # Environment variables template
├── .gitignore                      # Git ignore rules
├── setup.sh                        # Setup script
├── README.md                       # Main documentation
├── PROJECT_STRUCTURE.md            # This file
│
├── models/                         # Pydantic data models
│   ├── __init__.py
│   └── acat.py                     # ACAT data models and validation
│
├── services/                       # Business logic services
│   ├── __init__.py
│   ├── claude_service.py           # Claude AI integration
│   └── validation_service.py       # Basic ACAT validation
│
└── static/                         # Web dashboard files
    ├── index.html                  # Main dashboard UI
    ├── styles.css                  # CSS styling
    └── app.js                      # Frontend JavaScript
```

## Key Components

### Backend (Python/FastAPI)
- **main.py**: FastAPI application with REST endpoints
- **models/acat.py**: Pydantic models for ACAT data validation
- **services/claude_service.py**: Claude AI integration for analysis
- **services/validation_service.py**: Basic validation rules

### Frontend (HTML/CSS/JavaScript)
- **static/index.html**: Interactive dashboard for operators
- **static/styles.css**: Modern, responsive styling
- **static/app.js**: Client-side logic for form handling and AI suggestions

### Configuration
- **requirements.txt**: Python package dependencies
- **.env.example**: Environment variables template
- **setup.sh**: Automated setup script

## API Endpoints

- `GET /` - Web dashboard interface
- `POST /api/validate-acat` - Validate ACAT data and get AI suggestions
- `POST /api/submit-acat` - Submit corrected ACAT data
- `GET /api/health` - Health check
- `GET /api/contra-firms` - Get list of common contra firms

## Features

✅ **AI-Powered Validation**: Uses Claude AI to analyze ACAT data
✅ **Interactive Dashboard**: Modern web UI for operators
✅ **Real-time Suggestions**: AI provides correction suggestions with confidence scores
✅ **Operator Control**: Accept/reject/modify AI suggestions before submission
✅ **Success Probability**: Estimates likelihood of DTCC acceptance
✅ **Comprehensive Validation**: Covers all major ACAT fields and common rejection reasons
✅ **Responsive Design**: Works on desktop and mobile devices
