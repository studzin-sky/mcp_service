import os
import time
import requests
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# Load environment variables from .env.local for development
load_dotenv(".env.local")

# Corrected: Import from local logic module
from logic import preprocessor, guardrails, postprocessor
from logic.gap_extractor import extract_gaps, build_multi_gap_prompt
from schemas import EnhancementRequestBody, EnhancedDescriptionResponse

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
        # We split the request into individual items to ensure atomic processing and avoid timeouts
        bielik_results = []
        
        # processed_body is a Pydantic model (EnhancementRequestBody)
        base_request_dict = processed_body.model_dump()
        items_list = processed_body.items # List of InfillItem objects
        
        for item in items_list:
            # RAG Enhancement
            try:
                # Use text_with_gaps as query
                rag_query = item.text_with_gaps[:200]
                rag_service_url = os.getenv("RAG_SERVICE_URL", "http://localhost:8002")
                
                # print(f"MCP: Querying RAG for item {item.id}...")
                rag_response = requests.post(
                    f"{rag_service_url}/search",
                    json={
                        "domain": body.domain,
                        "query": rag_query,
                        "n_results": 1
                    },
                    timeout=2
                )
                if rag_response.status_code == 200:
                    rag_data = rag_response.json()
                    docs = rag_data.get("documents", [])
                    if docs and docs[0]:
                         # Limit context size for CPU-bound Bielik
                         context_text = "\n".join(docs[0])[:500]
                         if item.attributes is None:
                             item.attributes = {}
                         item.attributes["RAG_Knowledge"] = context_text
                         print(f"MCP: Added RAG context to item {item.id} (len={len(context_text)})")
            except Exception as e:
                # Silently fail RAG to not block main flow, but log it
                print(f"MCP: RAG search failed: {e}")

            # 2.5 Construct Custom Prompt (MCP Logic)
            system_prompt = (
                "Jesteś ekspertem motoryzacyjnym i copywriterem. "
                "Uzupełnij luki [GAP:n] w tekście. Wybierz pasujące, atrakcyjne słowa. "
                "Zwróć tylko numerowaną listę samych uzupełnień. "
                "Nie powtarzaj znaczników [GAP:n]."
            )
            
            context_str = ""
            rag_knowledge = item.attributes.get("RAG_Knowledge") if item.attributes else None
            if rag_knowledge:
                context_str = f"Wiedza pomocnicza:\n{rag_knowledge}\n\n"
            
            user_prompt = f"{context_str}Tekst ogłoszenia:\n{item.text_with_gaps}\n\nUzupełnienia (lista numerowana):"
            
            item.custom_messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            # Create a single-item request payload
            # We copy the base request structure but replace 'items' with just the current item
            single_item_payload = base_request_dict.copy()
            single_item_payload["items"] = [item.model_dump()]
            
            print(f"MCP: Sending item {item.id} to Bielik...")
            
            # Send single item request
            http_response = requests.post(
                f"{BIELIK_APP_URL}/infill",
                json=single_item_payload
            )
            http_response.raise_for_status()
            response_data = http_response.json()
            
            # Aggregate results
            if "results" in response_data:
                bielik_results.extend(response_data["results"])

        # Original bulk logic removed in favor of loop above
        
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
            
            # Reconstruct the FULL text using original text + fills
            # We ignore result['filled_text'] because it's based on the optimized (short) text
            reconstructed_text = postprocessor.apply_fills(original_text, fills)
            
            # Apply additional post-processing (formatting)
            final_text = postprocessor.format_output(reconstructed_text, {})
            
            # 4. Guardrails: Validate the result
            guard = guardrails.Guardrails()
            # Simple validation for now - check if gaps are still there
            is_valid, report = guard.validate_all({
                "original_description": original_text,
                "enhanced_description": final_text,
                "gaps": gaps_data,
                "alternatives": {}
            }, domain=body.domain)
            
            status = "ok" if is_valid else "warning"
            
            # Return the full result with processed text
            processed_result = {
                "id": item_id,
                "status": status,
                "filled_text": final_text,
                "gaps": gaps_data
            }
            if not is_valid:
                print(f"MCP: Guardrails found issues with item {item_id}: {report['errors']}")
            
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