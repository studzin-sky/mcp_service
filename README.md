# MCP Service (Model Context Protocol)

**MCP Service** is a middleware application designed to orchestrate AI text enhancement. It bridges client applications and the `bielik_app_service` to provide high-quality, context-aware text infilling with robust validation and Polish grammar correction.

## Key Features

*   **Smart Preprocessing:** Normalizes text and optimizes context for better model performance.
*   **Gap Management:** Detects and manages `[GAP:n]` markers and text placeholders.
*   **Polish Grammar Correction:** Automatically fixes case agreements (declensions) for adjectives based on context.
*   **Guardrails & Validation:** Ensures output quality, structure, and domain relevance.
*   **Resilient Batch Processing:** Handles multiple items efficiently to prevent timeouts.

## Architecture Flow

1.  **Client Request:** Sends text with gaps (e.g., "Fiat 500 [GAP:1]").
2.  **Preprocessing:** Normalizes text, extracts gap context.
3.  **Bielik Inference:** Calls the LLM service to generate fill content.
4.  **Postprocessing:** Formats output, reconstructs text, and applies Polish grammar rules.
5.  **Response:** Returns the enhanced text with validation reports.

## Getting Started

### Prerequisites

*   Python 3.8+
*   `bielik_app_service` running (for inference)

### Installation

```bash
pip install -r requirements.txt
```

### Running Locally

```bash
uvicorn app.main:app --reload --port 8002
```

The service will be available at `http://localhost:8002`.

## API Endpoints

*   `POST /api/v1/enhance-description`: Main endpoint for text enhancement.
*   `POST /api/v1/batch-enhance`: Process multiple items in a single request.
*   `GET /health`: Service health check.

## Documentation

For detailed architecture, component breakdown, and advanced configuration, please refer to [README_MCP.md](README_MCP.md).
