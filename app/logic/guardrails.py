# mcp_service/app/logic/guardrails.py

def check_compliance(description: str, rules: dict) -> bool:
    """
    Checks if the generated description meets business and quality standards
    defined in the rules.
    """
    print("MCP: Running guardrails...")
    
    # Check for prohibited words
    prohibited_words = rules.get("prohibited_words", [])
    for word in prohibited_words:
        if word in description.lower():
            print(f"Guardrail FAIL: Found prohibited word '{word}'.")
            return False
            
    # Check for length
    max_length = rules.get("max_length")
    if max_length and len(description) > max_length:
        print(f"Guardrail FAIL: Description is too long ({len(description)} characters). Max is {max_length}.")
        return False

    print("Guardrails PASSED.")
    return True
