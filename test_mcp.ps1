# PowerShell curl/Invoke-WebRequest test for MCP Service

# Health check
Write-Host "Testing health endpoint..." -ForegroundColor Green
curl -X GET http://localhost:8001/health
Write-Host ""

# Test infill request
Write-Host "Testing infill endpoint..." -ForegroundColor Green

$body = @{
    domain = "cars"
    data = @{
        make = "Volkswagen"
        model = "Golf"
        year = 2020
        mileage = 150000
        features = @("leather seats", "sunroof", "cruise control")
        condition = "excellent"
        description_template = "Sprzedam [GAP:1] Volkswagena Golf w kolorze [GAP:2] z silnikiem [GAP:3]."
    }
} | ConvertTo-Json

Write-Host "Request body:"
Write-Host $body
Write-Host ""

$response = Invoke-WebRequest -Uri "http://localhost:8001/api/v1/enhance-description" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body

Write-Host "Response:" -ForegroundColor Green
$response.Content | ConvertFrom-Json | ConvertTo-Json
