"""
Polish Grammar Module - Automatic case declension fixer using Spacy

Fixes common Polish grammar mistakes by converting words to proper cases
based on the surrounding context (prepositions, noun agreement, verb objects).
"""

import spacy
import re
from typing import Tuple, Optional, List, Dict, Any

# Load Spacy model
try:
    nlp = spacy.load("pl_core_news_lg")
    print("MCP: Loaded pl_core_news_lg for grammar fixing.")
except Exception as e:
    print(f"MCP: Warning - Could not load pl_core_news_lg: {e}")
    print("MCP: Falling back to limited regex-based grammar fixing.")
    nlp = None

# Case mapping from Spacy morph features
SPACY_CASE_MAP = {
    "Nom": "nominative",
    "Gen": "genitive",
    "Dat": "dative",
    "Acc": "accusative",
    "Ins": "instrumental",
    "Loc": "locative",
    "Voc": "vocative"
}

# Inverse mapping
CASE_TO_SPACY = {v: k for k, v in SPACY_CASE_MAP.items()}

# Common prepositions and the cases they govern
PREPOSITION_CASES = {
    "w": "locative",
    "we": "locative",
    "na": "locative",
    "o": "locative",
    "po": "locative",
    "przy": "locative",
    "z": "instrumental",
    "ze": "instrumental",
    "bez": "genitive",
    "do": "genitive",
    "od": "genitive",
    "dla": "genitive",
    "przez": "accusative"
}

# Verbs that typically take Accusative objects in car ads
VERB_ACCUSATIVE = {
    "sprzedać", "sprzedam", "kupić", "kupię", "mieć", "ma", 
    "posiadać", "posiada", "oferować", "oferuję", "ogłaszać", "ogłaszam"
}

# Expanded dictionary of common adjectives in car ads
ADJECTIVE_CASES = {
    "czarny": {"nominative": "czarny", "genitive": "czarnego", "dative": "czarnemu", "accusative": "czarny", "instrumental": "czarnym", "locative": "czarnym"},
    "biały": {"nominative": "biały", "genitive": "białego", "dative": "białemu", "accusative": "biały", "instrumental": "białym", "locative": "białym"},
    "czerwony": {"nominative": "czerwony", "genitive": "czerwonego", "dative": "czerwonemu", "accusative": "czerwony", "instrumental": "czerwonym", "locative": "czerwonym"},
    "srebrny": {"nominative": "srebrny", "genitive": "srebrnego", "dative": "srebremu", "accusative": "srebrny", "instrumental": "srebrnym", "locative": "srebrnym"},
    "szary": {"nominative": "szary", "genitive": "szarego", "dative": "szaremu", "accusative": "szary", "instrumental": "szarym", "locative": "szarym"},
    "niebieski": {"nominative": "niebieski", "genitive": "niebieskiego", "dative": "niebieskiemu", "accusative": "niebieski", "instrumental": "niebieskim", "locative": "niebieskim"},
    "zielony": {"nominative": "zielony", "genitive": "zielonego", "dative": "zielonemu", "accusative": "zielony", "instrumental": "zielonym", "locative": "zielonym"},
    "granatowy": {"nominative": "granatowy", "genitive": "granatowego", "dative": "granatowemu", "accusative": "granatowy", "instrumental": "granatowym", "locative": "granatowym"},
    "benzynowy": {"nominative": "benzynowy", "genitive": "benzynowego", "dative": "benzynowemu", "accusative": "benzynowy", "instrumental": "benzynowym", "locative": "benzynowym"},
    "diesel": {"nominative": "diesel", "genitive": "diesla", "dative": "dieslowi", "accusative": "diesla", "instrumental": "dieslem", "locative": "dieslu"},
    "elektryczny": {"nominative": "elektryczny", "genitive": "elektrycznego", "dative": "elektrycznemu", "accusative": "elektryczny", "instrumental": "elektrycznym", "locative": "elektrycznym"},
    "hybrydowy": {"nominative": "hybrydowy", "genitive": "hybrydowego", "dative": "hybrydowemu", "accusative": "hybrydowy", "instrumental": "hybrydowym", "locative": "hybrydowym"},
    "manualny": {"nominative": "manualny", "genitive": "manualnego", "dative": "manualnemu", "accusative": "manualny", "instrumental": "manualnym", "locative": "manualnym"},
    "automatyczny": {"nominative": "automatyczny", "genitive": "automatycznego", "dative": "automatycznemu", "accusative": "automatyczny", "instrumental": "automatycznym", "locative": "automatycznym"},
    "zadbany": {"nominative": "zadbany", "genitive": "zadbanego", "dative": "zadbanemu", "accusative": "zadbany", "instrumental": "zadbanym", "locative": "zadbanym"},
    "dobry": {"nominative": "dobry", "genitive": "dobrego", "dative": "dobremu", "accusative": "dobry", "instrumental": "dobrym", "locative": "dobrym"},
    "idealny": {"nominative": "idealny", "genitive": "idealnego", "dative": "idealnemu", "accusative": "idealny", "instrumental": "idealnym", "locative": "idealnym"},
    "pierwszy": {"nominative": "pierwszy", "genitive": "pierwszego", "dative": "pierwszemu", "accusative": "pierwszy", "instrumental": "pierwszym", "locative": "pierwszym"},
    "oryginalny": {"nominative": "oryginalny", "genitive": "oryginalnego", "dative": "oryginalnemu", "accusative": "oryginalny", "instrumental": "oryginalnym", "locative": "oryginalnym"},
    "bogaty": {"nominative": "bogaty", "genitive": "bogatego", "dative": "bogatemu", "accusative": "bogaty", "instrumental": "bogatym", "locative": "bogatym"},
    "używany": {"nominative": "używany", "genitive": "używanego", "dative": "używanemu", "accusative": "używany", "instrumental": "używanym", "locative": "używanym"},
    "niski": {"nominative": "niski", "genitive": "niskiego", "dative": "niskiemu", "accusative": "niski", "instrumental": "niskim", "locative": "niskim"}
}


