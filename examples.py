#!/usr/bin/env python3
"""
MCP Service - Quick Start Examples

Shows how to use each component of the MCP service.
"""

import json
from logic.preprocessor import TextPreprocessor, preprocess_data
from logic.guardrails import Guardrails, ValidationLevel
from logic.postprocessor import PostProcessor, create_final_output
from logic.polish_grammar import convert_to_case, fix_grammar_in_text, analyze_gap_context


def example_1_preprocessing():
    """Example 1: Text preprocessing and gap extraction"""
    print("\n" + "="*60)
    print("EXAMPLE 1: Preprocessing")
    print("="*60)
    
    preprocessor = TextPreprocessor("cars")
    
    text = "Fiat 500 [GAP:1] z [GAP:2] silnikiem, [GAP:3] przebieg, w [GAP:4] stanie"
    print(f"\nOriginal text:\n{text}")
    
    normalized, gaps_info = preprocessor.preprocess(text)
    
    print(f"\nNormalized text:\n{normalized}")
    print(f"\nExtracted gaps ({len(gaps_info)}):")
    for gap in gaps_info:
        print(f"  Gap {gap['index']}: position={gap['position']}, case={gap['required_case']}")
        print(f"    context_before: '{gap['context_before']}'")
        print(f"    context_after: '{gap['context_after']}'")
        if gap['metadata']:
            print(f"    metadata: {gap['metadata']}")


def example_2_polish_grammar():
    """Example 2: Polish grammar case conversion"""
    print("\n" + "="*60)
    print("EXAMPLE 2: Polish Grammar - Case Conversion")
    print("="*60)
    
    # Example 1: Simple case conversion
    print("\nCase Conversions:")
    
    cases = ["nominative", "genitive", "dative", "accusative", "instrumental", "locative", "vocative"]
    
    for case in cases:
        result = convert_to_case("biały", case)
        print(f"  biały ({case}): {result}")
    
    # Example 2: Color in context
    print("\n\nColor in different contexts:")
    contexts = [
        ("Samochód w [GAP:1] kolorze", "locative", "białym"),  # w = locative
        ("Samochód [GAP:1]", "nominative", "biały"),           # direct
        ("Kolor [GAP:1]", "nominative", "biały"),              # direct
    ]
    
    for context, case, expected in contexts:
        print(f"  Context: '{context}'")
        print(f"  Expected case: {case}")
        print(f"  Converted: {convert_to_case('biały', case)}")
    
    # Example 3: Grammar fixing
    print("\n\nGrammar Fixing:")
    
    text = "Samochód biały z benzynowy silnikiem w szary kolorze"
    gaps_info = [
        {"index": 1, "choice": "biały", "case": "nominative"},
        {"index": 2, "choice": "benzynowy", "case": "instrumental"},
        {"index": 3, "choice": "szary", "case": "locative"}
    ]
    
    print(f"Before: {text}")
    corrected, suggestions = fix_grammar_in_text(text, gaps_info)
    print(f"After: {corrected}")
    
    if suggestions:
        print(f"\nSuggestions ({len(suggestions)}):")
        for s in suggestions:
            print(f"  Gap {s['gap_index']}: '{s['original']}' → '{s['corrected']}' ({s['case']})")


def example_3_guardrails():
    """Example 3: Validation guardrails"""
    print("\n" + "="*60)
    print("EXAMPLE 3: Validation Guardrails")
    print("="*60)
    
    guardrails = Guardrails(ValidationLevel.NORMAL)
    
    # Test data
    data = {
        "original_description": "Fiat 500 [GAP:1] z [GAP:2] silnikiem",
        "enhanced_description": "Fiat 500 biały z benzynowym silnikiem",
        "gaps": [
            {"index": 1, "choice": "biały"},
            {"index": 2, "choice": "benzynowy"}
        ],
        "alternatives": {
            1: ["biały", "czarny"],
            2: ["benzynowy", "dieselowy"]
        },
        "domain": "cars"
    }
    
    print("\nValidating enhancement data:")
    is_valid, report = guardrails.validate_all(data, "cars")
    
    print(f"Valid: {is_valid}")
    if report['errors']:
        print(f"Errors ({len(report['errors'])}):")
        for e in report['errors']:
            print(f"  - {e}")
    if report['warnings']:
        print(f"Warnings ({len(report['warnings'])}):")
        for w in report['warnings']:
            print(f"  - {w}")
    
    # Test with bad data
    print("\n\nValidating bad data (with unfilled gaps):")
    bad_data = data.copy()
    bad_data['enhanced_description'] = "Fiat 500 [GAP:1] z benzynowym silnikiem [GAP:2]"
    
    is_valid, report = guardrails.validate_all(bad_data, "cars")
    print(f"Valid: {is_valid}")
    if report['errors']:
        print(f"Errors:")
        for e in report['errors']:
            print(f"  - {e}")


