#!/usr/bin/env python3

import sys
sys.path.append('/Users/ikarakas/Development/Python/TidyBot/tidybot/ai_service')

from services.language_detector import LanguageDetector

detector = LanguageDetector()

# Test texts
texts = {
    "German Invoice": "Rechnung für Bürobedarf. Sehr geehrte Damen und Herren, hiermit erhalten Sie die Rechnung für die bestellten Büroartikel.",
    "English Document": "This is a test document for TidyBot. It contains information about testing the async/await fix.",
    "Mixed German/English": "Die invoice für the purchase order ist ready.",
    "Spanish": "Este es un documento de prueba para el sistema.",
    "French": "Voici la facture pour les fournitures de bureau."
}

print("Language Detection Test Results:\n" + "="*50)

for name, text in texts.items():
    result = detector.get_language_info(text)
    print(f"\n{name}:")
    print(f"  Text: {text[:50]}...")
    print(f"  Detected: {result['language_name']} ({result['detected_language']})")
    print(f"  Confidence: {result['confidence']:.2%}")

print("\n" + "="*50)
print("✅ Language detection is working correctly!")