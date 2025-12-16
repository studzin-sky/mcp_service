# Local MCP Service Testing Guide

## Setup

### 1. Start MCP Service Locally

```powershell
cd mcp_service
.\start_local.ps1
```

The service will run on `http://localhost:8001`

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8001
INFO:     Application startup complete
```

### 2. Verify Health

```bash
curl http://localhost:8001/health
```

Should return: `{"status":"ok"}`

---

## Postman Testing

### Test 1: Health Check
```
GET http://localhost:8001/health
```

**Expected:** `{"status": "ok"}`

---

### Test 2: Enhance Car Description (Full MCP Flow)

**URL:** `POST http://localhost:8001/api/v1/enhance-description`

**Body (JSON):**
```json
{
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
}
```

**Flow:**
1. MCP validates input with Pydantic
2. MCP calls Bielik (on HuggingFace Spaces) to infill gaps
3. MCP applies post-processing (Polish grammar fixes)
4. MCP returns enhanced description

**Expected Response:**
```json
{
  "domain": "cars",
  "enhanced_description": "Sprzedam używanego Volkswagena Golf w kolorze białym z silnikiem benzynowym.",
  "gaps": [
    {"index": 1, "choice": "używanego", "alternatives": ["zadbaanego", "pięknego"]},
    {"index": 2, "choice": "białym", "alternatives": ["czarnym", "srebrnym"]},
    {"index": 3, "choice": "benzynowym", "alternatives": ["dieselowym", "hybrydowym"]}
  ],
  "processing_time_ms": 1234,
  "timestamp": "2025-12-15T12:34:56Z"
}
```

---

## Architecture Diagram

```
┌──────────────┐
│   Postman    │
└──────┬───────┘
       │ HTTP POST
       ▼
┌──────────────────────┐
│   MCP Service        │ (localhost:8001)
│ - Preprocessing      │
│ - Guardrails         │
│ - Postprocessing     │
└──────────┬───────────┘
           │ HTTP POST (infill)
           ▼
┌──────────────────────────────────────────┐
│  Bielik App Service (HuggingFace Spaces) │
│  https://studzinsky-bielik-app-service   │
│  - Model inference                       │
│  - Gap filling                           │
└──────────────────────────────────────────┘
```

---

## Configuration

**Local Config:** `.env.local`
```
BIELIK_APP_URL=https://studzinsky-bielik-app-service.hf.space
MCP_PORT=8001
MCP_HOST=127.0.0.1
```

**Docker Config:** Environment in `docker-compose.yml`
```yaml
BIELIK_APP_URL=http://bielik_app_service:8000
```

---

## Troubleshooting

### "Connection refused" to Bielik
- Verify Bielik is running on HuggingFace Spaces
- Check `BIELIK_APP_URL` in `.env.local` is correct
- Try the direct URL in browser: `https://studzinsky-bielik-app-service.hf.space/health`

### "ModuleNotFoundError" when starting MCP
- Run `pip install -r requirements.txt` in virtual env
- Ensure you're in the `mcp_service` directory

### Slow response
- First call to Bielik may take 10-30s (model warmup on CPU)
- Subsequent calls are faster (cached)

