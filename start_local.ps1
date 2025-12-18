# Start MCP Service locally for development
# This connects to the remote Bielik App on HuggingFace Spaces

Write-Host "Starting MCP Service locally..." -ForegroundColor Green
Write-Host "MCP will be available at: http://localhost:8001" -ForegroundColor Cyan
Write-Host "It will call Bielik App at: https://patst-bielik-app-service.hf.space" -ForegroundColor Cyan
Write-Host ""

# Install dependencies if needed
if (-not (Test-Path ".\venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install requirements
Write-Host "Installing requirements..." -ForegroundColor Yellow
pip install -r requirements.txt

# Start the server
Write-Host "Starting Uvicorn server..." -ForegroundColor Green
uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
