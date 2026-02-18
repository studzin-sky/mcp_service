"""
MCP Service - Model Context Protocol
=====================================
Gateway service that:
1. Validates incoming requests
2. Detects gaps in text locally
3. Builds domain-specific prompts
4. Calls Bielik /chat for inference (pure GPU)
5. Parses & reconstructs responses
6. Applies guardrails

Bielik now only does inference. MCP handles all business logic.
"""

import os
import time
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Import our new components
from app.logic.bielik_client import BielikClient
from app.logic.infill_utils import detect_gaps, parse_infill_response, apply_fills
from app.logic import guardrails
from app.logic.prompt_strategy import choose_strategy, build_per_gap_prompts
from app.logic.text_analyzer import TextAnalyzer
from app.mcp.server import create_mcp_router

# Import polish_grammar safely (requires spacy)
try:
    from app.logic import polish_grammar
except ImportError:
    polish_grammar = None

app = FastAPI(
    title="Model Context Protocol (MCP) Service",
    description="Gateway for AI model interactions with validation and guardrails.",
    version="2.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BIELIK_APP_URL = os.getenv("BIELIK_APP_URL", "http://bielik_app_service:8000")
MCP_PORT = int(os.getenv("MCP_PORT", 8001))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 600))

# Initialize Bielik client
bielik_client = BielikClient(base_url=BIELIK_APP_URL, timeout=REQUEST_TIMEOUT)

# Initialize TextAnalyzer (for smart context extraction)
text_analyzer = TextAnalyzer()

# ============== Register MCP Protocol Router ==============
mcp_router = create_mcp_router(bielik_client)
app.include_router(mcp_router)


# ============== Schemas ==============

class EnhancementItem(BaseModel):
    id: str
    text_with_gaps: str
    attributes: Optional[Dict[str, Any]] = None


class EnhancementOptions(BaseModel):
    language: str = "pl"
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_new_tokens: int = Field(default=200, ge=50, le=1000)
    top_n_per_gap: int = Field(default=1, ge=1, le=5)


class EnhancementRequest(BaseModel):
    domain: str = "cars"
    model: str = "bielik-1.5b-transformer"  # GPU-only models
    items: List[EnhancementItem]
    options: EnhancementOptions = Field(default_factory=EnhancementOptions)


class GapFill(BaseModel):
    index: int
    marker: str = ""
    choice: str
    alternatives: List[str] = []


class ProcessedItem(BaseModel):
    id: str
    status: str  # "ok", "warning", "error"
    filled_text: Optional[str] = None
    gaps: List[GapFill] = []
    error: Optional[str] = None


class EnhancementResponse(BaseModel):
    domain: str
    model: str
    items: List[ProcessedItem]
    processing_time_ms: float
    status: str  # "success", "partial", "error"


# ============== Endpoints ==============

@app.get("/")
async def root():
    return {
        "service": "MCP Service",
        "version": "3.0.0",
        "description": "Middleware for AI-powered gap filling",
        "bielik_url": BIELIK_APP_URL
    }


@app.get("/health")
async def health():
    """Health check - also verifies Bielik connectivity."""
    try:
        resp = requests.get(f"{BIELIK_APP_URL}/health", timeout=5)
        bielik_status = "ok" if resp.status_code == 200 else "degraded"
    except:
        bielik_status = "unreachable"
    
    return {
        "status": "ok",
        "bielik_status": bielik_status,
        "bielik_url": BIELIK_APP_URL
    }


FEW_SHOT_EXAMPLES = [
    {"role": "user", "content": "Tekst: Sprzedam samochód w bardzo dobrym stanie [LUKA].\n\nUzupełnij: [LUKA]"},
    {"role": "assistant", "content": "technicznym"},
    {"role": "user", "content": "Tekst: Do auta dodaję komplet opon [LUKA] na zmianę.\n\nUzupełnij: [LUKA]"},
    {"role": "assistant", "content": "zimowych"},
    {"role": "user", "content": "Tekst: Silnik pracuje równo, nie pobiera [LUKA].\n\nUzupełnij: [LUKA]"},
    {"role": "assistant", "content": "oleju"}
]

async def process_single_gap(client, model, prompt_text, gap, gap_marker, temperature, semaphore):
    """
    Helper function to process a single gap asynchronously but with concurrency control.
    """
    async with semaphore:
        try:
            # 1. System Prompt
            system_msg = (
                "Jesteś ekspertem redakcyjnym i korektorem tekstów motoryzacyjnych. "
                "Twoim zadaniem jest przywrócenie brakującego słowa w tekście. "
                "Zwróć TYLKO jedno słowo. Nie pisz całych zdań. "
                "Jesteś ekspertem redakcyjnym i korektorem tekstów motoryzacyjnych. "
                "Twoim zadaniem jest przywrócenie brakującego słowa w tekście. "
                "Zwróć TYLKO jedno słowo. Nie pisz całych zdań."
            )

            # 2. Extract context
            context_part = prompt_text.split("Tekst:\n", 1)[-1].split("\n\n")[0] if "Tekst:\n" in prompt_text else prompt_text

            # 3. Build Messages with Few-Shot
            messages = [{"role": "system", "content": system_msg}]
            messages.extend(FEW_SHOT_EXAMPLES)
            messages.append({
                "role": "user", 
                "content": f"Tekst: {context_part}\n\nUzupełnij: {gap_marker}"
            })

            # 4. Call Model (use request temperature)
            # print(f"MCP: Sending request for gap {gap.index}...") # Uncomment for debug
            raw_output = await client.chat(
                model=model,
                messages=messages,
                max_tokens=10, 
                temperature=temperature, 
                top_p=0.9
            )

            word = raw_output.strip().rstrip(".").rstrip(",").strip('"').strip("'")
            
            # Guardrail against placeholders
            if word.lower() in ["gap", "luka", "wypełnij", "brak", "słowo"]:
                print(f"MCP: Warning - Model returned placeholder '{word}' for gap {gap.index}")
                return gap.index, None
                
            return gap.index, word

        except Exception as e:
            print(f"MCP: Error processing gap {gap.index}: {e}")
            return gap.index, None

