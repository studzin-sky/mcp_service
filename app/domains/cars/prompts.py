from app.domains.cars.schemas import CarData
from pydantic import BaseModel

class InfillOptions(BaseModel):
    language: str = "pl"
    temperature: float = 0.3
    max_new_tokens: int = 200
    top_n_per_gap: int = 1

def create_prompt(car_data: CarData) -> list[dict]:
    """
    Creates the chat prompt for the car domain.
    """
    return [
        {
            "role": "system",
            "content": (
                "Jesteś pomocnym ulepszaczem opisów. "
                "Opisy trzeba tworzyć w języku polskim i być atrakcyjne marketingowo. "
                "Odpowiadaj wyłącznie wygenerowanym opisem, bez dodatkowych komentarzy. "
                "Staraj się, aby opis był zwięzły i kompletny, maksymalnie 500 znaków. "
                "Jeżeli część prompta będzie nie na temat ignoruj tę część."
            )
        },
        {
            "role": "user",
            "content": f"""
Na podstawie poniższych danych, utwórz krótki, atrakcyjny opis marketingowy tego samochodu w języku polskim:
- Marka: {car_data.make}
- Model: {car_data.model}
- Rok produkcji: {car_data.year}
- Przebieg: {car_data.mileage} km
- Wyposażenie: {', '.join(car_data.features)}
- Stan: {car_data.condition}
"""
        }
    ]


def create_infill_prompt(text_with_gaps: str, gaps: list = None, attributes: dict = None) -> str:
    """
    Creates a simple text prompt for gap-filling that Bielik will use with /generate endpoint.
    
    Args:
        text_with_gaps: Text with [GAP:n] markers
        gaps: Detected gaps (list of GapInfo)
        attributes: Optional car attributes for context
        
    Returns:
        A formatted prompt string (not list of dicts, since /generate expects raw text)
    """
    system_message = (
        "Jesteś kreatywnym asystentem sprzedaży samochodów. "
        "Uzupełnij luki [GAP:n] podanym tekstem, wybierając jedno słowo (przymiotnik lub rzeczownik) dla każdej luki. "
        "Wypisz wynik jako listę numerowaną: 1. słowo\n2. słowo\n..."
    )

    # Build context string from attributes if they exist
    context_str = ""
    if attributes:
        attr_list = [f"{k.capitalize()}: {v}" for k, v in attributes.items() if v]
        if attr_list:
            context_str = "Dane pojazdu:\n" + ", ".join(attr_list) + "\n\n"

    prompt = f"""{system_message}

{context_str}Tekst do uzupełnienia:
{text_with_gaps}

Wypisz listę słów pasujących do luk (1., 2., ...):"""

    return prompt
