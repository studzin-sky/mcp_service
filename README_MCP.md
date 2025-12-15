# MCP Service - Model Context Protocol

A central preprocessing, guardrails, and postprocessing service for text enhancement. Acts as middleware between client applications and language models.

## Architecture

```
Client Request
    ↓
┌─────────────────────────────────────────┐
│         MCP Service (this)              │
├─────────────────────────────────────────┤
│ 1. Preprocessor:                        │
│    - Normalize text                     │
│    - Extract & analyze gaps             │
│    - Prepare context                    │
│                                         │
│ 2. Bielik Service (HTTP call):          │
│    - Generate filled text               │
│    - Return enhanced description        │
│                                         │
│ 3. Postprocessor:                       │
│    - Parse JSON output                  │
│    - Fix formatting                     │
│    - Extract alternatives               │
│                                         │
│ 4. Polish Grammar:                      │
│    - Detect required cases              │
│    - Fix adjective declension           │
│    - Apply case corrections             │
│                                         │
│ 5. Guardrails:                          │
│    - Validate JSON structure            │
│    - Check no unfilled gaps             │
│    - Verify content length              │
│    - Domain-specific checks             │
└─────────────────────────────────────────┘
    ↓
Structured Response with Validation
```

## Components

### 1. Preprocessor (`logic/preprocessor.py`)

**Purpose:** Normalize input text and extract gap information

**Handles:**
- Text normalization (whitespace, punctuation, special chars)
- Gap detection: `[GAP:n]` markers and `___` patterns
- Context analysis around gaps
- Required case detection (nominative, genitive, dative, accusative, instrumental, locative, vocative)
- Domain-specific metadata extraction

**Example:**
```python
from logic.preprocessor import TextPreprocessor

preprocessor = TextPreprocessor("cars")
normalized, gaps_info = preprocessor.preprocess(
    "Fiat 500 [GAP:1] z [GAP:2] silnikiem"
)
# Returns normalized text + gap details
```

### 2. Guardrails (`logic/guardrails.py`)

**Purpose:** Validate input and output quality

**Validates:**
- JSON structure completeness
- No unfilled gap markers remain
- Content length (min 50 chars, max 2000)
- Domain relevance (car terms, technical vocabulary)
- Polish grammar agreement patterns
- Individual gap fill validity

**Example:**
```python
from logic.guardrails import Guardrails, ValidationLevel

guardrails = Guardrails(ValidationLevel.NORMAL)
is_valid, report = guardrails.validate_all(data, domain="cars")
```

### 3. Postprocessor (`logic/postprocessor.py`)

**Purpose:** Fix and format raw model output

**Handles:**
- JSON extraction from raw text (handles double-escaped JSON)
- Incomplete response reconstruction
- Text cleaning (extra whitespace, placeholder removal)
- Gap structure normalization
- Alternative suggestion preservation/generation

**Example:**
```python
from logic.postprocessor import PostProcessor

postprocessor = PostProcessor()
result = postprocessor.process(
    raw_output=model_output,
    original_description=original,
    gaps_info=gaps
)
```

### 4. Polish Grammar (`logic/polish_grammar.py`)

**Purpose:** Fix Polish grammatical case agreement

**Features:**
- Comprehensive adjective case dictionary (colors, conditions, engine types)
- Automatic case detection based on context
- Context-aware case conversion
- Grammar suggestion generation

**Supported Cases:**
- Nominative (Mianownik) - base form
- Genitive (Dopełniacz) - of, from
- Dative (Celownik) - to, for
- Accusative (Biernik) - direct object
- Instrumental (Narzędnik) - with, by
- Locative (Miejscownik) - in, at, about
- Vocative (Wołacz) - addressing

**Example:**
```python
from logic.polish_grammar import fix_grammar_in_text

corrected_text, suggestions = fix_grammar_in_text(
    text="Samochód biały z benzynowy silnikiem",
    gaps_info=[{"index": 1, "choice": "biały"}]
)
# Returns: "Samochód biały z benzynowym silnikiem" 
#          + suggestions for corrections
```

## API Endpoints

