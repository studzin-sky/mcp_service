# mcp_service/app/logic/preprocessor.py

from pydantic import BaseModel

def preprocess_data(data: BaseModel, rules: dict) -> BaseModel:
    """
    Preprocesses the input data based on a set of rules.
    """
    print("MCP: Running preprocessor...")
    
    # Example of a generic rule: capitalize a field if it exists.
    # The field to capitalize would be defined in the domain's config.
    if hasattr(data, 'make'):
        data.make = data.make.capitalize()
        print(f"Standardized make: {data.make}")
    
    return data
