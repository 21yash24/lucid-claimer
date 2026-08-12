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
    Scans raw text and extracts ONLY LBOX- prefix codes (Aug 11 behavior).
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

    # ONLY LBOX- codes (Aug 11: priority 1 exclusively)
    lbox_matches = re.findall(r'\bLBOX-[A-Za-z0-9_-]{5,35}\b', cleaned_text, re.IGNORECASE)
    for code in lbox_matches:
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
    variations = [code]
    c_upper = code.upper()
    replacements = [('E', 'F'), ('TT', 'Y7'), ('QTT', 'QY7'), ('S', '5'), ('O', '0')]
    for old, new in replacements:
        if old in c_upper:
            alt = c_upper.replace(old, new)
            if alt not in variations:
                variations.append(alt)
    return variations
