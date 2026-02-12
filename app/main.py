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


@app.post("/api/v1/enhance-description", response_model=EnhancementResponse)
async def enhance_description(body: EnhancementRequest):
    """
    Main endpoint for gap-filling car advertisements using Bielik GPU inference.
    
    New Flow (Phase 2):
    1. Validate input (gaps exist, domain valid)
    2. Detect gaps locally
    3. For each item: build prompt → call Bielik /generate → parse response
    4. Reconstruct text with filled gaps
    5. Apply guardrails (already in MCP)
    6. Return processed results
    """
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"MCP: New request - {len(body.items)} items, model={body.model}")
    print(f"MCP: Bielik URL: {BIELIK_APP_URL}")
    
    # ---- Step 1: Input Validation ----
    validated_items = []
    for item in body.items:
        has_gaps = "[GAP:" in item.text_with_gaps or "___" in item.text_with_gaps
        if not has_gaps:
            print(f"MCP: Warning - Item {item.id} has no gaps, will pass through unchanged")
        validated_items.append(item)
    
    if not validated_items:
        return EnhancementResponse(
            domain=body.domain,
            model=body.model,
            items=[],
            processing_time_ms=0,
            status="success"
        )
    
    # ---- Step 2: Process each item ----
    processed_items = []
    guard = guardrails.Guardrails()
    original_texts = {item.id: item.text_with_gaps for item in body.items}
    
    for item in validated_items:
        try:
            print(f"\nMCP: Processing item {item.id}...")
            
            # Step 2a: Detect gaps
            gaps = detect_gaps(item.text_with_gaps)
            if not gaps:
                print(f"MCP: No gaps found in item {item.id}")
                processed_items.append(ProcessedItem(
                    id=item.id,
                    status="ok",
                    filled_text=item.text_with_gaps,
                    gaps=[],
                    error=None
                ))
                continue
            
            print(f"MCP: Detected {len(gaps)} gaps in item {item.id}")

            # Step 2b: Choose strategy based on gap count
            strategy = choose_strategy(item.text_with_gaps, gaps)
            print(f"MCP: Using strategy: {strategy} for {len(gaps)} gaps")

            alternatives = {}

            if strategy == "per_gap" or len(gaps) > 5:
                # Per-gap strategy: process each gap individually
                print(f"MCP: Processing gaps individually (prevents word copying)")

                # Build individual prompts for each gap
                per_gap_prompts = build_per_gap_prompts(
                    item.text_with_gaps,
                    gaps,
                    item.attributes,
                    context_tokens=150
                )

                # Process each gap
                for prompt_text, gap, gap_marker in per_gap_prompts:
                    # Update the prompt to prevent copying
                    system_msg = (
                        "Jesteś asystentem sprzedaży samochodów. "
                        f"Twoim zadaniem jest uzupełnić lukę {gap_marker} w podanym tekście. "
                        "WYGENERUJ JEDNO nowe słowo (przymiotnik lub rzeczownik) pasujące do kontekstu. "
                        "NIE kopiuj żadnych słów które widzisz w tekście - wymyśl nowe odpowiednie słowo. "
                        "Odpowiedź: tylko jedno nowe słowo, bez wyjaśnień."
                    )

                    # Extract context from prompt
                    context_part = prompt_text.split("Tekst:\n", 1)[-1].split("\n\n")[0] if "Tekst:\n" in prompt_text else prompt_text

                    messages = [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": f"Tekst:\n{context_part}\n\nWypełnij lukę {gap_marker} - podaj jedno NOWE słowo:"}
                    ]

                    # Call Bielik for this gap only
                    raw_output = await bielik_client.chat(
                        model=body.model,
                        messages=messages,
                        max_tokens=20,  # Only need one word
                        temperature=body.options.temperature,
                        top_p=0.9
                    )

                    # Extract the single word (clean it up)
                    word = raw_output.strip().split()[0] if raw_output.strip() else ""
                    # Remove punctuation and numbers
                    word = ''.join(c for c in word if c.isalpha())

                    if word:
                        alternatives[gap.index] = word
                        print(f"MCP: Gap {gap.index}: {word}")

            else:
                # Batched strategy: process all gaps at once (for <=5 gaps)
                print(f"MCP: Using batched strategy for {len(gaps)} gaps")

                # ============ NEW: Use TextAnalyzer for smart context ============
                analysis = text_analyzer.analyze(item.text_with_gaps)
                print(f"MCP: Ad type detected: {analysis.ad_type.value}")
                print(f"MCP: Keywords: {', '.join(analysis.keywords[:5])}")

                # Build adaptive prompt using TextAnalyzer
                messages = text_analyzer.build_adaptive_prompt(analysis, item.text_with_gaps)
                # ================================================================

                # tokens needed: ~5 tokens per gap response + buffer
                tokens_needed = len(gaps) * 5 + 50
                max_tokens = min(max(tokens_needed, 200), 1000)

                print(f"MCP: Calling Bielik /chat for batch processing...")
                raw_output = await bielik_client.chat(
                    model=body.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=body.options.temperature,
                    top_p=0.9
                )
                print(f"DEBUG: BIELIK OUTPUT:\n{raw_output}\n")

                # Parse response
                parsed = parse_infill_response(raw_output)
                if not parsed or "gaps" not in parsed:
                    raise Exception("Failed to parse Bielik response")

                # Extract alternatives
                for gap_entry in parsed.get("gaps", []):
                    idx = gap_entry.get("index")
                    choice = gap_entry.get("choice")
                    if idx and choice:
                        alternatives[idx] = choice

            print(f"MCP: Collected {len(alternatives)} alternatives for {len(gaps)} gaps")
            
            # Step 2e: Reconstruct text
            filled_text = apply_fills(item.text_with_gaps, gaps, alternatives)
            print(f"DEBUG: FINAL FILLED TEXT:\n{filled_text}\n")
            print(f"MCP: Reconstructed text for item {item.id}")
            
            # Step 2f: Apply grammar fix (optional, requires spacy)
            final_status = "ok"
            if polish_grammar:
                try:
                    fixed_text, fixed_gaps = polish_grammar.fix_grammar_in_text(
                        item.text_with_gaps,
                        [{"index": g.index, "choice": alternatives.get(g.index)} for g in gaps]
                    )
                    filled_text = fixed_text
                    print(f"MCP: Grammar fix applied for item {item.id}")
                except Exception as e:
                    print(f"MCP: Grammar fix failed for item {item.id}: {e}")
            else:
                print(f"MCP: Skipping grammar fix (spacy not installed)")
            
            
            # Step 2g: Apply guardrails
            if filled_text:
                is_valid, report = guard.validate_all({
                    "original_description": item.text_with_gaps,
                    "enhanced_description": filled_text,
                    "gaps": [{"index": g.index, "marker": g.marker} for g in gaps],
                    "alternatives": alternatives
                }, domain=body.domain)
                
                if not is_valid:
                    final_status = "warning"
                    print(f"MCP: Guardrails flagged item {item.id}: {report}")
            
            # Build response item
            gap_fills = []
            for gap in gaps:
                gap_fills.append(GapFill(
                    index=gap.index,
                    marker=gap.marker,
                    choice=alternatives.get(gap.index, ""),
                    alternatives=[]
                ))
            
            processed_items.append(ProcessedItem(
                id=item.id,
                status=final_status,
                filled_text=filled_text,
                gaps=gap_fills,
                error=None
            ))
            
        except Exception as e:
            print(f"MCP: Error processing item {item.id}: {e}")
            processed_items.append(ProcessedItem(
                id=item.id,
                status="error",
                filled_text=None,
                gaps=[],
                error=str(e)
            ))
    
    # ---- Step 3: Return Response ----
    processing_time_ms = (time.time() - start_time) * 1000
    
    error_count = sum(1 for item in processed_items if item.status == "error")
    if error_count == len(processed_items):
        overall_status = "error"
    elif error_count > 0:
        overall_status = "partial"
    else:
        overall_status = "success"
    
    print(f"MCP: Completed in {processing_time_ms:.0f}ms - {overall_status}")
    print(f"{'='*60}\n")
    
    return EnhancementResponse(
        domain=body.domain,
        model=body.model,
        items=processed_items,
        processing_time_ms=processing_time_ms,
        status=overall_status
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