@app.post("/api/v1/enhance-description", response_model=EnhancementResponse)
async def enhance_description(body: EnhancementRequest):
    """
    Optimized endpoint with Semaphore Control (Safe for Local GPU/HF Spaces) and Few-Shot Prompting.
    """
    start_time = time.time()
    
    # ---- Konfiguracja Sprzętowa ----
    # Ustaw na 1 dla HF Spaces (działanie sekwencyjne - bezpieczne).
    # Ustaw na 2-4 jeśli masz mocne GPU (np. A100) i vLLM.
    MAX_CONCURRENT_REQUESTS = 1 
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    # ... (Step 1: Input Validation code remains same) ...
    validated_items = []
    for item in body.items:
        has_gaps = "[GAP:" in item.text_with_gaps or "___" in item.text_with_gaps
        validated_items.append(item)
    if not validated_items:
        return EnhancementResponse(domain=body.domain, model=body.model, items=[], processing_time_ms=0, status="success")

    # ---- Step 2: Process each item ----
    processed_items = []
    
    for item in validated_items:
        try:
            print(f"\nMCP: Processing item {item.id}...")
            
            # Step 2a: Detect gaps
            gaps = detect_gaps(item.text_with_gaps)
            if not gaps:
                processed_items.append(ProcessedItem(id=item.id, status="ok", filled_text=item.text_with_gaps, gaps=[], error=None))
                continue

            # Step 2b: Choose strategy
            strategy = choose_strategy(item.text_with_gaps, gaps) 
            
            alternatives = {}

            if strategy == "per_gap" or len(gaps) > 5:
                print(f"MCP: Processing {len(gaps)} gaps individually using SEMAPHORE (Limit={MAX_CONCURRENT_REQUESTS})")

                # Build individual prompts
                per_gap_prompts = build_per_gap_prompts(
                    item.text_with_gaps,
                    gaps,
                    item.attributes,
                    context_tokens=150
                )

                tasks = []
                for prompt_text, gap, gap_marker in per_gap_prompts:
                    tasks.append(
                        process_single_gap(
                            client=bielik_client,
                            model=body.model,
                            prompt_text=prompt_text,
                            gap=gap,
                            gap_marker=gap_marker,
                            temperature=body.options.temperature,
                            semaphore=semaphore 
                        )
                    )


                results = await asyncio.gather(*tasks)

                # Collect results
                for idx, word in results:
                    if word:
                        alternatives[idx] = word
                        print(f"MCP: Gap {idx}: {word}")

            else:
                print(f"MCP: Using batched strategy for {len(gaps)} gaps")

            # Step 2e: Reconstruct text
            filled_text = apply_fills(item.text_with_gaps, gaps, alternatives)

            # Mock output structure
            processed_items.append(ProcessedItem(
                id=item.id,
                status="ok",
                filled_text=filled_text,
                gaps=[GapFill(index=g.index, marker=g.marker, choice=alternatives.get(g.index, ""), alternatives=[]) for g in gaps],
                error=None
            ))

        except Exception as e:
            print(f"MCP: Error processing item {item.id}: {e}")
            processed_items.append(ProcessedItem(id=item.id, status="error", filled_text=None, gaps=[], error=str(e)))

    # ---- Step 3: Return Response ----
    processing_time_ms = (time.time() - start_time) * 1000
    
    return EnhancementResponse(
        domain=body.domain,
        model=body.model,
        items=processed_items,
        processing_time_ms=processing_time_ms,
        status="success"
    )


# ============== Additional Utility Endpoints ==============

@app.get("/models")
async def list_models():
    """Proxy to Bielik's model list."""
    try:
        resp = requests.get(f"{BIELIK_APP_URL}/models", timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e), "models": []}


@app.post("/api/v1/validate")
async def validate_only(body: EnhancementRequest):
    """
    Validate a request without processing.
    Useful for checking if gaps are properly formatted.
    """
    results = []
    for item in body.items:
        gap_count = item.text_with_gaps.count("[GAP:") + item.text_with_gaps.count("___")
        results.append({
            "id": item.id,
            "gap_count": gap_count,
            "has_gaps": gap_count > 0,
            "text_length": len(item.text_with_gaps)
        })
    
    return {
        "valid": all(r["has_gaps"] for r in results),
        "items": results
    }