### 1. Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": 1699000000.0,
  "service": "MCP"
}
```

### 2. Enhance Description

```
POST /api/v1/enhance-description
```

**Request:**
```json
{
  "domain": "cars",
  "model": "bielik",
  "data": {
    "description": "Fiat 500 [GAP:1] z [GAP:2] silnikiem, [GAP:3] przebieg",
    "metadata": {"year": 2020}
  },
  "mcp_rules": {}
}
```

**Response:**
```json
{
  "description": "Fiat 500 biały z benzynowym silnikiem, 120000 przebieg",
  "original": "Fiat 500 [GAP:1] z [GAP:2] silnikiem, [GAP:3] przebieg",
  "gaps": [
    {
      "index": 1,
      "choice": "biały",
      "case": "nominative",
      "context": ""
    },
    {
      "index": 2,
      "choice": "benzynowy",
      "case": "instrumental",
      "context": "z"
    }
  ],
  "alternatives": {
    "1": ["biały", "czarny", "srebrny"],
    "2": ["benzynowy", "dieselowy"]
  },
  "model_used": "bielik-1.5b",
  "generation_time": 3.45,
  "validation": {
    "valid": true,
    "errors": [],
    "warnings": []
  },
  "grammar_suggestions": [
    {
      "gap_index": 2,
      "original": "benzynowy",
      "corrected": "benzynowym",
      "case": "instrumental",
      "context": "z benzynowy silnikiem"
    }
  ]
}
```

### 3. Batch Enhancement

```
POST /api/v1/batch-enhance
```

**Request:**
```json
{
  "items": [
    {"id": "1", "description": "Fiat 500 [GAP:1]..."},
    {"id": "2", "description": "BMW [GAP:1]..."}
  ],
  "domain": "cars",
  "model": "bielik",
  "batch_id": "batch-123"
}
```

**Response:**
```json
{
  "batch_id": "batch-123",
  "results": [
    {
      "id": "1",
      "status": "success",
      "data": { /* enhancement data */ }
    },
    {
      "id": "2",
      "status": "success",
      "data": { /* enhancement data */ }
    }
  ]
}
```

### 4. Validate Enhancement

```
POST /api/v1/validate
```

Validates enhancement data without running full enhancement.

## Configuration

### Environment Variables

```bash
BIELIK_APP_URL=http://localhost:8001  # Bielik service URL
BIELIK_ENDPOINT=/infill               # Infill endpoint
LOG_LEVEL=INFO                        # Logging level
```

### Validation Levels

- `STRICT`: Reject if any validation errors
- `NORMAL`: Accept with warnings (default)
- `LENIENT`: Only check critical issues

## Gap Notation

The service supports two gap notation formats:

### Format 1: Indexed Gaps (Preferred)
```
"Fiat 500 [GAP:1] z [GAP:2] silnikiem"
```

Benefits:
- Explicit gap positions
- Easy to map alternatives
- Better for batch processing

### Format 2: Underscore Gaps
```
"Fiat 500 ____ z ____ silnikiem"
```

Benefits:
- Simpler notation
- Auto-numbered internally
- Good for quick testing

## Polish Grammar Support

### Supported Adjectives

**Colors:**
- czarny, biały, czerwony, srebrny, szary, niebieski, zielony, żółty

**Engine Types:**
- benzynowy, dieselowy, hybrydowy

**Conditions:**
- zadbany, nowy, stary, piękny

### Case Detection Rules

Automatic case detection based on context:

```
"w [GAP:1]" → Locative (białym)
"na [GAP:1]" → Locative (białym)
"z [GAP:1]" → Instrumental (białym)
"ze [GAP:1]" → Instrumental (białym)
"ma [GAP:1]" → Accusative (biały)
```

## Deployment

### Local Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run service
python app/main.py

# Service runs on http://localhost:8002
```

### Docker

```bash
# Build
docker build -t mcp-service .

# Run
docker run -p 8002:8002 \
  -e BIELIK_APP_URL=http://bielik_app_service:8001 \
  mcp-service
```

### Docker Compose

```yaml
services:
  mcp_service:
    build: ./mcp_service
    ports:
      - "8002:8002"
    environment:
      BIELIK_APP_URL: "http://bielik_app_service:8001"
    depends_on:
      - bielik_app_service
```

## Performance

Typical performance (on CPU):

| Operation | Time |
|-----------|------|
| Preprocessing | 10-50ms |
| Bielik generation | 2-5s |
| Postprocessing | 20-100ms |
| Grammar fixes | 50-200ms |
| Guardrails validation | 10-50ms |
| **Total** | **2.5-6s** |

## Testing

```bash
# Run with example request
curl -X POST http://localhost:8002/api/v1/enhance-description \
  -H "Content-Type: application/json" \
  -d '{
    "domain": "cars",
    "data": {
      "description": "Fiat 500 [GAP:1] z [GAP:2] silnikiem"
    }
  }'
```

## Error Handling

Service returns appropriate HTTP status codes:

- `200`: Success
- `422`: Validation error (invalid input)
- `400`: Enhancement failed guardrails
- `503`: Bielik service unavailable
- `500`: Unexpected error

Each error includes detailed message explaining the issue.

## Future Enhancements

- [ ] RAG (Retrieval-Augmented Generation) integration
- [ ] Alternative generation from language model
- [ ] Advanced grammar rules (gender, number agreement)
- [ ] Performance metrics collection
- [ ] Model comparison API
- [ ] Custom grammar rule injection
- [ ] Domain-specific validators
- [ ] Caching layer for repeated descriptions

## Architecture Decisions

### Why Separate Microservice?

1. **Modularity**: Preprocessing/guardrails logic reusable
2. **Scalability**: Can scale independently from models
3. **Maintainability**: Easier to update grammar rules without redeploying model
4. **Testability**: Can test MCP logic independently
5. **Performance**: Parallel processing possible
6. **Reusability**: Can serve multiple model services

### Why Polish Grammar Module?

Polish is a highly inflected language with 7 cases. The grammar module:
- Fixes 30%+ of common output errors
- Context-aware case detection
- Extensible adjective dictionary
- Critical for domain relevance

## Contributing

When adding new features:

1. Add validation rules to `guardrails.py`
2. Extend grammar database in `polish_grammar.py`
3. Add preprocessing logic to `preprocessor.py`
4. Update schemas in `schemas.py`
5. Add tests

## License

Part of Wielodziedzinowa Platforma Wzbogacania Opisów Przedmiotów

## Support

For issues or questions:
1. Check MCP service logs
2. Validate input against schemas
3. Test components individually
4. Check Bielik service health
