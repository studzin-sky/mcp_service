from app.domains.cars.schemas import CarData
from app.domains.cars.prompts import create_prompt, create_infill_prompt

# Domain-specific configuration for 'cars'
domain_config = {
    "schema": CarData,
    "create_prompt": create_prompt,
    "create_infill_prompt": create_infill_prompt,
    "mcp_rules": {
        "preprocessor": {
            # Add any car-specific preprocessing rules here
        },
        "guardrails": {
            "prohibited_words": ["gwarantowane"],
            "max_length": 600
        },
        "postprocessor": {
            "closing_statement": "Zapraszamy do kontaktu!"
        }
    }
}
