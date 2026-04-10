"""
Classify events for STEM-for-kids relevance.

Strategy:
1. Org-level: some orgs are inherently STEM-for-kids — keep all events.
   Others are inherently not — exclude all events.
   The rest need per-event filtering.
2. Event-level: score based on STEM keywords and youth audience signals.
   Penalize for known noise patterns (corporate events, adult-only, etc.)
"""

import re

# ── Org-level classification ──────────────────────────────────────────────────

# Orgs whose entire mission is STEM education for kids — include all events
STEM_KIDS_ORGS = {
    # Afterschool/STEM education
    "Elementary Institute of Science",
    "The LEAGUE of Amazing Programmers",
    "EDforTech",
    "Challenge Island San Diego Coastal",
    "Robolink",
    "RoboThink - Robotics & Video Game Coding",
    "RoboThink Chula Vista",
    "Smart Mind Robotics",
    "MetaCoders, Inc.",
    "Busylabs",
    "Design Code Build",
    "XplorStem LLC",
    "NextWave STEM",
    "Hands-On Technology Education",
    "Girls Who Code",
    "BSD Education",
    "Traveling Miss T. (NBTutors LLC)",
    "Brain Balance of San Diego",
    "SmartLab Learning",
    "Project Lead The Way",
    "DETOUR - FANCY Teen Girls Leadership Academy",
    "Fit Kids America",
    "All Friends Nature School",
    "Intelitek",  # GoCoderz
    "Sylvan Learning of Eastlake/Chula Vista",
    "AoPS (Art of Problem Solving) Academy",
    "Science Delivered",
    "National Inventors Hall of Fame",
    "Zero Robotics",
    "Citizen Schools",

    # Museums / science centers / zoos
    "Fleet Science Center",
    "San Diego Natural History Museum",
    "Birch Aquarium at Scripps Institution of Oceanography",
    "San Diego Air & Space Museum",
    "San Diego Automotive Museum",
    "San Diego Model Railroad Museum",
    "The Living Coast Discovery Center",
    "San Diego Zoo",
    "EcoVivarium",
    "USS Midway Museum",
    "San Diego Children's Discovery Museum",
    "National Marine Mammal Foundation",

    # Environmental / nature education
    "Coastal Roots Farm",
    "Ocean Connectors",
    "Ocean Discovery Institiute",
    "Olivewood Gardens",
    "Agua Hedionda Lagoon Foundation",
    "Escondido Creek Conservancy",
    "Climate Science Alliance",
    "Nature Collective",
    "Coastal Marine Biolabs",
    "I Love A Clean San Diego",
    "Solana Center for Environmental Innovation",
    "Resource Conservation District of Greater San Diego County",
    "The San Diego River Park Foundation",
    "San Dieguito River Valley Conservancy",
    "San Diego County Water Authority",
    "Japanese Friendship Garden Society of San Diego",
    "Anza-Borrego Foundation",
    "The Water Conservation Garden",
    "The EcoLogik Institute",
    "Biomimicry San Diego",
    "Strategic Energy Innovations",

    # STEM outreach / equity
    "Greater San Diego Science and Engineering Fair",
    "Expanding Your Horizons of San Diego",
    "San Diego STEM Ecosystem",
    "North County San Diego STEM Circle",
    "Association for Women in Science San Diego Outreach",
    "National Girls Collaborative",
    "Society of Women Engineers - San Diego",
    "National Society of Black Engineers - San Diego",
    "San Diego Festival of Science & Engineering",
    "USA Science & Engineering Festival",
    "SciREN San Diego",
    "Robotics Inspiring Science and Engineering, Inc.",
    "FRC Team 2543 TitanBot",

    # Education orgs focused on youth
    "EastLake Educational Foundation",
    "Alpine Education Foundation Inc.",
    "Girl Scouts San Diego",
    "Junior Achievement of San Diego County",
    "Outside the Lens",
    "Media Arts Center San Diego",
    "San Diego LabRats",
    "Teach for America San Diego",
    "EnCorps Inc",
    "Thrive Public Schools",
    "Boy Scouts National Foundation",
}

# Orgs that are NOT about STEM for kids — exclude all events
NOT_RELEVANT_ORGS = {
    "Viasat",
    "Qualcomm Incorporated",
    "Genentech",
    "DRS Daylight Solutions",
    "Ionis Pharmaceuticals",
    "Thermo Fisher Scientific",
    "Barnes & Noble",
    "iFLY San Diego",
    "Women's Construction Coalition",
    "Leukemia & Lymphoma Society",
    "The Lawhorn School",
    "DIII-D National Fusion Facility",
    "Wahupa Educational Services",
    "Aquillius Corporation",
    "The Energy Coalition",  # utility programs, not events for kids
    "National University Library",  # adult university programs
    "Grid Alternatives",  # solar installation nonprofit, not youth STEM
    "Biocom Institute",  # biotech industry org
    "American Society of Naval Engineers",  # professional org (mirror has web.dev pages)
    "North American Marine Environment Protaction Association",  # professional maritime
    "San Diego-Imperial Counties Community Colleges",  # adult education
}

# Orgs that need per-event filtering (libraries, universities, government, etc.)
# Everything not in the above two sets goes through event-level filtering.


# ── Event-level relevance scoring ─────────────────────────────────────────────

