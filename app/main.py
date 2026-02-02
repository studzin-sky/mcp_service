"""
MCP Service - Model Context Protocol
=====================================
A lightweight middleware that:
1. Validates incoming requests
2. Forwards to Bielik App Service (bulk mode with GBNF grammar)
3. Applies guardrails to responses
4. Returns validated results

This is a passthrough service - Bielik does the heavy LLM work.
"""

import os
import time
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Import guardrails for post-processing validation
from logic import guardrails
from logic import polish_grammar

app = FastAPI(
    title="Model Context Protocol (MCP) Service",
    description="Middleware for AI model interactions with validation and guardrails.",
    version="3.0.0"
)

# Configuration
BIELIK_APP_URL = os.getenv("BIELIK_APP_URL", "http://bielik_app_service:8000")
MCP_PORT = int(os.getenv("MCP_PORT", 8001))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 600))  # 10 minutes for bulk requests (GPU may compile on first run)


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
    model: str = "bielik-1.5b-gguf"
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
    Main endpoint for gap-filling car advertisements.
    
    Flow:
    1. Validate input (check gaps exist, domain valid)
    2. Forward to Bielik in bulk mode (uses GBNF grammar for fast, structured output)
    3. Apply guardrails (validate fills are appropriate)
    4. Return processed results
    """
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"MCP: New request - {len(body.items)} items, model={body.model}")
    print(f"MCP: Bielik URL: {BIELIK_APP_URL}")
    
    # ---- Step 1: Input Validation ----
    validated_items = []
    for item in body.items:
        # Check if text has gaps
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
    
    # ---- Step 2: Forward to Bielik (Bulk Mode) ----
    bielik_payload = {
        "domain": body.domain,
        "model": body.model,
        "items": [
            {
                "id": item.id,
                "text_with_gaps": item.text_with_gaps,
                "attributes": item.attributes or {}
            }
            for item in validated_items
        ],
        "options": {
            "language": body.options.language,
            "temperature": body.options.temperature,
            "max_new_tokens": body.options.max_new_tokens,
            "top_n_per_gap": body.options.top_n_per_gap,
            "gap_notation": "auto"
        }
    }
    
    print(f"MCP: Sending bulk request to Bielik...")
    
    try:
        bielik_response = requests.post(
            f"{BIELIK_APP_URL}/infill",
            json=bielik_payload,
            timeout=REQUEST_TIMEOUT
        )
        
        if bielik_response.status_code != 200:
            print(f"MCP: Bielik error {bielik_response.status_code}: {bielik_response.text[:500]}")
            raise HTTPException(
                status_code=502,
                detail=f"Bielik service error: {bielik_response.status_code}"
            )
        
        bielik_data = bielik_response.json()
        print(f"MCP: Bielik returned {len(bielik_data.get('results', []))} results")
        
    except requests.exceptions.Timeout:
        print(f"MCP: Bielik request timed out after {REQUEST_TIMEOUT}s")
        raise HTTPException(status_code=504, detail="Bielik service timeout")
    except requests.exceptions.RequestException as e:
        print(f"MCP: Bielik connection error: {e}")
        raise HTTPException(status_code=503, detail=f"Cannot connect to Bielik: {e}")
    
    # ---- Step 3: Apply Guardrails ----
    processed_items = []
    guard = guardrails.Guardrails()
    
    # Map original texts for guardrail validation
    original_texts = {item.id: item.text_with_gaps for item in body.items}
    
    for result in bielik_data.get("results", []):
        item_id = result.get("id")
        status = result.get("status", "error")
        filled_text = result.get("filled_text")
        gaps = result.get("gaps", [])
        error = result.get("error")
        
        # ---- Step 2b: Apply Grammar Fix (New) ----
        if status == "ok" and gaps:
            original_text = original_texts.get(item_id, "")
            if original_text:
                try:
                    # Fix grammar based on context (inflection)
                    fixed_text, fixed_gaps = polish_grammar.fix_grammar_in_text(original_text, gaps)
                    
                    # Update if successful
                    filled_text = fixed_text
                    gaps = fixed_gaps
                    print(f"MCP: Grammar fix applied for item {item_id}")
                except Exception as e:
                    print(f"MCP: Grammar fix failed for item {item_id}: {e}")
        
        # Apply guardrails if we have a successful fill
        final_status = status
        if status == "ok" and filled_text:
            is_valid, report = guard.validate_all({
                "original_description": original_texts.get(item_id, ""),
                "enhanced_description": filled_text,
                "gaps": gaps,
                "alternatives": {}
            }, domain=body.domain)
            
            if not is_valid:
                final_status = "warning"
                print(f"MCP: Guardrails flagged item {item_id}: {report}")
        
        processed_items.append(ProcessedItem(
            id=item_id,
            status=final_status,
            filled_text=filled_text,
            gaps=[GapFill(**g) if isinstance(g, dict) else g for g in gaps],
            error=error
        ))
    
    # ---- Step 4: Return Response ----
    processing_time_ms = (time.time() - start_time) * 1000
    
    # Determine overall status
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
