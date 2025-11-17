import time
import requests
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, ValidationError

# Corrected: Direct imports from modules in the same directory
from logic import preprocessor, guardrails, postprocessor
from schemas import EnhancementRequestBody, EnhancedDescriptionResponse

app = FastAPI(
    title="Model Context Protocol (MCP) Service",
    description="A central service to manage AI model interactions, including pre-processing, guardrails, and post-processing.",
    version="1.0.0"
)

# Configuration
BIELIK_APP_URL = "http://bielik_app_service:8000" # This will be the internal docker network address

@app.get("/")
async def read_root():
    return {"message": "Welcome to the MCP Service. This service acts as a middleman for AI model interactions."}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/v1/enhance-description", response_model=EnhancedDescriptionResponse)
async def enhance_description(body: EnhancementRequestBody):
    """
    This endpoint orchestrates the enhancement of a description by applying MCP rules.
    """
    start_time = time.time()
    
    # For now, we pass a generic Pydantic model.
    # In a real scenario, this would dynamically load the domain-specific schema.
    class GenericDomainSchema(BaseModel):
        make: str
        model: str
        # Add other potential fields with default None
        year: int | None = None
        mileage: int | None = None
        features: list | None = []
        condition: str | None = None


    # --- 1. Validate Input Data ---
    try:
        validated_data = GenericDomainSchema(**body.data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Invalid data for domain '{body.domain}': {e}")

    # --- 2. MCP Pre-processing ---
    processed_data = preprocessor.preprocess_data(validated_data, body.mcp_rules.get("preprocessor", {}))

    # --- 3. Prompt Construction (will be part of the call to bielik) ---
    # This part is simplified. The actual prompt creation logic remains in bielik_app for now.
    chat_messages = f"Create a description for: {processed_data.model_dump_json()}"


    # --- 4. Text Generation (Call to Bielik App Service) ---
    try:
        # Actual HTTP call to bielik_app_service
        http_response = requests.post(
            f"{BIELIK_APP_URL}/generate",
            json={"chat_template_messages": chat_messages}
        )
        http_response.raise_for_status() # Raise an exception for HTTP errors
        generated_description = http_response.json()["generated_text"]
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Could not connect to the text generation service: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during text generation: {str(e)}")

    # --- 5. MCP Guardrails & Post-processing ---
    if not guardrails.check_compliance(generated_description, body.mcp_rules.get("guardrails", {})):
        raise HTTPException(status_code=400, detail="Generated description failed compliance checks.")

    final_description = postprocessor.format_output(generated_description, body.mcp_rules.get("postprocessor", {}))
    
    generation_time = time.time() - start_time

    return EnhancedDescriptionResponse(
        description=final_description,
        model_used="speakleash/Bielik-1.5B-v3.0-Instruct", # Now using the actual model name
        generation_time=round(generation_time, 2)
    )