"""
MCP Protocol Server Implementation

Exposes the following tools via Anthropic's Model Context Protocol:
1. fill_gaps - Fill gaps in ad text
2. analyze_ad - Analyze ad content type and extract context
3. validate_fill - Validate filled text for quality

Resources:
1. available_models - List of Bielik models
2. ad_schemas - Ad schema definitions
"""

from typing import Any, Dict, List, Optional
from app.logic.text_analyzer import TextAnalyzer, AdType
from app.logic.infill_utils import detect_gaps, apply_fills, parse_infill_response
from app.logic.bielik_client import BielikClient
from app.logic import guardrails
import json
import os


class MCPTools:
    """MCP Tools implementation"""

    def __init__(self, bielik_client: BielikClient, text_analyzer: TextAnalyzer):
        """Initialize with dependencies"""
        self.bielik_client = bielik_client
        self.analyzer = text_analyzer
        self.guard = guardrails.Guardrails()

    async def fill_gaps(self, ad_text: str, model: str = "bielik-1.5b-transformer", gaps_notation: str = "auto") -> Dict[str, Any]:
        """
        Fill gaps in ad text using Bielik model.

        Context is auto-extracted from the ad text using TextAnalyzer.

        Args:
            ad_text: Text with [GAP:n] markers
            model: Bielik model to use
            gaps_notation: Gap notation type ("auto", "[GAP:n]", or "___")

        Returns:
            {
                "filled_text": "Text with gaps filled",
                "gaps": [{"index": 1, "choice": "word", "marker": "[GAP:1]"}],
                "confidence": 0.85,
                "ad_analysis": {"type": "marketing", "keywords": [...]}
            }
        """
        try:
            # Detect gaps
            gaps = detect_gaps(ad_text, gaps_notation)

            if not gaps:
                return {
                    "filled_text": ad_text,
                    "gaps": [],
                    "confidence": 1.0,
                    "error": None
                }

            # Analyze ad to get context
            analysis = self.analyzer.analyze(ad_text)

            # Build adaptive prompt using TextAnalyzer
            messages = self.analyzer.build_adaptive_prompt(analysis, ad_text)

            # Call Bielik for inference
            raw_output = await self.bielik_client.chat(
                model=model,
                messages=messages,
                max_tokens=256,
                temperature=0.3,  # Lower temp for consistency
                top_p=0.9
            )

            # Parse response
            parsed = parse_infill_response(raw_output)
            if not parsed:
                return {
                    "filled_text": ad_text,
                    "gaps": [],
                    "confidence": 0.0,
                    "error": "Could not parse model response"
                }

            # Build fills dictionary
            fills_dict = {}
            gap_fills = []
            for gap_entry in parsed.get("gaps", []):
                idx = gap_entry.get("index")
                choice = gap_entry.get("choice")
                if idx and choice:
                    fills_dict[idx] = choice
                    gap_fills.append({
                        "index": idx,
                        "choice": choice,
                        "marker": f"[GAP:{idx}]"
                    })

            # Apply fills to text
            filled_text = apply_fills(ad_text, gaps, fills_dict)

            # Validate result
            is_valid, validation = self.guard.validate_all({
                "original_description": ad_text,
                "enhanced_description": filled_text,
                "gaps": gap_fills
            }, domain="cars")

            return {
                "filled_text": filled_text,
                "gaps": gap_fills,
                "confidence": 0.9 if is_valid else 0.7,
                "valid": is_valid,
                "ad_analysis": {
                    "type": analysis.ad_type.value,
                    "keywords": analysis.keywords[:5],
                    "sentiment": analysis.sentiment
                },
                "error": None
            }

        except Exception as e:
            return {
                "filled_text": ad_text,
                "gaps": [],
                "confidence": 0.0,
                "error": str(e)
            }

    async def analyze_ad(self, ad_text: str) -> Dict[str, Any]:
        """
        Analyze ad content type and extract context.

        Returns:
            {
                "ad_type": "marketing|technical|mixed",
                "keywords": ["keyword1", "keyword2", ...],
                "car_makes": ["Toyota", "Audi"],
                "sentiment": "positive|negative|neutral",
                "estimated_price": "150000 PLN",
                "condition": ["excellent", "well-maintained"],
                "domain": "cars"
            }
        """
        try:
            analysis = self.analyzer.analyze(ad_text)

            return {
                "ad_type": analysis.ad_type.value,
                "keywords": analysis.keywords,
                "car_makes": analysis.car_makes,
                "car_models": analysis.car_models,
                "condition_descriptors": analysis.condition_descriptors,
                "sentiment": analysis.sentiment,
                "estimated_price": analysis.estimated_price,
                "domain": analysis.domain,
                "confidence": 0.85
            }
        except Exception as e:
            return {
                "ad_type": "mixed",
                "keywords": [],
                "car_makes": [],
                "car_models": [],
                "condition_descriptors": [],
                "sentiment": "neutral",
                "estimated_price": None,
                "error": str(e)
            }

    async def validate_fill(self, original_text: str, filled_text: str, filled_gaps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate filled text for quality and guardrails.

        Args:
            original_text: Original text with gaps
            filled_text: Text with gaps filled
            filled_gaps: List of {"index": n, "choice": "word"}

        Returns:
            {
                "valid": True|False,
                "issues": [],
                "warnings": [],
                "confidence_score": 0.9
            }
        """
        try:
            gap_fills = [
                {
                    "index": g.get("index"),
                    "marker": f"[GAP:{g.get('index')}]",
                    "choice": g.get("choice")
                }
                for g in filled_gaps
            ]

            is_valid, report = self.guard.validate_all({
                "original_description": original_text,
                "enhanced_description": filled_text,
                "gaps": gap_fills
            }, domain="cars")

            return {
                "valid": is_valid,
                "issues": report.get("errors", []),
                "warnings": report.get("warnings", []),
                "confidence_score": 0.9 if is_valid else 0.6,
                "validation_report": report
            }
        except Exception as e:
            return {
                "valid": False,
                "issues": [str(e)],
                "warnings": [],
                "confidence_score": 0.0,
                "error": str(e)
            }


class MCPResources:
    """MCP Resources available to clients"""

    @staticmethod
    def available_models() -> Dict[str, Any]:
        """Get list of available models"""
        return {
            "models": [
                {
                    "id": "bielik-1.5b-transformer",
                    "name": "Bielik 1.5B",
                    "size": "1.5B parameters",
                    "speed": "fast",
                    "quality": "good",
                    "memory": "Low"
                },
                {
                    "id": "bielik-11b-transformer",
                    "name": "Bielik 11B",
                    "size": "11B parameters",
                    "speed": "medium",
                    "quality": "excellent",
                    "memory": "High (requires GPU)"
                }
            ],
            "default_model": "bielik-1.5b-transformer"
        }

    @staticmethod
    def ad_schemas() -> Dict[str, Any]:
        """Get ad type schemas"""
        return {
            "schemas": {
                "marketing": {
                    "type": "Marketing/Sales Copy",
                    "characteristics": [
                        "Dealership or seller description",
                        "Promotional language",
                        "Sales-oriented content",
                        "Focus on benefits to buyer"
                    ],
                    "example_gaps_fill": [
                        "adjectives: wonderful, beautiful, reliable",
                        "sales terms: guaranteed, certified, special offer"
                    ]
                },
                "technical": {
                    "type": "Technical Specifications",
                    "characteristics": [
                        "Vehicle specifications",
                        "Technical details",
                        "Objective facts",
                        "Mileage, year, engine specs"
                    ],
                    "example_gaps_fill": [
                        "technical terms: horsepower, displacement, petrol",
                        "conditions: excellent, well-maintained, original"
                    ]
                },
                "mixed": {
                    "type": "Mixed Content",
                    "characteristics": [
                        "Combination of marketing and technical",
                        "Both subjective and objective content",
                        "Balanced approach needed"
                    ],
                    "example_gaps_fill": [
                        "balanced terms: reliable, powerful, efficient"
                    ]
                }
            }
        }

    @staticmethod
    def supported_domains() -> Dict[str, Any]:
        """Get supported domains"""
        return {
            "domains": [
                {
                    "id": "cars",
                    "name": "Automobiles",
                    "description": "Car listings and descriptions",
                    "status": "production"
                }
            ],
            "coming_soon": ["real_estate", "products"]
        }
