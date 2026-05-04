"""
H1-B Sponsor Check — based on USCIS public H1-B disclosure data.
Top employers in tech, analytics, consulting, and finance known to sponsor.
"""

# Top H1-B sponsors in tech / analytics / consulting (from USCIS LCA data)
H1B_SPONSORS = {
    # Big Tech
    "amazon", "amazon web services", "aws", "google", "alphabet", "microsoft", "apple",
    "meta", "facebook", "netflix", "nvidia", "intel", "ibm", "oracle", "salesforce",
    "adobe", "servicenow", "workday", "sap", "vmware", "broadcom", "qualcomm",
    "cisco", "palo alto networks", "crowdstrike", "datadog", "snowflake", "databricks",
    "palantir", "splunk", "elastic", "mongodb", "confluent", "dbt labs", "fivetran",
    "stripe", "square", "block", "paypal", "braintree", "twilio", "zendesk", "okta",
    "cloudflare", "fastly", "akamai", "rackspace",

    # Consulting / Professional Services
    "deloitte", "pwc", "kpmg", "ernst & young", "ey", "accenture", "mckinsey",
    "boston consulting group", "bcg", "bain", "capgemini", "cognizant", "infosys",
    "wipro", "tata consultancy", "tcs", "hcl", "tech mahindra", "epam", "globant",

    # Finance / Banking
    "jpmorgan", "jp morgan", "goldman sachs", "morgan stanley", "bank of america",
    "citibank", "citi", "wells fargo", "blackrock", "fidelity", "vanguard",
    "american express", "capital one", "discover", "mastercard", "visa",
    "bloomberg", "two sigma", "de shaw", "jane street", "citadel",

    # Healthcare / Pharma / Biotech
    "johnson & johnson", "pfizer", "merck", "abbvie", "amgen", "genentech",
    "biogen", "moderna", "bristol myers squibb", "eli lilly", "cvs health",
    "unitedhealth", "anthem", "aetna", "humana", "epic systems",

    # Retail / E-commerce
    "walmart", "target", "ebay", "shopify", "wayfair", "chewy", "etsy",
    "doordash", "instacart", "lyft", "uber", "airbnb",

    # Media / Entertainment / Gaming
    "disney", "comcast", "at&t", "verizon", "t-mobile", "spotify",
    "twitter", "x corp", "linkedin", "snap", "pinterest", "reddit",

    # Semiconductors / Hardware
    "amd", "arm", "texas instruments", "applied materials", "lam research",
    "micron", "western digital", "seagate",

    # Aerospace / Defense / Auto
    "boeing", "lockheed martin", "raytheon", "northrop grumman", "spacex",
    "tesla", "ford", "general motors", "toyota", "honda",

    # Data / Analytics focused
    "tableau", "palantir", "alteryx", "qlik", "microstrategy", "informatica",
    "talend", "domo", "looker", "sisense", "mixpanel", "amplitude",

    # Cloud / DevOps
    "hashicorp", "github", "gitlab", "atlassian", "jfrog", "chef",
    "puppet", "new relic", "dynatrace", "appdynamics",

    # Startups known to sponsor
    "openai", "anthropic", "cohere", "scale ai", "hugging face", "weights & biases",
    "anyscale", "modal", "together ai", "mistral", "deepmind",
    "waymo", "cruise", "aurora", "zoox", "nuro",

    # Boston / Northeast specific
    "wayfair", "athenahealth", "hubspot", "drift", "salsify", "brightcove",
    "toast", "rapid7", "carbon black", "veeva systems", "medidata",
    "biogen", "vertex pharmaceuticals", "shire", "takeda",
}


def normalize(name: str) -> str:
    """Lowercase + strip common suffixes for fuzzy matching."""
    name = name.lower().strip()
    for suffix in [", inc", " inc.", " inc", " llc", " ltd", " corp", " corporation",
                   " co.", " co", " limited", " group", " technologies", " technology",
                   " solutions", " services", " holdings", " labs", " ai"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def is_h1b_sponsor(company_name: str) -> bool:
    """Return True if company is a known H1-B sponsor."""
    if not company_name:
        return False
    norm = normalize(company_name)
    # Exact match
    if norm in H1B_SPONSORS:
        return True
    # Partial match (company name contains a known sponsor)
    for sponsor in H1B_SPONSORS:
        if sponsor in norm or norm in sponsor:
            return True
    return False


def h1b_label(company_name: str) -> str:
    if not company_name:
        return "Unknown"
    if is_h1b_sponsor(company_name):
        return "H1-B Sponsor ✓"
    return "Verify on myvisajobs.com"
