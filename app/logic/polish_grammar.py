"""
Polish Grammar Module - Automatic case declension fixer

Fixes common Polish grammar mistakes by converting words to proper cases.
Supports 7 Polish grammatical cases (declension).

Cases:
- Nominative (Mianownik): Base form
- Genitive (Dopełniacz): Of, from
- Dative (Celownik): To, for  
- Accusative (Biernik): Direct object
- Instrumental (Narzędnik): With, by
- Locative (Miejscownik): In, at, about
- Vocative (Wołacz): Addressing
"""

from typing import Tuple, Optional, List
import re

# Common Polish adjectives and their case forms
ADJECTIVE_CASES = {
    # Colors - common in car ads
    "czarny": {
        "nominative": "czarny", "genitive": "czarnego", "dative": "czarnemu",
        "accusative": "czarny", "instrumental": "czarnym", "locative": "czarnym", "vocative": "czarny"
    },
    "biały": {
        "nominative": "biały", "genitive": "białego", "dative": "białemu",
        "accusative": "biały", "instrumental": "białym", "locative": "białym", "vocative": "biały"
    },
    "czerwony": {
        "nominative": "czerwony", "genitive": "czerwonego", "dative": "czerwonemu",
        "accusative": "czerwony", "instrumental": "czerwonym", "locative": "czerwonym", "vocative": "czerwony"
    },
    "srebrny": {
        "nominative": "srebrny", "genitive": "srebrnego", "dative": "srebremu",
        "accusative": "srebrny", "instrumental": "srebrnym", "locative": "srebrnym", "vocative": "srebrny"
    },
    "szary": {
        "nominative": "szary", "genitive": "szarego", "dative": "szaremu",
        "accusative": "szary", "instrumental": "szarym", "locative": "szarym", "vocative": "szary"
    },
    "niebieski": {
        "nominative": "niebieski", "genitive": "niebieskiego", "dative": "niebieskiemu",
        "accusative": "niebieski", "instrumental": "niebieskim", "locative": "niebieskim", "vocative": "niebieski"
    },
    "zielony": {
        "nominative": "zielony", "genitive": "zielonego", "dative": "zielonemu",
        "accusative": "zielony", "instrumental": "zielonym", "locative": "zielonym", "vocative": "zielony"
    },
    "żółty": {
        "nominative": "żółty", "genitive": "żółtego", "dative": "żółtemu",
        "accusative": "żółty", "instrumental": "żółtym", "locative": "żółtym", "vocative": "żółty"
    },
    # Engine types
    "benzynowy": {
        "nominative": "benzynowy", "genitive": "benzynowego", "dative": "benzynowemu",
        "accusative": "benzynowy", "instrumental": "benzynowym", "locative": "benzynowym", "vocative": "benzynowy"
    },
    "dieselowy": {
        "nominative": "dieselowy", "genitive": "dieselowego", "dative": "dieselowemu",
        "accusative": "dieselowy", "instrumental": "dieselowym", "locative": "dieselowym", "vocative": "dieselowy"
    },
    "hybrydowy": {
        "nominative": "hybrydowy", "genitive": "hybrydowego", "dative": "hybrydowemu",
        "accusative": "hybrydowy", "instrumental": "hybrydowym", "locative": "hybrydowym", "vocative": "hybrydowy"
    },
    # Condition adjectives
    "zadbany": {
        "nominative": "zadbany", "genitive": "zadbanego", "dative": "zadbånemu",
        "accusative": "zadbany", "instrumental": "zadbany", "locative": "zadbany", "vocative": "zadbany"
    },
    "nowy": {
        "nominative": "nowy", "genitive": "nowego", "dative": "nowemu",
        "accusative": "nowy", "instrumental": "nowym", "locative": "nowym", "vocative": "nowy"
    },
    "stary": {
        "nominative": "stary", "genitive": "starego", "dative": "staremu",
        "accusative": "stary", "instrumental": "starym", "locative": "starym", "vocative": "stary"
    },
    "piękny": {
        "nominative": "piękny", "genitive": "pięknego", "dative": "pięknemu",
        "accusative": "piękny", "instrumental": "pięknym", "locative": "pięknym", "vocative": "piękny"
    },
}

# Context patterns that indicate required cases
CONTEXT_CASES = {
    # Locative (Miejscownik) - "w", "na", "o" prepositions
    r"w\s+\w+": "locative",  # "w kolorze"
    r"na\s+\w+": "locative",  # "na dachu"
    r"o\s+\w+": "locative",  # "o mocy"
    
    # Instrumental (Narzędnik) - "z", "ze" prepositions
    r"z\s+\w+": "instrumental",  # "z silnikiem"
    r"ze\s+\w+": "instrumental",
    
    # Accusative (Biernik) - Direct object, no preposition usually
    r"ma\s+\w+": "accusative",  # "ma przebieg"
    r"posiada\s+\w+": "accusative",  # "posiada wyposażenie"
    
    # Genitive (Dopełniacz) - "z", "od", "do" in possessive context
    r"drzwi\s+\w+": "genitive",  # "drzwi samochodu"
}


