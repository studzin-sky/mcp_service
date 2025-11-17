# mcp_service/app/logic/postprocessor.py

def format_output(description: str, rules: dict) -> str:
    """
    Formats the final output description based on a set of rules.
    """
    print("MCP: Running postprocessor...")
    
    formatted_description = description.strip()
    
    # Add a closing statement if defined in the rules
    closing_statement = rules.get("closing_statement")
    if closing_statement and not formatted_description.endswith(closing_statement):
        formatted_description = f"{formatted_description}\n\n{closing_statement}"
        
    print("Post-processing complete.")
    return formatted_description
