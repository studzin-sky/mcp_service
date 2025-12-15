"""
MCP Service - Model Context Protocol middleware

Orchestrates preprocessing, guardrails, and postprocessing for text enhancement.
Acts as central hub between bielik_app_service and clients.

Flow:
1. Client sends description with gaps [GAP:n]
2. Preprocessor extracts gap context, normalizes text
3. Guardrails validates input structure
4. Bielik model generates filled text
5. Postprocessor fixes JSON, extracts alternatives
6. Guardrails validates output quality
7. Response with enhanced text, gaps, alternatives
"""

import time
import requests
import json
import logging
from fastapi import FastAPI, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import Dict, Any, List

from logic.preprocessor import TextPreprocessor, preprocess_data
from logic.guardrails import Guardrails, ValidationLevel, create_validation_report
from logic.postprocessor import PostProcessor, create_final_output
from logic.polish_grammar import fix_grammar_in_text
from schemas import EnhancementRequestBody, EnhancedDescriptionResponse

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Model Context Protocol (MCP) Service",
    description="Central preprocessing, guardrails, and postprocessing service for text enhancement",
    version="2.0.0"
)

# Configuration
BIELIK_APP_URL = "http://localhost:8001"  # Local for testing, will be docker service name in production
BIELIK_ENDPOINT = "/infill"

# Initialize components
preprocessor = TextPreprocessor("cars")
guardrails = Guardrails(ValidationLevel.NORMAL)
postprocessor = PostProcessor()


@app.get("/")
async def read_root():
    """Service health and info endpoint"""
    return {
        "service": "MCP (Model Context Protocol)",
        "version": "2.0.0",
        "status": "ready",
        "endpoints": {
            "health": "/health",
            "enhance": "/api/v1/enhance-description",
            "batch_enhance": "/api/v1/batch-enhance"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "MCP"
    }


@app.post("/api/v1/enhance-description", response_model=EnhancedDescriptionResponse)
async def enhance_description(body: EnhancementRequestBody):
    """
    Main enhancement endpoint.
    
    Flow:
    1. Preprocess: Normalize, extract gaps, prepare context
    2. Call Bielik: Send to model for gap-filling
    3. Postprocess: Parse JSON, fix formatting
    4. Grammar: Apply Polish case corrections
    5. Guardrails: Validate output quality
    
    Returns:
        Enhanced description with gaps, alternatives, metadata
    """
    start_time = time.time()
    
    try:
        # Step 1: Preprocess
        logger.info(f"[MCP] Preprocessing domain={body.domain}")
        
        preprocessed = preprocess_data(
            {
                "description": body.data.get("description", ""),
                "metadata": body.data.get("metadata", {})
            },
            domain=body.domain
        )
        
        normalized_text = preprocessed["normalized_description"]
        gaps_info = preprocessed["gaps"]
        model_context = preprocessed["model_context"]
        
        logger.info(f"[MCP] Found {len(gaps_info)} gaps")
        
        # Step 2: Call Bielik service
        logger.info(f"[MCP] Calling Bielik service for text generation")
        
        bielik_request = {
            "description": normalized_text,
            "domain": body.domain,
            "model": body.model if hasattr(body, 'model') else "bielik",
            "compare": False
        }
        
        try:
            response = requests.post(
                f"{BIELIK_APP_URL}{BIELIK_ENDPOINT}",
                json=bielik_request,
                timeout=60
            )
            response.raise_for_status()
            bielik_result = response.json()
            generated = bielik_result.get("result", "")
            
            logger.info(f"[MCP] Bielik returned {len(generated)} chars")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"[MCP] Bielik service error: {e}")
            raise HTTPException(status_code=503, detail=f"Text generation service unavailable: {str(e)}")
        
        # Step 3: Postprocess
        logger.info(f"[MCP] Postprocessing output")
        
        postprocessed = postprocessor.process(
            raw_output=generated,
            original_description=normalized_text,
            gaps_info=gaps_info
        )
        
        enhanced_text = postprocessed.get("enhanced_description", "")
        gaps_filled = postprocessed.get("gaps", [])
        alternatives = postprocessed.get("alternatives", {})
        
        # Step 4: Grammar fixes (Polish)
        logger.info(f"[MCP] Applying Polish grammar corrections")
        
        corrected_text, grammar_suggestions = fix_grammar_in_text(enhanced_text, gaps_filled)
        
        logger.info(f"[MCP] Applied {len(grammar_suggestions)} grammar fixes")
        
        # Step 5: Guardrails validation
        logger.info(f"[MCP] Running validation guardrails")
        
        validation_data = {
            "original_description": normalized_text,
            "enhanced_description": corrected_text,
            "gaps": gaps_filled,
            "alternatives": alternatives,
            "domain": body.domain
        }
        
        is_valid, validation_report = guardrails.validate_all(validation_data, body.domain)
        
        if not is_valid and guardrails.level == ValidationLevel.STRICT:
            logger.warning(f"[MCP] Validation failed: {validation_report['errors']}")
            raise HTTPException(status_code=422, detail=f"Output validation failed: {validation_report['errors']}")
        
        if validation_report.get("warnings"):
            logger.info(f"[MCP] Validation warnings: {validation_report['warnings']}")
        
        # Build response
        generation_time = time.time() - start_time
        
        logger.info(f"[MCP] Complete in {generation_time:.2f}s")
        
        return EnhancedDescriptionResponse(
            description=corrected_text,
            original=normalized_text,
            gaps=gaps_filled,
            alternatives=alternatives,
            model_used=body.model if hasattr(body, 'model') else "bielik-1.5b",
            generation_time=round(generation_time, 2),
            validation={
                "valid": is_valid,
                "errors": validation_report.get("errors", []),
                "warnings": validation_report.get("warnings", [])
            },
            grammar_suggestions=grammar_suggestions
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MCP] Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Enhancement failed: {str(e)}")


@app.post("/api/v1/batch-enhance")
async def batch_enhance(batch_data: Dict[str, Any]):
    """
    Batch enhancement endpoint for multiple descriptions.
    
    Request:
    {
        "items": [
            {
                "id": "1",
                "description": "Fiat 500...",
                "metadata": {...}
            }
        ],
        "domain": "cars",
        "model": "bielik",
        "parallel": false
    }
    """
    items = batch_data.get("items", [])
    domain = batch_data.get("domain", "cars")
    model = batch_data.get("model", "bielik")
    
    logger.info(f"[MCP] Batch enhancement: {len(items)} items")
    
    results = []
    for item in items:
        try:
            request_body = EnhancementRequestBody(
                domain=domain,
                data={"description": item.get("description", ""), "metadata": item.get("metadata", {})},
                model=model,
                mcp_rules=batch_data.get("mcp_rules", {})
            )
            
            response = await enhance_description(request_body)
            results.append({
                "id": item.get("id"),
                "status": "success",
                "data": response.model_dump()
            })
        except Exception as e:
            results.append({
                "id": item.get("id"),
                "status": "failed",
                "error": str(e)
            })
    
    return {"batch_id": batch_data.get("batch_id"), "results": results}


@app.post("/api/v1/validate")
async def validate_enhancement(data: Dict[str, Any]):
    """
    Validate enhancement data without running full enhancement.
    """
    validation_report = create_validation_report(
        original=data.get("original_description", ""),
        enhanced=data.get("enhanced_description", ""),
        gaps=data.get("gaps", []),
        alternatives=data.get("alternatives", {}),
        domain=data.get("domain", "cars")
    )
    
    return validation_report


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