def detect_required_case(text: str, gap_position: int) -> Optional[str]:
    """
    Detect the grammatical case required for a gap based on surrounding context.
    
    Args:
        text: Full text with gaps
        gap_position: Position of the gap in text
        
    Returns:
        Case name (nominative, genitive, etc.) or None if unclear
    """
    # Get context around gap (50 chars before and after)
    start = max(0, gap_position - 50)
    end = min(len(text), gap_position + 50)
    context = text[start:end].lower()
    
    # Check patterns
    for pattern, case in CONTEXT_CASES.items():
        if re.search(pattern, context):
            return case
    
    return None


def convert_to_case(word: str, target_case: str) -> str:
    """
    Convert a Polish adjective to the target case.
    
    Args:
        word: Word to convert (should be in nominative or base form)
        target_case: Target case (nominative, genitive, dative, accusative, instrumental, locative, vocative)
        
    Returns:
        Word in the target case, or original word if not found
    """
    word_lower = word.lower()
    
    # Try exact match
    if word_lower in ADJECTIVE_CASES:
        cases = ADJECTIVE_CASES[word_lower]
        result = cases.get(target_case, word)
        # Preserve original capitalization
        if word[0].isupper():
            result = result.capitalize()
        return result
    
    # Try to find by checking nominative form
    for base_word, cases in ADJECTIVE_CASES.items():
        if cases.get("nominative") == word_lower:
            result = cases.get(target_case, word)
            if word[0].isupper():
                result = result.capitalize()
            return result
    
    # Word not in database, return as-is
    return word


def fix_adjective_case(text: str, adjective: str, required_case: str) -> str:
    """
    Fix a single adjective's case in the text.
    
    Args:
        text: Text containing the adjective
        adjective: The adjective to fix
        required_case: The required case
        
    Returns:
        Text with corrected adjective
    """
    if not required_case or required_case == "nominative":
        return text
    
    correct_form = convert_to_case(adjective, required_case)
    
    # Replace (case-insensitive, but preserve case pattern)
    pattern = re.compile(re.escape(adjective), re.IGNORECASE)
    return pattern.sub(correct_form, text, count=1)


def analyze_gap_context(text: str, gap_index: int) -> dict:
    """
    Analyze the context around a gap to understand what kind of word should fill it.
    
    Returns:
        {
            "position": "after_noun",
            "required_case": "locative",
            "preposition": "w",
            "noun": "kolorze",
            "confidence": 0.95
        }
    """
    # Find the gap marker in text
    gap_marker = f"[GAP:{gap_index}]"
    pos = text.find(gap_marker)
    
    if pos == -1:
        return {"position": "unknown", "required_case": None}
    
    # Get context before and after
    before = text[max(0, pos - 30):pos].strip()
    after = text[pos + len(gap_marker):min(len(text), pos + 30)].strip()
    
    # Detect case
    required_case = detect_required_case(text, pos)
    
    return {
        "position": before,
        "required_case": required_case,
        "after": after,
        "full_context": before + " [GAP:" + str(gap_index) + "] " + after
    }


def fix_grammar_in_text(text: str, gaps_info: List[dict]) -> Tuple[str, List[dict]]:
    """
    Analyze gaps and suggest grammar fixes.
    
    Args:
        text: Text with [GAP:n] markers
        gaps_info: List of gap dicts with "index", "choice", etc.
        
    Returns:
        (corrected_text, fix_suggestions)
    """
    corrected_text = text
    suggestions = []
    
    for gap_info in gaps_info:
        gap_index = gap_info.get("index", 0)
        choice = gap_info.get("choice", "")
        
        # Analyze context
        context = analyze_gap_context(text, gap_index)
        required_case = context.get("required_case")
        
        if required_case and required_case != "nominative":
            # Try to fix the case
            corrected_word = convert_to_case(choice, required_case)
            
            if corrected_word != choice:
                suggestions.append({
                    "gap_index": gap_index,
                    "original": choice,
                    "corrected": corrected_word,
                    "case": required_case,
                    "context": context.get("full_context")
                })
                
                # Replace in text (replace [GAP:n] with corrected word)
                gap_marker = f"[GAP:{gap_index}]"
                corrected_text = corrected_text.replace(gap_marker, corrected_word)
            else:
                # Just replace marker with choice
                gap_marker = f"[GAP:{gap_index}]"
                corrected_text = corrected_text.replace(gap_marker, choice)
        else:
            # Just replace marker with choice
            gap_marker = f"[GAP:{gap_index}]"
            corrected_text = corrected_text.replace(gap_marker, choice)
    
    return corrected_text, suggestions