def example_4_postprocessing():
    """Example 4: Postprocessing raw output"""
    print("\n" + "="*60)
    print("EXAMPLE 4: Postprocessing")
    print("="*60)
    
    postprocessor = PostProcessor()
    
    # Simulate raw model output (messy JSON)
    raw_output = '''{
      "enhanced_description": "Fiat 500  biały  z  benzynowym  silnikiem",
      "gaps": [{"index": 1, "choice": "biały"}, {"index": 2, "choice": "benzynowy"}],
      "alternatives": {}
    }'''
    
    print(f"Raw output:\n{raw_output}")
    
    original = "Fiat 500 [GAP:1] z [GAP:2] silnikiem"
    gaps_info = [
        {"index": 1, "choice": "biały", "case": "nominative"},
        {"index": 2, "choice": "benzynowy", "case": "instrumental"}
    ]
    
    result = postprocessor.process(raw_output, original, gaps_info)
    
    print(f"\nProcessed output:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


def example_5_full_pipeline():
    """Example 5: Full enhancement pipeline"""
    print("\n" + "="*60)
    print("EXAMPLE 5: Full Pipeline")
    print("="*60)
    
    # Step 1: Preprocess
    print("\n1. PREPROCESSING")
    preprocessor = TextPreprocessor("cars")
    original = "Fiat 500 [GAP:1] z [GAP:2] silnikiem o [GAP:3] mocy"
    normalized, gaps_info = preprocessor.preprocess(original)
    print(f"   Original: {original}")
    print(f"   Normalized: {normalized}")
    print(f"   Gaps found: {len(gaps_info)}")
    
    # Step 2: Simulate model output
    print("\n2. MODEL GENERATION (simulated)")
    enhanced = "Fiat 500 biały z benzynowy silnikiem o 100 mocy"
    print(f"   Model output: {enhanced}")
    
    # Step 3: Apply grammar fixes
    print("\n3. GRAMMAR FIXES")
    gaps_filled = [
        {"index": 1, "choice": "biały", "case": "nominative"},
        {"index": 2, "choice": "benzynowy", "case": "instrumental"},
        {"index": 3, "choice": "100", "case": "locative"}
    ]
    corrected, suggestions = fix_grammar_in_text(enhanced, gaps_filled)
    print(f"   Corrected: {corrected}")
    if suggestions:
        print(f"   Fixes: {len(suggestions)}")
        for s in suggestions:
            print(f"     - '{s['original']}' → '{s['corrected']}' ({s['case']})")
    
    # Step 4: Validate
    print("\n4. VALIDATION")
    guardrails = Guardrails(ValidationLevel.NORMAL)
    data = {
        "original_description": original,
        "enhanced_description": corrected,
        "gaps": gaps_filled,
        "alternatives": {},
        "domain": "cars"
    }
    is_valid, report = guardrails.validate_all(data, "cars")
    print(f"   Valid: {is_valid}")
    if report['warnings']:
        print(f"   Warnings: {len(report['warnings'])}")
    
    # Step 5: Final output
    print("\n5. FINAL OUTPUT")
    final = create_final_output(original, corrected, gaps_filled, {})
    print(json.dumps(final, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MCP SERVICE - COMPONENT EXAMPLES")
    print("="*60)
    
    # Run examples
    example_1_preprocessing()
    example_2_polish_grammar()
    example_3_guardrails()
    example_4_postprocessing()
    example_5_full_pipeline()
    
    print("\n" + "="*60)
    print("Examples complete!")
    print("="*60)
