import re
from typing import List, Optional

# Regular expressions for common giveaway drop patterns
# Match LBOX codes, CJ/WAWA/LUCID/FLEX codes, or general alphanumeric coupon codes (3-30 chars)
CODE_PATTERNS = [
    re.compile(r'\bLBOX[A-Z0-9_-]{2,30}\b', re.IGNORECASE),
    re.compile(r'\b(?:WAWA|CJ|LUCID|FLEX|PROMO|EVAL|FREE)[A-Z0-9_-]{0,25}\b', re.IGNORECASE),
    re.compile(r'\b[A-Z0-9]{4,25}\b', re.IGNORECASE),
]



# 2. URLs / Drop links e.g. https://lucidtrading.com/claim?code=XYZ
URL_PATTERN = re.compile(r'https?://[^\s>"]+', re.IGNORECASE)

def clean_discord_text(text: str) -> str:
    """Removes Discord custom emoji syntax and normalizes smart quotes."""
    if not text:
        return ""
    # Strip custom emoji syntax <:emojiname:123456789012345678>
    text = re.sub(r'<a?:[a-zA-Z0-9_]+:\d+>', '', text)
    # Replace smart quotes with standard spaces so word boundaries work
    text = text.replace('“', ' ').replace('”', ' ').replace('"', ' ').replace("'", ' ').replace('‘', ' ').replace('’', ' ')
    return text

FORBIDDEN_WORDS = {
    "PAYMENT", "CANCEL", "CLOSE", "TERMS", "PRIVACY", "CREDIT", "CARD", 
    "CHECKOUT", "PROCEED", "SELECT", "SUMMARY", "LUCID", "TRADING", 
    "ACCOUNT", "PRODUCT", "SUBTOTAL", "TOTAL", "STATUS", "SUBMIT", "CODE",
    "OFF", "COPY", "EVAL", "25K", "50K", "100K", "150K", "LUCIDPRO", "LUCIDPRE",
    "PRO", "PERCENT", "FREE"
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

def extract_all_giveaway_codes(text: str) -> List[str]:
    """
    Scans raw text and extracts ALL unique giveaway codes or claim keys found.
    Returns a list of unique codes.
    """
    if not text:
        return []

    cleaned_text = clean_discord_text(text)
    # Remove URLs
    cleaned_text = re.sub(r'https?://\S+|t\.co/\S+', '', cleaned_text, flags=re.IGNORECASE)

    extracted_codes = []

    # 1. First search for explicit code patterns after keywords like 'code', 'coupon', 'use'
    keyword_match = re.finditer(r'(?:code|coupon|use|drop|key|voucher)\s*[:=»"“\'`]?\s*([A-Za-z0-9_-]{3,30})', cleaned_text, re.IGNORECASE)
    for m in keyword_match:
        c = m.group(1).strip().upper()
        if c not in FORBIDDEN_WORDS and c not in COMMON_ENGLISH_WORDS and len(c) >= 3:
            if c not in extracted_codes:
                extracted_codes.append(c)

    # 2. Extract any standalone alphanumeric token (3-25 chars) that is not a forbidden or noise word
    tokens = re.findall(r'\b[A-Za-z0-9_-]{3,25}\b', cleaned_text)
    for token in tokens:
        t_upper = token.upper()
        if t_upper.isdigit() and len(t_upper) >= 15: # Ignore long numeric IDs
            continue
        if t_upper not in FORBIDDEN_WORDS and t_upper not in COMMON_ENGLISH_WORDS:
            # Must contain at least 1 letter or digit
            if any(ch.isalnum() for ch in t_upper):
                if t_upper not in extracted_codes:
                    extracted_codes.append(t_upper)

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

