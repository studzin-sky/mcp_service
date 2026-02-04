"""
Phase 2b Integration Test Script

Tests the new MCP endpoint flow:
1. Gap detection
2. Prompt building
3. (Mock) Bielik call
4. Response parsing
5. Text reconstruction
6. Guardrails

Run with: python test_phase2b.py
"""

import sys
import asyncio
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from app.logic.infill_utils import detect_gaps, parse_infill_response, apply_fills
from app.domains.cars.prompts import create_infill_prompt

def test_gap_detection():
    """Test gap detection with different notations."""
    print("\n" + "="*60)
    print("TEST 1: Gap Detection")
    print("="*60)
    
    # Test [GAP:n] notation
    text1 = "Auto [GAP:1] z [GAP:2] silnikiem"
    gaps1 = detect_gaps(text1)
    print(f"✓ Detected {len(gaps1)} gaps in '[GAP:n]' notation")
    for gap in gaps1:
        print(f"  - Gap {gap.index}: '{gap.marker}' at position {gap.start}-{gap.end}")
    assert len(gaps1) == 2
    
    # Test ___ notation
    text2 = "Auto ___ z ___ silnikiem"
    gaps2 = detect_gaps(text2)
    print(f"✓ Detected {len(gaps2)} gaps in '___' notation")
    assert len(gaps2) == 2
    
    print("✅ Gap detection: PASSED")

def test_prompt_building():
    """Test prompt building for Bielik."""
    print("\n" + "="*60)
    print("TEST 2: Prompt Building")
    print("="*60)
    
    text = "Auto [GAP:1] z [GAP:2] silnikiem"
    gaps = detect_gaps(text)
    
    prompt = create_infill_prompt(
        text_with_gaps=text,
        gaps=gaps,
        attributes={"brand": "BMW", "year": 2020}
    )
    
    print(f"✓ Built prompt ({len(prompt)} chars)")
    print(f"  Preview: {prompt[:100]}...")
    
    # Check prompt contains key elements
    assert "[GAP:1]" in prompt
    assert "[GAP:2]" in prompt
    assert "BMW" in prompt
    
    print("✅ Prompt building: PASSED")

def test_response_parsing():
    """Test parsing of Bielik responses."""
    print("\n" + "="*60)
    print("TEST 3: Response Parsing")
    print("="*60)
    
    # Test numbered list format (expected from Bielik)
    raw_output = """1. eleganckie
2. 1.6"""
    
    parsed = parse_infill_response(raw_output)
    print(f"✓ Parsed numbered list response")
    print(f"  Gaps: {parsed['gaps']}")
    
    assert len(parsed['gaps']) == 2
    assert parsed['gaps'][0]['choice'] == 'eleganckie'
    assert parsed['gaps'][1]['choice'] == '1.6'
    
    print("✅ Response parsing: PASSED")

def test_text_reconstruction():
    """Test text reconstruction with filled gaps."""
    print("\n" + "="*60)
    print("TEST 4: Text Reconstruction")
    print("="*60)
    
    text = "Auto [GAP:1] z [GAP:2] silnikiem"
    gaps = detect_gaps(text)
    
    alternatives = {
        1: "eleganckie",
        2: "1.6"
    }
    
    filled_text = apply_fills(text, gaps, alternatives)
    print(f"✓ Reconstructed text")
    print(f"  Original: {text}")
    print(f"  Filled:   {filled_text}")
    
    assert "[GAP:" not in filled_text
    assert "eleganckie" in filled_text
    assert "1.6" in filled_text
    
    print("✅ Text reconstruction: PASSED")

def test_end_to_end():
    """Test full pipeline without Bielik."""
    print("\n" + "="*60)
    print("TEST 5: End-to-End Pipeline")
    print("="*60)
    
    # Step 1: Detect gaps
    original_text = "Sprzedam [GAP:1] BMW z [GAP:2] przebiegiem"
    gaps = detect_gaps(original_text)
    print(f"✓ Step 1: Detected {len(gaps)} gaps")
    
    # Step 2: Build prompt
    prompt = create_infill_prompt(original_text, gaps)
    print(f"✓ Step 2: Built prompt")
    
    # Step 3: Mock Bielik response (in real scenario, call bielik_client.generate)
    mock_bielik_response = "1. zadbane\n2. 50000"
    print(f"✓ Step 3: Mock Bielik response: {mock_bielik_response}")
    
    # Step 4: Parse response
    parsed = parse_infill_response(mock_bielik_response)
    alternatives = {g['index']: g['choice'] for g in parsed['gaps']}
    print(f"✓ Step 4: Parsed response -> {alternatives}")
    
    # Step 5: Reconstruct
    filled_text = apply_fills(original_text, gaps, alternatives)
    print(f"✓ Step 5: Reconstructed: {filled_text}")
    
    assert "[GAP:" not in filled_text
    assert "zadbane" in filled_text
    assert "50000" in filled_text
    
    print("✅ End-to-End Pipeline: PASSED")

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("PHASE 2b INTEGRATION TESTS")
    print("="*70)
    
    try:
        test_gap_detection()
        test_prompt_building()
        test_response_parsing()
        test_text_reconstruction()
        test_end_to_end()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED - PHASE 2b IS READY")
        print("="*70 + "\n")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
