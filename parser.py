import re
from typing import List, Optional

# Regular expressions for common giveaway drop patterns
# 1. Lucid Box keys starting with LBOX e.g. "LBOX1234", "LBOX-X7Y9", "LBOX_9921"
CODE_PATTERNS = [
    re.compile(r'\bLBOX[A-Z0-9_-]{3,24}\b', re.IGNORECASE),                         # Priority 1: LBOX... keys
    re.compile(r'\b[A-Z0-9]{4,6}-[A-Z0-9]{4,6}-[A-Z0-9]{4,6}\b', re.IGNORECASE), # e.g. XXXX-YYYY-ZZZZ
    re.compile(r'\b(?:CODE|PROMO|DROP|GIVEAWAY|CLAIM|KEY|BOX):\s*([A-Z0-9_-]{4,24})\b', re.IGNORECASE),
    re.compile(r'\b[A-Z0-9]{8,20}\b'), # Standalone 8-20 character uppercase alphanumeric codes
]


# 2. URLs / Drop links e.g. https://lucidtrading.com/claim?code=XYZ
URL_PATTERN = re.compile(r'https?://[^\s>"]+', re.IGNORECASE)

def clean_discord_text(text: str) -> str:
    """Removes Discord custom emoji syntax like <:name:123456789> before parsing."""
    if not text:
        return ""
    # Strip custom emoji syntax <:emojiname:123456789012345678>
    text = re.sub(r'<a?:[a-zA-Z0-9_]+:\d+>', '', text)
    return text

def extract_all_giveaway_codes(text: str) -> List[str]:
    """
    Scans raw text and extracts ALL unique giveaway codes or claim keys found.
    Returns a list of unique codes.
    """
    if not text:
        return []

    cleaned_text = clean_discord_text(text)
    extracted_codes = []

    # 1. Search for all pattern matches in text
    for pattern in CODE_PATTERNS:
        matches = pattern.finditer(cleaned_text)
        for match in matches:
            code = match.group(1) if match.groups() else match.group(0)
            # Avoid matching purely numeric 18-19 digit Discord IDs
            if code.isdigit() and len(code) >= 17:
                continue
            if code and code not in extracted_codes:
                extracted_codes.append(code)

    # 2. Search for claim links with ?code= or ?claim=
    url_matches = URL_PATTERN.findall(cleaned_text)
    for url in url_matches:
        code_param = re.search(r'[?&](?:code|claim|key|drop)=([A-Z0-9_-]+)', url, re.IGNORECASE)
        if code_param:
            code = code_param.group(1)
            if code and code not in extracted_codes:
                extracted_codes.append(code)

    return extracted_codes

def parse_discord_message_all(message_content: str, embeds: List[dict]) -> List[str]:
    """
    Inspects plain text content and all Discord embeds, returning ALL unique codes found.
    """
    found_codes = []

    # Scan plain text
    for code in extract_all_giveaway_codes(message_content):
        if code not in found_codes:
            found_codes.append(code)

    # Scan embeds
    for embed in embeds:
        if 'title' in embed:
            for code in extract_all_giveaway_codes(embed['title']):
                if code not in found_codes:
                    found_codes.append(code)
        if 'description' in embed:
            for code in extract_all_giveaway_codes(embed['description']):
                if code not in found_codes:
                    found_codes.append(code)
        for field in embed.get('fields', []):
            for code in extract_all_giveaway_codes(field.get('name', '')) + extract_all_giveaway_codes(field.get('value', '')):
                if code not in found_codes:
                    found_codes.append(code)

    return found_codes

