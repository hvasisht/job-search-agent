"""
Unified job filter — applied to ALL sources after normalization.
"""

import re

EXCLUDE_TITLE_WORDS = [
    "senior", " sr ", "sr.", "lead ", "principal", "staff ",
    "manager", "director", "vp ", "vice president", "head of",
    "architect", "distinguished", "fellow", "president", "cto",
    "cdo", "coo", "partner", "consultant",
    " ii", " iii", " iv",
    "mid-level", "mid level", "intermediate",
    "level 2", "level 3", "l2 ", "l3 ",
    "ios ", "android ", "mobile ", "frontend ", "front-end ",
    "backend ", "back-end ", "devops", "infrastructure", "security ",
    "embedded ", "firmware ", "hardware ", "network ",
]

EXCLUDE_DESC_PATTERNS = [
    r"\b[3-9]\d*\s*\+\s*years?\s+(?:of\s+)?(?:relevant\s+|related\s+|industry\s+|professional\s+|work\s+)?experience",
    r"\b[3-9]\d*\s+years?\s+(?:of\s+)?(?:relevant\s+|related\s+|industry\s+|professional\s+|work\s+)?experience",
    r"(?:minimum|requires?|must\s+have|at\s+least)\s+(?:\w+\s+)?[3-9]\d*\s+years?",
    r"\b[3-9]\d*\s*\+\s*years?\s+(?:in|of|with)\s+\w",
    r"\b[3-9]\d*\s+years?\s+of\s+\w",
    r"\b[3-9]\s*[-–]\s*\d+\s+years?",
    r"\b(?:ph\.?d\.?|doctorate)\s+(?:required|degree\s+required)",
    r"phd\s+required",
    r"\b(?:mid[- ]level|intermediate\s+(?:engineer|analyst|scientist))\b",
    # OPT / citizenship hard filters
    r"\bno\s+(?:opt|cpt|f-?1)\b",
    r"(?:opt|cpt|f-?1)\s+(?:not\s+accepted|not\s+eligible|not\s+supported|ineligible)",
    r"must\s+be\s+(?:a\s+)?(?:us\s+)?(?:citizen|permanent\s+resident)",
    r"(?:us\s+)?citizen(?:ship)?\s+(?:only|required|is\s+required)",
    r"security\s+clearance\s+required",
    r"active\s+(?:secret|ts|top\s+secret)\s+clearance",
]

DATA_ROLE_TITLE_KEYWORDS = [
    "data analyst", "data scientist", "data engineer", "data science",
    "analytics engineer", "machine learning", "ml engineer", "ai engineer",
    "applied ai", "applied scientist", "applied ml", "applied researcher",
    "business intelligence", "bi analyst", "quantitative analyst",
    "data analytics", "nlp engineer", "llm engineer", "research scientist",
    "associate data", "junior data",
]

NON_US_LOCATIONS = [
    "canada", "toronto", "montreal", "vancouver", "calgary", "ottawa",
    "united kingdom", "london", "england", "scotland", "manchester",
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "pune",
    "australia", "sydney", "melbourne", "brisbane",
    "germany", "berlin", "munich", "france", "paris",
    "singapore", "ireland", "dublin", "netherlands", "amsterdam",
    "israel", "tel aviv", "poland", "romania",
]

US_LOCATION_SIGNALS = [
    "us", "united states", "remote", "new york", "boston", "chicago",
    "seattle", "san francisco", "austin", "atlanta", "denver", "dallas",
    "hybrid", "usa", "ny", ", ca", " ca ", "tx", "cambridge", "washington",
    "virginia", "maryland", "new jersey", "anywhere",
    "los angeles", "san jose", "philadelphia", "phoenix", "portland",
    "san diego", "raleigh", "minneapolis", "miami", "pittsburgh",
    "columbus", "nashville", "charlotte", "detroit", "salt lake",
    "florida", "north carolina", "illinois", "ohio", "michigan",
]

EXCLUDE_COMPANY_PATTERNS = [
    r"\bjobs?\s+via\b",
    r"\bstaffing\b",
    r"\brecruiting\b",
    r"\brecruitment\b",
    r"\bconsulting\s+(llc|inc|corp|group|services)\b",
    r"\bsolutions\s+(llc|inc|corp|group|services)\b",
    r"\boutsourcing\b",
]

EXCLUDE_COMPANIES = {
    "rk infotech", "infosys", "tata consultancy", "tcs", "wipro", "hcl",
    "cognizant", "tech mahindra", "mphasis", "hexaware", "ltimindtree",
    "capgemini", "dice", "cybercoders", "revature",
    "kforce", "modis", "insight global", "apex systems",
}

MIN_DESC_LENGTH = 300


def _is_staffing_company(company: str) -> bool:
    c = company.lower().strip()
    if c in EXCLUDE_COMPANIES:
        return True
    for pattern in EXCLUDE_COMPANY_PATTERNS:
        if re.search(pattern, c, re.IGNORECASE):
            return True
    return False


def is_relevant(job: dict) -> bool:
    title    = (job.get("title") or "").lower()
    desc     = (job.get("description") or "").lower()
    location = (job.get("location") or "").lower()

    if not job.get("url"):
        return False
    if len(desc) < MIN_DESC_LENGTH:
        return False
    if not any(kw in title for kw in DATA_ROLE_TITLE_KEYWORDS):
        return False
    for word in EXCLUDE_TITLE_WORDS:
        if word in title:
            return False
    if _is_staffing_company(job.get("company") or ""):
        return False
    for pattern in EXCLUDE_DESC_PATTERNS:
        if re.search(pattern, desc, re.IGNORECASE):
            return False
    if any(kw in location for kw in NON_US_LOCATIONS):
        return False
    if location and not any(sig in location for sig in US_LOCATION_SIGNALS):
        return False
    return True


def deduplicate(jobs: list) -> list:
    seen_urls, seen_keys, out = set(), set(), []
    for job in jobs:
        url = (job.get("url") or "").split("?")[0].rstrip("/")
        key = f"{job.get('company','').lower().strip()}|{job.get('title','').lower().strip()}"
        if url in seen_urls or key in seen_keys:
            continue
        seen_urls.add(url)
        seen_keys.add(key)
        out.append(job)
    return out
