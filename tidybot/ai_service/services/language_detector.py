from typing import Optional, Dict, Any
import re
from collections import Counter

class LanguageDetector:
    """Simple language detection based on common words and patterns"""

    def __init__(self):
        # Common words in different languages
        self.language_patterns = {
            'german': {
                'words': ['der', 'die', 'das', 'und', 'ist', 'für', 'von', 'mit', 'auf', 'in',
                         'zu', 'den', 'des', 'dem', 'eine', 'ein', 'sie', 'er', 'es', 'nicht'],
                'patterns': ['ä', 'ö', 'ü', 'ß'],
                'name': 'German'
            },
            'english': {
                'words': ['the', 'and', 'is', 'for', 'of', 'with', 'on', 'in', 'to', 'a',
                         'an', 'it', 'this', 'that', 'are', 'was', 'were', 'be', 'have'],
                'patterns': [],
                'name': 'English'
            },
            'spanish': {
                'words': ['el', 'la', 'de', 'y', 'es', 'en', 'un', 'una', 'que', 'por',
                         'con', 'para', 'los', 'las', 'del', 'al'],
                'patterns': ['ñ', 'á', 'é', 'í', 'ó', 'ú'],
                'name': 'Spanish'
            },
            'french': {
                'words': ['le', 'la', 'les', 'de', 'et', 'est', 'un', 'une', 'pour', 'avec',
                         'dans', 'sur', 'ce', 'que', 'qui', 'ne', 'pas'],
                'patterns': ['à', 'è', 'é', 'ê', 'ç', 'ô'],
                'name': 'French'
            }
        }

    def detect_language(self, text: str) -> str:
        """Detect the language of the given text"""
        if not text:
            return 'unknown'

        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)

        if not words:
            return 'unknown'

        scores = {}

        for lang, data in self.language_patterns.items():
            score = 0

            # Check common words
            for word in data['words']:
                score += words.count(word) * 2  # Weight word matches higher

            # Check character patterns
            for pattern in data['patterns']:
                score += text_lower.count(pattern)

            scores[lang] = score

        # Return language with highest score
        if scores:
            best_lang = max(scores, key=scores.get)
            if scores[best_lang] > 0:
                return best_lang

        return 'unknown'

    def get_language_info(self, text: str) -> Dict[str, Any]:
        """Get detailed language information"""
        lang = self.detect_language(text)

        return {
            'detected_language': lang,
            'language_name': self.language_patterns.get(lang, {}).get('name', 'Unknown'),
            'confidence': self._calculate_confidence(text, lang)
        }

    def _calculate_confidence(self, text: str, detected_lang: str) -> float:
        """Calculate confidence score for language detection"""
        if detected_lang == 'unknown':
            return 0.0

        text_lower = text.lower()
        words = re.findall(r'\b\w+\b', text_lower)

        if not words:
            return 0.0

        lang_data = self.language_patterns.get(detected_lang, {})
        matches = 0

        for word in lang_data.get('words', []):
            matches += words.count(word)

        # Calculate confidence as ratio of matched words to total words
        confidence = min(1.0, matches / max(len(words), 1) * 3)

        return confidence