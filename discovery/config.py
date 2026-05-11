"""Discovery PL Creators v1 — configuration.

Edit hashtags / filters here before each run.
PRD: docs/prd-discovery-v1.md (parked in chat).
"""

IG_HASHTAGS = [
    # from SOP
    "biznesonline",
    "marketing",
    "treneronline",
    "edukacja",
    "rozwojosobisty",
    # extensions (user-approved, "rozszerzona lista")
    "przedsiebiorca",
    "onlinebiznes",
    "produktywnosc",
    "finanseosobiste",
    "mentalhealthpl",
    "nauka",
    "jezykangielski",
    "fitnesspl",
]

TT_HASHTAGS = [
    # from SOP
    "biznes",
    "marketing",
    "copywriting",
    "edutok",
    "nauka",
    "rozwojosobisty",
    # extensions
    "edukacjapl",
    "storytime",
    "opowiadania",
    "produktywnosc",
    "motywacja",
    "fitnesspolska",
]

# Hard filters
FOLLOWERS_MIN = 1_000
FOLLOWERS_MAX = 10_000
MIN_REELS_30D = 5
WINDOW_DAYS = 30

# PL language heuristic
PL_DIACRITICS = set("ąęćłńóśźżĄĘĆŁŃÓŚŹŻ")
PL_STOPWORDS = {"się", "jest", "nie", "jak", "że", "to", "na", "do", "dla", "ale", "czy", "tylko", "wszystko"}
PL_STOPWORDS_HITS_REQUIRED = 2

# Soft filter — bio blacklist (corp / B2B signals)
BIO_BLACKLIST_SUBSTRINGS = [
    "b2b",
    "saas",
    "hr tech",
    "automation dla firm",
    "agencja marketingowa",
    "marketing manager",
]

# Output cap per platform (user choice: "bez capu, max 100")
MAX_ROWS_PER_PLATFORM = 100