def convert_to_case(word: str, target_case: str, pos: str = "ADJ") -> str:
    """Look up word and return inflected form."""
    if not word or not target_case:
        return word
        
    word_lower = word.lower()
    
    # Check dictionary
    if word_lower in ADJECTIVE_CASES:
        return ADJECTIVE_CASES[word_lower].get(target_case, word)
    
    # Only apply heuristics to Adjectives
    if pos == "ADJ":
        if target_case in ["locative", "instrumental"]:
            if word_lower.endswith("a"): return word[:-1] + "ej"
            if word_lower.endswith("y"): return word + "m"
            if word_lower.endswith("i"): return word + "m"
        elif target_case == "genitive":
            if word_lower.endswith("y"): return word[:-1] + "ego"
            if word_lower.endswith("i"): return word[:-1] + "ego"
    
    return word


def analyze_context_and_fix(context_text: str, choice: str) -> str:
    """Analyzes context before gap and inflects the choice."""
    if not nlp or not context_text or not choice:
        return choice
        
    # Analyze the CHOICE word first
    choice_doc = nlp(choice)
    if not choice_doc or len(choice_doc) == 0:
        return choice
    
    choice_token = choice_doc[0]
    choice_pos = choice_token.pos_
    choice_morph = choice_token.morph
    
    # Analyze context
    doc = nlp(context_text[-100:].strip())
    if not doc or len(doc) == 0:
        return choice
        
    # Find last significant token (ignoring punctuation/space)
    last_token = None
    for i in range(len(doc)-1, -1, -1):
        if doc[i].pos_ not in ["PUNCT", "SPACE"]:
            last_token = doc[i]
            break
            
    if not last_token:
        return choice
        
    target_case = None
    
    # 1. Preposition
    if last_token.pos_ == "ADP":
        target_case = PREPOSITION_CASES.get(last_token.lemma_.lower())
        
    # 2. Noun Agreement
    elif last_token.pos_ == "NOUN":
        case_feature = last_token.morph.get("Case")
        if case_feature:
            target_case = SPACY_CASE_MAP.get(case_feature[0])
            
    # 3. Verb Governance
    elif last_token.pos_ == "VERB":
        lemma = last_token.lemma_.lower()
        if lemma in VERB_ACCUSATIVE:
            target_case = "accusative"
            
    if target_case:
        # CHECK IF ALREADY IN TARGET CASE
        current_cases = choice_morph.get("Case")
        target_spacy_case = CASE_TO_SPACY.get(target_case)
        
        if current_cases and target_spacy_case in current_cases:
            # Already in correct case, don't touch it!
            # (e.g. "do jazdy" -> "jazdy" is already Genitive)
            return choice

        inflected = convert_to_case(choice, target_case, pos=choice_pos)
        # Preserve capitalization
        if choice and choice[0].isupper():
            inflected = inflected.capitalize()
        return inflected
        
    return choice


def fix_grammar_in_text(text: str, gaps_info: List[Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """Replaces [GAP:n] markers with inflected choices."""
    if not nlp:
        print("MCP: Skipping grammar fix (Spacy model not loaded)")
        return text, gaps_info
        
    # Robustly map index -> choice (handle both dicts and objects)
    gap_map = {}
    for g in gaps_info:
        try:
            if isinstance(g, dict):
                idx = g.get('index')
                choice = g.get('choice', '')
            else:
                idx = getattr(g, 'index', None)
                choice = getattr(g, 'choice', '')
            if idx is not None:
                gap_map[str(idx)] = choice
        except Exception:
            continue

    gap_pattern = re.compile(r"\[GAP:(\d+)\]")
    current_pos = 0
    result_parts = []
    updated_gaps = []
    
    matches = list(gap_pattern.finditer(text))
    print(f"MCP: Found {len(matches)} gaps in text for grammar fixing.")

    for match in matches:
        gap_id_str = match.group(1)
        start, end = match.span()
        
        # Add text before gap
        result_parts.append(text[current_pos:start])
        
        # Get choice
        choice = gap_map.get(gap_id_str, "")
        
        # Context is everything we have built so far
        full_context = "".join(result_parts)
        
        # Fix inflection
        corrected = analyze_context_and_fix(full_context, choice)
        
        result_parts.append(corrected)
        current_pos = end
        
        # Track for metadata
        updated_gaps.append({
            "index": int(gap_id_str),
            "original_choice": choice,
            "choice": corrected
        })
        
    # Add remaining text
    result_parts.append(text[current_pos:])
    final_text = "".join(result_parts)
    
    return final_text, updated_gaps