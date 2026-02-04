# mcp_service/app/logic/preprocessor.py

from pydantic import BaseModel
from typing import List
from .gap_extractor import extract_gaps, create_optimized_text

def optimize_item_text(text: str) -> str:
    """
    Optimizes text by extracting only relevant context around gaps.
    """
    gaps = extract_gaps(text, context_window=40)
    if not gaps:
        return text
    return create_optimized_text(gaps)

def preprocess_data(data: BaseModel, rules: dict) -> BaseModel:
    """
    Preprocesses the input data based on a set of rules.
    Optimizes text with gaps for efficient processing.
    """
    print("MCP: Running preprocessor...")
    
    # Check if this is an EnhancementRequestBody with items
    if hasattr(data, 'items') and isinstance(data.items, list):
        for item in data.items:
            if hasattr(item, 'text_with_gaps'):
                original_len = len(item.text_with_gaps)
                item.text_with_gaps = optimize_item_text(item.text_with_gaps)
                optimized_len = len(item.text_with_gaps)
                print(f"MCP: Optimized item {item.id}: {original_len} chars -> {optimized_len} chars")

    # Example of a generic rule: capitalize a field if it exists.
    if hasattr(data, 'make'):
        data.make = data.make.capitalize()
        print(f"Standardized make: {data.make}")
    
    return data
