"""
MCP Service - Model Context Protocol
=====================================
Gateway service that:
1. Validates incoming requests
2. Detects gaps in text locally
3. Builds domain-specific prompts
4. Calls Bielik /generate for inference (pure GPU)
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
from app.domains.cars.prompts import create_infill_prompt
from app.logic import guardrails

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
            
            # Step 2b: Build domain-specific prompt
            prompt = create_infill_prompt(
                text_with_gaps=item.text_with_gaps,
                gaps=gaps,
                attributes=item.attributes
            )
            print(f"MCP: Built prompt for item {item.id}")
            
            # Step 2c: Call Bielik /generate
            print(f"MCP: Calling Bielik /generate for item {item.id}...")
            raw_output = await bielik_client.generate(
                model=body.model,
                prompt=prompt,
                max_tokens=body.options.max_new_tokens,
                temperature=body.options.temperature,
                top_p=0.9
            )
            print(f"MCP: Bielik returned {len(raw_output)} chars for item {item.id}")
            print(f"MCP: Raw output: {raw_output[:200]}...")
            
            # Step 2d: Parse response
            parsed = parse_infill_response(raw_output)
            if not parsed or "gaps" not in parsed:
                print(f"MCP: Failed to parse response for item {item.id}")
                raise Exception("Failed to parse Bielik response")
            
            # Extract alternatives from parsed response
            alternatives = {}
            for gap_entry in parsed.get("gaps", []):
                idx = gap_entry.get("index")
                choice = gap_entry.get("choice")
                if idx and choice:
                    alternatives[idx] = choice
            
            print(f"MCP: Parsed {len(alternatives)} alternatives for item {item.id}")
            
            # Step 2e: Reconstruct text
            filled_text = apply_fills(item.text_with_gaps, gaps, alternatives)
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
                    "gaps": gaps,
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
