"""
Enhanced NLP parser for travel requests with improved accuracy and robustness
"""

import spacy
import re
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import dateparser
from dateparser.search import search_dates

# Configure logging
logger = logging.getLogger(__name__)

class NLPParser:
    """Enhanced NLP parser with error handling and improved accuracy"""
    
    def __init__(self):
        self.nlp = self._load_model()
        self.date_settings = {
            "PREFER_DATES_FROM": "current_period",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "UTC",
            "STRICT_PARSING": False,
        }
    
    def _load_model(self):
        """Load spaCy model with error handling"""
        try:
            return spacy.load("en_core_web_lg")
        except OSError:
            try:
                logger.warning("en_core_web_lg not found, falling back to en_core_web_sm")
                return spacy.load("en_core_web_sm")
            except OSError:
                logger.error("No spaCy model available. Install with: python -m spacy download en_core_web_lg")
                raise RuntimeError("spaCy model not available")

# Global parser instance
parser = NLPParser()

def extract_date_range(text: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Enhanced date range extraction with better patterns and error handling"""
    try:
        # Enhanced patterns for date ranges
        date_patterns = [
            r'from\s+(.+?)\s+(?:to|until|through|-)\s+(.+?)(?:[.,;\s]|$)',
            r'between\s+(.+?)\s+and\s+(.+?)(?:[.,;\s]|$)',
            r'starting\s+(.+?)(?:\s+for\s+(\d+)\s+days?)?(?:[.,;\s]|$)',
            r'(\d+)\s+days?\s+(?:starting|from)\s+(.+?)(?:[.,;\s]|$)'
        ]
        
        # for pattern in date_patterns:
        #     m = re.search(pattern, text, flags=re.IGNORECASE)
        #     if m:
        #         try:
        #             d1 = dateparser.parse(m.group(1), settings=parser.date_settings)
                    
                    
        #             # Handle duration patterns
        #             if "days" in pattern and len(m.groups()) > 1:
        #                 if m.group(2) and m.group(2).isdigit():
        #                     days = int(m.group(2))
        #                     d2 = d1 + timedelta(days=days) if d1 else None
        #                 else:
        #                     d2 = dateparser.parse(m.group(2), settings=parser.date_settings) if len(m.groups()) > 1 else None
        #             else:
        #                 d2 = dateparser.parse(m.group(2), settings=parser.date_settings) if len(m.groups()) > 1 else None
                    
        #             if d1 and d2:
        #                 return (min(d1, d2), max(d1, d2))
        #             elif d1:
        #                 # Check for duration indicator
        #                 duration_match = re.search(r'(\d+)\s+days?', text, re.IGNORECASE)
        #                 if duration_match:
        #                     days = int(duration_match.group(1))
        #                     d2 = d1 + timedelta(days=days)
        #                     return (d1, d2)
        #                 return (d1, d1)
        for pattern in date_patterns:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                try:
                    d1 = dateparser.parse(m.group(1), settings=parser.date_settings)
                    d2 = dateparser.parse(m.group(2), settings=parser.date_settings) if m.groups(2) else d1
                    
                    now = datetime.now(tz=d1.tzinfo)

                    if d1:
                        if d1.year > now.year + 1 or d1.year < now.year:
                            d1 = d1.replace(year=now.year, month=now.month, day=now.day)
                            logger.warning(f"Date {d1} is too far in the future or past, ignoring")
                    if d2:
                        if d2.year > now.year + 1 or d2.year < now.year:
                            d2 = d2.replace(year=now.year, month=now.month, day=now.day)
                            logger.warning(f"Date {d2} is too far in the future or past, ignoring")
                    
                    return (min(d1, d2), max(d1, d2)) if d1 and d2 else (d1, d2)
                except Exception as e:
                    logger.warning(f"Error parsing date in pattern: {e}")
                    continue

        # Fallback to search_dates with enhanced filtering
        raw = search_dates(text, settings=parser.date_settings)
        if not raw:
            return None, None

        # Enhanced filtering to exclude false positives
        filtered = []
        for frag, dt in raw:
            # Skip monetary values, pure numbers, and common false positives
            if any(indicator in frag.lower() for indicator in ["$", "€", "£", "usd", "eur"]):
                continue
            if frag.strip().isdigit() and len(frag.strip()) < 4:
                continue
            if frag.lower() in ["a", "an", "the", "in", "on", "at"]:
                continue
            filtered.append((frag, dt))

        if not filtered:
            return None, None

        dts = [dt for _, dt in filtered]
        return (min(dts), max(dts))
        
    except Exception as e:
        logger.error(f"Error in date extraction: {e}")
        return None, None


def extract_budget(text: str, doc) -> Tuple[Optional[Decimal], List[str]]:
    """Enhanced budget extraction with multiple currency support"""
    warnings = []
    budget = None
    
    try:
        # Enhanced currency patterns
        currency_patterns = [
            r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # USD
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|usd)',
            r'€\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # EUR
            r'£\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # GBP
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:euros?|eur)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:pounds?|gbp)',
        ]
        
        for pattern in currency_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try:
                    # Take the largest amount found
                    amounts = [float(match.replace(',', '')) for match in matches]
                    budget = Decimal(str(max(amounts)))
                    break
                except (ValueError, TypeError) as e:
                    warnings.append(f"Error parsing currency: {e}")

        # Fallback to spaCy MONEY entities
        if budget is None:
            for ent in doc.ents:
                if ent.label_ == "MONEY":
                    try:
                        cleaned = re.sub(r'[^\d.,]', '', ent.text).replace(',', '')
                        if cleaned and '.' in cleaned:
                            budget = Decimal(cleaned)
                        elif cleaned:
                            budget = Decimal(cleaned)
                        break
                    except (ValueError, TypeError) as e:
                        warnings.append(f"Error parsing MONEY entity: {e}")

    except Exception as e:
        logger.error(f"Error in budget extraction: {e}")
        warnings.append(f"Budget extraction error: {e}")
    
    return budget, warnings

def extract_group_size(text: str) -> Optional[int]:
    """Extract group size from travel request"""
    try:
        # Patterns for group size
        group_patterns = [
            r'(\d+)\s+(?:people|persons|travelers|guests|adults)',
            r'(?:group|party)\s+of\s+(\d+)',
            r'family\s+of\s+(\d+)',
            r'(\d+)\s+(?:couples?)',
        ]
        
        for pattern in group_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        
        # Default assumptions
        if re.search(r'\bfamily\b', text, re.IGNORECASE):
            return 4
        if re.search(r'\bcouple\b', text, re.IGNORECASE):
            return 2
            
        return None
    except Exception as e:
        logger.error(f"Error extracting group size: {e}")
        return None

def parse_travel_request(text: str) -> dict:
    """Enhanced travel request parsing with better error handling and additional features"""
    start_time = time.time()
    
    try:
        if not text or not text.strip():
            raise ValueError("Empty text provided")
        
        doc = parser.nlp(text)
        warnings = []
        
        # Enhanced result structure
        result = {
            "locations": [], 
            "dates": [], 
            "interests": [], 
            "budget": None,
            "duration_days": None,
            "group_size": None,
            "travel_style": None,
            "confidence_score": 0.0,
            "parsing_time_ms": 0.0,
            "warnings": []
        }

        # Enhanced location extraction (GPE, LOC, FAC)
        for ent in doc.ents:
            if ent.label_ in ("GPE", "LOC", "FAC"):
                location = ent.text.strip()
                if location and location not in result["locations"]:
                    result["locations"].append(location)
        
        # Enhanced date extraction
        start, end = extract_date_range(text)
        if start and end:
            if start.date() == end.date():
                result["dates"] = [start]
                result["duration_days"] = 1
            else:
                result["dates"] = [start, end]
                result["duration_days"] = (end - start).days
        elif start:
            result["dates"] = [start]
            result["duration_days"] = 1
        
        # Enhanced budget extraction
        budget, budget_warnings = extract_budget(text, doc)
        result["budget"] = float(budget) if budget else None
        warnings.extend(budget_warnings)
        
        # Group size extraction
        result["group_size"] = extract_group_size(text)
        
        # Travel style detection
        text_lower = text.lower()
        if any(word in text_lower for word in ["luxury", "premium", "upscale", "5-star"]):
            result["travel_style"] = "luxury"
        elif any(word in text_lower for word in ["budget", "cheap", "affordable"]):
            result["travel_style"] = "budget"
        elif any(word in text_lower for word in ["family", "kids", "children"]):
            result["travel_style"] = "family"
        elif any(word in text_lower for word in ["adventure", "hiking", "extreme"]):
            result["travel_style"] = "adventure"

        # Build enhanced date token set
        date_tokens = {
            tok.text.lower()
            for ent in doc.ents
            if ent.label_ == "DATE"
            for tok in ent
            if tok.is_alpha
        }

        # Enhanced interest extraction
        seen = set()
        for tok in doc:
            lemma = tok.lemma_.lower()
            if (
                tok.pos_ in ("NOUN", "PROPN", "ADJ")  # Added adjectives
                and tok.is_alpha
                and len(lemma) > 2  # Filter short words
                and lemma not in seen
                and tok.text not in result["locations"]
                and tok.text.lower() not in date_tokens
                and not tok.like_num
                and not tok.is_stop  # Filter stop words
            ):
                seen.add(lemma)
                result["interests"].append(lemma)

        # Calculate confidence score
        confidence = 0.0
        if result["locations"]: confidence += 30.0
        if result["dates"]: confidence += 25.0
        if result["budget"]: confidence += 20.0
        if result["interests"]: confidence += 15.0
        if result["group_size"]: confidence += 5.0
        if result["travel_style"]: confidence += 5.0
        
        result["confidence_score"] = min(confidence, 100.0)
        result["parsing_time_ms"] = (time.time() - start_time) * 1000
        result["warnings"] = warnings

        logger.info(f"Parsed travel request with {result['confidence_score']:.1f}% confidence")
        return result
        
    except Exception as e:
        logger.error(f"Error parsing travel request: {e}")
        parsing_time = (time.time() - start_time) * 1000
        
        return {
            "locations": [], 
            "dates": [], 
            "interests": [], 
            "budget": None,
            "duration_days": None,
            "group_size": None,
            "travel_style": None,
            "confidence_score": 0.0,
            "parsing_time_ms": parsing_time,
            "warnings": [f"Parsing error: {str(e)}"]
        }
