import re
from typing import List, Optional

FORBIDDEN_WORDS = {
    "PAYMENT", "CANCEL", "CLOSE", "TERMS", "PRIVACY", "CREDIT", "CARD", 
    "CHECKOUT", "PROCEED", "SELECT", "SUMMARY", "LUCID", "TRADING", 
    "ACCOUNT", "PRODUCT", "SUBTOTAL", "TOTAL", "STATUS", "SUBMIT", "CODE",
    "OFF", "COPY", "EVAL", "25K", "50K", "100K", "150K", "LUCIDPRO", "LUCIDPRE",
    "PRO", "PERCENT", "FREE", "ROBLOX", "SPOTIFY", "POKER", "GAME"
}

COMMON_ENGLISH_WORDS = {
    "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", 
    "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", 
    "ITS", "NEW", "NOW", "OLD", "SEE", "TWO", "WAY", "WHO", "DID", "HAVE", 
    "FROM", "THEY", "THIS", "WILL", "YOUR", "BEEN", "GOOD", "MUCH", "SOME", 
    "TIME", "VERY", "WHEN", "COME", "HERE", "JUST", "KNOW", "LIKE", "LOOK", 
    "MAKE", "MOST", "OVER", "SUCH", "TAKE", "THAN", "THEM", "WELL", "WERE", 
    "WITH", "THAT", "INTO", "ONLY", "ALSO", "BACK", "AFTER", "FIRST", "THEIR", 
    "THERE", "THESE", "THINK", "THOSE", "ABOUT", "COULD", "EVERY", "GOING", 
    "GREAT", "WHICH", "WOULD", "OTHER", "TRADE", "TODAY", "OFFER", "VALID", 
    "CLAIM", "CHECK", "RETWEET", "FOLLOW", "COMMENT", "REPLY", "HTTPS", "HTTP",
    "TWITTER", "PIC", "STATUS", "MEDIA", "PHOTO", "VIDEO", "LINK"
}

def clean_discord_text(text: str) -> str:
    """Removes Discord custom emoji syntax and normalizes smart quotes."""
    if not text:
        return ""
    text = re.sub(r'<a?:[a-zA-Z0-9_]+:\d+>', '', text)
    text = text.replace('“', ' ').replace('”', ' ').replace('"', ' ').replace("'", ' ').replace('‘', ' ').replace('’', ' ')
    return text

def extract_all_giveaway_codes(text: str) -> List[str]:
    """
    Scans raw text and extracts LUCID- and LBOX- prefix codes.
    """
    if not text:
        return []

    cleaned_text = clean_discord_text(text)
    
    # Ignore non-Lucid URLs
    urls = re.findall(r'https?://\S+', cleaned_text)
    for u in urls:
        if not any(domain in u.lower() for domain in ['lucidtrading.com', 't.co', 'x.com']):
            cleaned_text = cleaned_text.replace(u, ' ')

    extracted_codes = []

    # LUCID- and LBOX- codes (deduped, upper-cased)
    code_matches = re.findall(r'\b(?:LUCID|LBOX)-[A-Za-z0-9_-]{5,35}\b', cleaned_text, re.IGNORECASE)
    for code in code_matches:
        c_upper = code.upper()
        if c_upper not in extracted_codes:
            extracted_codes.append(c_upper)

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

def generate_code_variations(code: str) -> List[str]:
    """
    Generates plausible OCR-correction variations for a code, handling the
    character confusions tesseract commonly makes on giveaway code fonts
    (0/O, 5/S, 1/I/l, 7/Z/T, 2/Z, 6/G, 8/B, Q/O). Tries single-char fixes
    first, then pairs, capped at 24 variants. The original code is first.
    """
    variations = [code]
    c_upper = code.upper()

    confusion_sets = [
        {'0', 'O'},
        {'5', 'S'},
        {'1', 'I', 'l'},
        {'7', 'Z', 'T'},
        {'2', 'Z'},
        {'6', 'G'},
        {'8', 'B'},
        {'Q', 'O', '0'},
    ]

    # (char index, replacement chars) for every ambiguous position
    ambiguous = []
    for idx, ch in enumerate(c_upper):
        for group in confusion_sets:
            if ch in group:
                ambiguous.append((idx, sorted(group - {ch})))
                break

    from itertools import combinations, product

    def build(fix_positions):
        for combo in product(*[ambiguous[p][1] for p in fix_positions]):
            chars = list(c_upper)
            for p, rep in zip(fix_positions, combo):
                chars[ambiguous[p][0]] = rep
            v = ''.join(chars)
            if v not in variations:
                variations.append(v)
                if len(variations) >= 24:
                    return False
        return True

    # Prioritize the most likely single fixes, then pairs of fixes
    for fix_count in (1, 2):
        for positions in combinations(range(len(ambiguous)), fix_count):
            if not build(positions):
                return variations

    return variations
