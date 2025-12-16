import os
import time
import requests
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# Load environment variables from .env.local for development
load_dotenv(".env.local")

# Corrected: Import from local logic module
from .logic import preprocessor, guardrails, postprocessor
from .logic.gap_extractor import extract_gaps, build_multi_gap_prompt
from .schemas import EnhancementRequestBody, EnhancedDescriptionResponse

app = FastAPI(
    title="Model Context Protocol (MCP) Service",
    description="A central service to manage AI model interactions, including pre-processing, guardrails, and post-processing.",
    version="1.0.0"
)

# Configuration - supports both Docker and local development
BIELIK_APP_URL = os.getenv("BIELIK_APP_URL", "http://bielik_app_service:8000")
MCP_PORT = int(os.getenv("MCP_PORT", 8001))
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")

@app.get("/")
async def read_root():
    return {"message": "Welcome to the MCP Service. This service acts as a middleman for AI model interactions."}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/v1/enhance-description", response_model=EnhancedDescriptionResponse)
async def enhance_description(body: EnhancementRequestBody):
    """
    This endpoint orchestrates the gap-filling by:
    1. Extracting gap context from the text
    2. Forwarding to Bielik infill endpoint
    3. Applying MCP post-processing
    """
    start_time = time.time()
    
    try:
        # Extract gaps and their context for analysis
        gaps_list = []
        for item in body.items:
            text = item.text_with_gaps
            gaps = extract_gaps(text, context_window=35)
            gaps_list.extend(gaps)
            print(f"MCP: Extracted {len(gaps)} gaps from item {item.id}")
            for gap in gaps:
                print(f"  GAP:{gap.index}: '{gap.context}'")
        
        # Forward the request to Bielik infill endpoint
        http_response = requests.post(
            f"{BIELIK_APP_URL}/infill",
            json=body.model_dump()
        )
        http_response.raise_for_status()
        bielik_response = http_response.json()
        
        # Extract results from Bielik response
        bielik_results = bielik_response.get("results", [])
        
        # Apply MCP post-processing if needed
        processed_items = []
        for result in bielik_results:
            # Extract the filled text and post-process it
            filled_text = result.get("filled_text", "")
            processed_text = postprocessor.format_output(filled_text, {})
            
            # Return the full result with processed text
            processed_result = {
                "id": result.get("id"),
                "status": result.get("status"),
                "filled_text": processed_text,
                "gaps": result.get("gaps", [])
            }
            processed_items.append(processed_result)
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        return EnhancedDescriptionResponse(
            domain=body.domain,
            model=body.model,
            items=processed_items,
            processing_time_ms=processing_time_ms,
            status="success"
        )
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Could not connect to Bielik service: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")