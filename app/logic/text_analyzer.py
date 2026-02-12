"""
TextAnalyzer - Smart context extraction from heterogeneous otomoto ads

Detects ad type (marketing/technical/mixed) and extracts relevant keywords
to improve prompt generation and gap-filling quality.

Uses Spacy for:
- Named entity recognition (car makes, models, features)
- Part-of-speech tagging (adjectives, nouns for keywords)
- Dependency parsing (relationship analysis)
- Sentence segmentation (smart context extraction)
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum

try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False


class AdType(str, Enum):
    """Classification of ad content type"""
    MARKETING = "marketing"      # Dealership/sales pitch
    TECHNICAL = "technical"      # Specific vehicle specs
    MIXED = "mixed"              # Both elements present


@dataclass
class TextAnalysis:
    """Result of analyzing ad text"""
    ad_type: AdType
    keywords: List[str]           # Extracted domain-relevant words
    condition_descriptors: List[str]  # Quality indicators (excellent, worn, etc.)
    car_makes: List[str]          # Identified car brands
    car_models: List[str]         # Identified car models
    sentiment: str                # positive/negative/neutral
    estimated_price: Optional[str] = None
    domain: str = "cars"


class TextAnalyzer:
    """
    Analyzes car ad text to extract context and detect ad type.

    Improves prompt generation by understanding:
    - Whether ad is marketing copy or technical specifications
    - What keywords are relevant to gap-filling
    - What sentiment/tone to use in fills
    """

    def __init__(self, model_name: str = "pl_core_news_lg"):
        """Initialize with Polish Spacy model"""
        self.model_name = model_name
        self.nlp = None
        self.has_spacy = HAS_SPACY

        if self.has_spacy:
            try:
                self.nlp = spacy.load(model_name)
            except OSError:
                print(f"[TextAnalyzer] Model {model_name} not found. Install with:")
                print(f"  python -m spacy download {model_name}")
                self.has_spacy = False

        # Keywords for different ad types
        self.marketing_keywords = {
            "najlepszy", "wspaniały", "piękny", "nowoczesny", "elegancki",
            "komfortowy", "niezawodny", "pewny", "doskonały", "idealny",
            "okazja", "promocja", "specjalna", "polecamy", "gwarancja",
            "certyfikat", "serwis", "oryginał", "zadbany"
        }

        self.technical_keywords = {
            "silnik", "pojemność", "moc", "przebieg", "rocznik", "paliwo",
            "spalanie", "emissions", "naped", "skrzynia", "biegów",
            "zawieszenie", "hamulce", "opony", "felgi", "tłumik",
            "katalizator", "turbo", "turbosprężarka", "intercooler",
            "pojazd", "samochód", "auto", "marka", "model"
        }

        self.condition_words = {
            "doskonały": "excellent",
            "bardzo dobry": "very good",
            "dobry": "good",
            "zadowalający": "satisfactory",
            "zły": "poor",
            "zadbany": "well-maintained",
            "zaniedbany": "neglected",
            "oryginalny": "original",
            "lakierowany": "repainted",
            "wybity": "dented"
        }

    def analyze(self, text: str) -> TextAnalysis:
        """
        Analyze ad text and extract context.

        Returns:
            TextAnalysis with ad_type, keywords, descriptors, etc.
        """
        if not self.has_spacy or not self.nlp:
            # Fallback to regex-based analysis if Spacy not available
            return self._analyze_regex(text)

        try:
            doc = self.nlp(text)

            # Extract entities, keywords, ad type
            ad_type = self._detect_ad_type(doc, text)
            keywords = self._extract_keywords(doc)
            condition_descriptors = self._extract_conditions(text)
            car_makes = self._extract_car_makes(doc, text)
            car_models = self._extract_car_models(doc, text)
            sentiment = self._analyze_sentiment(text)
            price = self._extract_price(text)

            return TextAnalysis(
                ad_type=ad_type,
                keywords=keywords,
                condition_descriptors=condition_descriptors,
                car_makes=car_makes,
                car_models=car_models,
                sentiment=sentiment,
                estimated_price=price,
                domain="cars"
            )
        except Exception as e:
            print(f"[TextAnalyzer] Error during analysis: {e}, falling back to regex")
            return self._analyze_regex(text)

    def _detect_ad_type(self, doc, text: str) -> AdType:
        """Detect if ad is marketing, technical, or mixed"""
        text_lower = text.lower()

        # Count marketing vs technical keywords
        marketing_count = sum(1 for token in doc if token.text.lower() in self.marketing_keywords)
        technical_count = sum(1 for token in doc if token.text.lower() in self.technical_keywords)

        # Check for dealership/company markers
        dealership_markers = [
            "salon", "dealer", "sprzedaż", "oferta", "zapewniamy", "gwarantujemy",
            "jesteśmy", "najlepsze", "specjalista", "doświadczenie", "zaufanie"
        ]
        has_dealership = sum(1 for marker in dealership_markers if marker in text_lower)

        # Check for technical spec markers
        spec_markers = [
            "cc", "km", "roku", "silnika", "paliwa", "spalania", "naped", "skrzynia",
            "przebieg", "pojemność", "moc", "kw", "ps"
        ]
        has_specs = sum(1 for marker in spec_markers if marker in text_lower)

        # Decide ad type
        if has_dealership > has_specs and marketing_count > technical_count:
            return AdType.MARKETING
        elif has_specs > has_dealership and technical_count > marketing_count:
            return AdType.TECHNICAL
        else:
            return AdType.MIXED

    def _extract_keywords(self, doc) -> List[str]:
        """Extract relevant keywords from text"""
        keywords = set()

        # Add marketing and technical keywords that appear in text
        for token in doc:
            word = token.text.lower()
            if word in self.marketing_keywords:
                keywords.add(word)
            elif word in self.technical_keywords:
                keywords.add(word)
            # Add adjectives and nouns with good POS tags
            elif token.pos_ in ["ADJ", "NOUN"] and len(word) > 3:
                keywords.add(word)

        return list(keywords)[:20]  # Limit to top 20

    def _extract_conditions(self, text: str) -> List[str]:
        """Extract condition/quality descriptors"""
        descriptors = []
        text_lower = text.lower()

        for condition, english in self.condition_words.items():
            if condition in text_lower:
                descriptors.append(english)

        return descriptors

    def _extract_car_makes(self, doc, text: str) -> List[str]:
        """Extract car makes/brands mentioned in text"""
        makes = set()

        # Common Polish car makes
        common_makes = [
            "toyota", "volkswagen", "audi", "bmw", "mercedes", "ford", "fiat",
            "peugeot", "renault", "opel", "kia", "hyundai", "skoda", "honda",
            "mazda", "suzuki", "mitsubishi", "volvo", "jaguar", "porsche",
            "citroen", "dacia", "jeep", "chevrolet", "dodge", "cadillac",
            "tesla", "nissan", "subaru", "lexus", "infiniti", "acura"
        ]

        text_lower = text.lower()
        for make in common_makes:
            if make in text_lower:
                makes.add(make)

        return list(makes)

    def _extract_car_models(self, doc, text: str) -> List[str]:
        """Extract car models mentioned in text"""
        models = set()

        # Extract likely model names (capitalized words after brand names or near "model")
        text_lower = text.lower()

        # Common patterns for model mentions
        model_patterns = [
            r"\b(civic|corolla|camry|accord|cr-v|rav4|q3|a4|a6|x5|c-class|e-class|focus|fiesta|f-150)",
            r"model[:\s]+(\w+)",
            r"(series|edition|sport|comfort|elegance|active)\b",
        ]

        for pattern in model_patterns:
            matches = re.findall(pattern, text_lower)
            models.update(matches)

        return list(models)[:5]

    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis based on keywords"""
        text_lower = text.lower()

        positive_words = [
            "najlepszy", "wspaniały", "piękny", "nowoczesny", "doskonały",
            "idealne", "polecam", "zadbany", "nowy", "zachwycony"
        ]

        negative_words = [
            "słaby", "zły", "stary", "zniszczony", "problem", "usterka",
            "wymiana", "naprawa", "złe", "brak"
        ]

        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)

        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"

    def _extract_price(self, text: str) -> Optional[str]:
        """Extract price if mentioned"""
        # Pattern for price: number with optional spaces and PLN/zł/euro
        price_pattern = r"(\d{1,3}(?:\s\d{3})*)\s*(pln|zł|euro|eur|€)"
        match = re.search(price_pattern, text, re.IGNORECASE)

        if match:
            return f"{match.group(1)} {match.group(2)}"
        return None

    def _analyze_regex(self, text: str) -> TextAnalysis:
        """Fallback regex-based analysis when Spacy not available"""
        text_lower = text.lower()

        # Detect ad type
        dealership_markers = sum(1 for m in ["salon", "dealer", "oferta", "zapewniamy"] if m in text_lower)
        spec_markers = sum(1 for m in ["cc", "km", "silnika", "spalania"] if m in text_lower)

        if dealership_markers > spec_markers:
            ad_type = AdType.MARKETING
        elif spec_markers > dealership_markers:
            ad_type = AdType.TECHNICAL
        else:
            ad_type = AdType.MIXED

        # Extract price
        price_pattern = r"(\d{1,3}(?:\s\d{3})*)\s*(pln|zł|euro)"
        price_match = re.search(price_pattern, text_lower)
        price = f"{price_match.group(1)} {price_match.group(2)}" if price_match else None

        # Simple keyword extraction
        keywords = re.findall(r"\b[a-ząćęłńóśźż]{4,}\b", text_lower)
        keywords = list(set(keywords))[:20]

        return TextAnalysis(
            ad_type=ad_type,
            keywords=keywords,
            condition_descriptors=[],
            car_makes=[],
            car_models=[],
            sentiment="neutral",
            estimated_price=price,
            domain="cars"
        )

    def extract_semantic_context(
        self, text: str, gap_start: int, gap_end: int, context_tokens: int = 150
    ) -> str:
        """
        Extract meaningful context around a gap.

        Instead of fixed 150 tokens, extract complete sentences/paragraphs.

        Args:
            text: Full text
            gap_start: Start position of gap marker
            gap_end: End position of gap marker
            context_tokens: Approximate token budget

        Returns:
            Extracted context as string
        """
        if not self.has_spacy or not self.nlp:
            # Fallback: fixed character window
            context_chars = context_tokens * 4  # ~4 chars per token
            left_idx = max(0, gap_start - context_chars // 2)
            right_idx = min(len(text), gap_end + context_chars // 2)
            return text[left_idx:right_idx]

        try:
            doc = self.nlp(text)

            # Find sentence containing the gap
            gap_sentence = None
            for sent in doc.sents:
                if sent.start_char <= gap_start < sent.end_char:
                    gap_sentence = sent
                    break

            if not gap_sentence:
                # Fallback to character-based extraction
                context_chars = context_tokens * 4
                left_idx = max(0, gap_start - context_chars // 2)
                right_idx = min(len(text), gap_end + context_chars // 2)
                return text[left_idx:right_idx]

            # Extract surrounding sentences (±1 sentence for context)
            all_sentences = list(doc.sents)
            gap_sent_idx = all_sentences.index(gap_sentence)

            start_sent = max(0, gap_sent_idx - 1)
            end_sent = min(len(all_sentences), gap_sent_idx + 2)

            # Concatenate sentences
            context_start = all_sentences[start_sent].start_char
            context_end = all_sentences[end_sent - 1].end_char

            return text[context_start:context_end]

        except Exception as e:
            print(f"[TextAnalyzer] Error extracting context: {e}")
            # Fallback to character extraction
            context_chars = context_tokens * 4
            left_idx = max(0, gap_start - context_chars // 2)
            right_idx = min(len(text), gap_end + context_chars // 2)
            return text[left_idx:right_idx]

    def build_adaptive_prompt(self, analysis: TextAnalysis, text_with_gaps: str) -> List[Dict[str, str]]:
        """
        Build adaptive prompt based on ad type and content.

        Different prompts for marketing vs technical ads:
        - Marketing: Use creative, sales-oriented language
        - Technical: Use specifications-oriented language
        - Mixed: Balance both approaches

        Args:
            analysis: TextAnalysis result
            text_with_gaps: Text containing gap markers

        Returns:
            List of chat messages (system + user)
        """

        # System message varies by ad type
        if analysis.ad_type == AdType.MARKETING:
            system_msg = (
                "Jesteś kreatywnym asystentem sprzedaży samochodów. "
                "Twoim zadaniem jest uzupełnienie luk [GAP:n] w marketingowym opisie pojazdu "
                "używając atrakcyjnych, sprzedażowych słów. "
                "Dla każdej luki wybierz JEDNO słowo (przymiotnik lub rzeczownik), "
                "które będzie przyciągające i sprawdzać się w kontekście sprzedaży. "
                "Wypisz wynik jako prostą listę numerowaną: 1. słowo\\n2. słowo"
            )
        elif analysis.ad_type == AdType.TECHNICAL:
            system_msg = (
                "Jesteś technicznym specjalistą katalogowania pojazdów. "
                "Twoim zadaniem jest uzupełnienie luk [GAP:n] w opisie technicznym pojazdu "
                "używając precyzyjnych, specjalistycznych słów. "
                "Dla każdej luki wybierz JEDNO słowo (przymiotnik lub rzeczownik), "
                "które dokładnie opisze cechę pojazdu. "
                "Wypisz wynik jako prostą listę numerowaną: 1. słowo\\n2. słowo"
            )
        else:  # MIXED
            system_msg = (
                "Jesteś asystentem sprzedaży samochodów. "
                "Twoim zadaniem jest uzupełnienie luk [GAP:n] w opisie pojazdu "
                "używając zarówno atrakcyjnych jak i precyzyjnych słów. "
                "Dla każdej luki wybierz JEDNO słowo (przymiotnik lub rzeczownik), "
                "które będzie zarówno przyciągające jak i dokładne. "
                "Wypisz wynik jako prostą listę numerowaną: 1. słowo\\n2. słowo"
            )

        # Build user message with keywords as context
        keywords_str = ", ".join(analysis.keywords[:10]) if analysis.keywords else ""
        keywords_context = f"Słowa kluczowe: {keywords_str}\n\n" if keywords_str else ""

        user_msg = f"""{keywords_context}Tekst do uzupełnienia:
{text_with_gaps}

Wypisz listę słów pasujących do luk (1., 2., ...):"""

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
