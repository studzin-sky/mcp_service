# Test MCP Service with curl

# Health check
curl -X GET http://localhost:8001/health

# Enhance car description (infill test)
curl -X POST http://localhost:8001/api/v1/enhance-description \
  -H "Content-Type: application/json" \
  -d '{
  "domain": "cars",
  "data": {
    "make": "Volkswagen",
    "model": "Golf",
    "year": 2020,
    "mileage": 150000,
    "features": ["leather seats", "sunroof", "cruise control"],
    "condition": "excellent",
    "description_template": "Sprzedam [GAP:1] Volkswagena Golf w kolorze [GAP:2] z silnikiem [GAP:3]."
  }
}'