# Strong STEM indicators (in title or description)
STEM_STRONG = re.compile(
    r"\b(stem|science|coding|robotics?|programming|engineer|computer science"
    r"|biology|chemistry|physics|astronomy|ecology|marine biology"
    r"|maker\s*space|3d print|arduino|raspberry pi|scratch|python"
    r"|drone|circuit|electronics|specimen|microscope|fossil|dinosaur"
    r"|telescope|planetarium|tide\s*pool|dissect|lab\b|experiment"
    r"|biotech|genome|dna|species|habitat|ecosystem|watershed"
    r"|solar|renewable|climate change|carbon|recycle|compost"
    r"|invention|innovate|prototype|design challenge"
    r")\b", re.I
)

# Moderate STEM indicators
STEM_MODERATE = re.compile(
    r"\b(nature|wildlife|animal|bird|fish|shark|turtle|whale|dolphin"
    r"|garden|plant|tree|seed|harvest|farm|soil|organic"
    r"|ocean|reef|lagoon|creek|river|watershed|water quality"
    r"|museum|aquarium|zoo|exhibit|discovery"
    r"|math|geometry|algebra|calculus|statistics"
    r"|space|rocket|satellite|planet|star|moon"
    r"|engineer|build|construct|design|create|code"
    r"|explore|investigate|observe|collect|identify"
    r")\b", re.I
)

# Youth / family audience indicators
YOUTH_SIGNALS = re.compile(
    r"\b(youth|kids|children|child|student|family|families|teen|teenager"
    r"|girl|boy|scout|junior|young|elementary|middle school|high school"
    r"|k-\d|grade\s*\d|ages?\s*\d|preschool|kindergarten|toddler"
    r"|after.?school|afterschool|summer camp|day camp|spring break"
    r"|field trip|school group|homeschool|parent|storytime"
    r"|learning|educational|hands.?on|interactive"
    r"|camp\b|class\b|lesson|workshop|program\b|club\b"
    r"|intern\b|mentor|scholarship|fellows"
    r")\b", re.I
)

# Negative signals — these are probably NOT kid STEM events
NOISE_SIGNALS = re.compile(
    r"\b(earnings|investor|quarterly|shareholder|annual report|10-k|sec filing"
    r"|board meeting|staff meeting|hiring|job opening|career fair"
    r"|wine|beer|cocktail|happy hour|gala|fundrais|auction|luncheon"
    r"|grant program|block grant|procurement|construction bid|rfp|rfq"
    r"|mixer|networking event|conference call|press release|media advisory"
    r"|yoga|meditation|pilates|zumba|fitness"
    r"|wedding|birthday party|rental|private event"
    r"|census|voting|election|council meeting|city council|zoning"
    r"|worship|sermon|mass\b|prayer|bible|church"
    r"|french|spanish|german|arabic|chinese|danish|dutch|filipino"
    r"|real estate|mortgage|insurance|tax prep|financial planning"
    r"|blood drive|vaccination|flu shot"
    r"|dog walk|cat|pet adoption"
    r"|osha|safety certificate|compliance training"
    r"|succulent|floral|flower arranging|wreath|quilt|crochet|knit|craft"
    r"|comedy|improv|karaoke|trivia night|bingo|movie night|film festival"
    r"|book club|poetry|writing group|author reading"
    r"|community development|block grant|zoning|permit|city plan"
    r")\b", re.I
)


def score_event(title: str, description: str, org: str, org_type: str,
                audience: str = "", url: str = "") -> dict:
    """
    Score an event for STEM-for-kids relevance.
    Returns dict with 'relevant' bool, 'score' float, and 'reason' string.
    """
    # Org-level override
    if org in STEM_KIDS_ORGS:
        return {"relevant": True, "score": 1.0, "reason": "stem_org"}
    if org in NOT_RELEVANT_ORGS:
        return {"relevant": False, "score": 0.0, "reason": "not_relevant_org"}

    # Event-level scoring
    text = f"{title} {description} {audience}"

    stem_strong = len(STEM_STRONG.findall(text))
    stem_moderate = len(STEM_MODERATE.findall(text))
    youth_signals = len(YOUTH_SIGNALS.findall(text))
    noise = len(NOISE_SIGNALS.findall(text))

    score = 0.0
    score += min(stem_strong * 0.3, 0.6)
    score += min(stem_moderate * 0.1, 0.3)
    score += min(youth_signals * 0.15, 0.4)
    score -= noise * 0.3

    # Org type bonus — some org types are more likely relevant
    if org_type in ("Afterschool/Out-of-School Time", "Curriculum Provider"):
        score += 0.3
    elif org_type in ("Museums, Science Centers & Zoos",):
        score += 0.2
    elif org_type in ("District/School",):
        score += 0.2
    elif org_type in ("Colleges, Universities, and Certificate/Credential Programs",):
        score += 0.1

    # URL path bonus
    url_lower = url.lower()
    if any(k in url_lower for k in ["/camp", "/class", "/program", "/workshop",
                                     "/youth", "/kids", "/student", "/education"]):
        score += 0.15

    score = max(0.0, min(1.0, score))
    relevant = score >= 0.35

    reason = []
    if stem_strong > 0:
        reason.append(f"stem_strong={stem_strong}")
    if stem_moderate > 0:
        reason.append(f"stem_mod={stem_moderate}")
    if youth_signals > 0:
        reason.append(f"youth={youth_signals}")
    if noise > 0:
        reason.append(f"noise={noise}")

    return {
        "relevant": relevant,
        "score": round(score, 2),
        "reason": ",".join(reason) if reason else "low_signal",
    }
