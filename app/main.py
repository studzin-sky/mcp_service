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
        # 1. Store original texts for reconstruction later
        original_texts = {item.id: item.text_with_gaps for item in body.items}
        
        # 2. Preprocess: Optimize text (reduce to contexts)
        # This modifies 'body' in place or returns modified object
        # We need to be careful with Pydantic models. 
        # model_dump() creates a dict, let's work with that or modify body items directly.
        # preprocessor.preprocess_data modifies the Pydantic model in place if it can, or returns it.
        processed_body = preprocessor.preprocess_data(body, {})
        
        # Forward the request to Bielik infill endpoint with OPTIMIZED texts
        http_response = requests.post(
            f"{BIELIK_APP_URL}/infill",
            json=processed_body.model_dump()
        )
        http_response.raise_for_status()
        bielik_response = http_response.json()
        
        # Extract results from Bielik response
        bielik_results = bielik_response.get("results", [])
        
        # Apply MCP post-processing if needed
        processed_items = []
        for result in bielik_results:
            item_id = result.get("id")
            original_text = original_texts.get(item_id, "")
            
            # Extract the gaps choices
            gaps_data = result.get("gaps", [])
            fills = {}
            for g in gaps_data:
                # Bielik returns 'index' and 'choice'
                if 'index' in g and 'choice' in g:
                    fills[g['index']] = g['choice']
            
            # 3. Reconstruct the FULL text using original text + fills
            # We ignore result['filled_text'] because it's based on the optimized (short) text
            reconstructed_text = postprocessor.apply_fills(original_text, fills)
            
            # Apply additional post-processing (formatting)
            final_text = postprocessor.format_output(reconstructed_text, {})
            
            # Return the full result with processed text
            processed_result = {
                "id": item_id,
                "status": result.get("status"),
                "filled_text": final_text,
                "gaps": gaps_data
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