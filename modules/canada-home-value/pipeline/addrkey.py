"""Shared address normalisation so city records, the National Address Register and user picks line up."""
import re, unicodedata

TYPES = {"ST", "STREET", "AVE", "AV", "AVENUE", "RD", "ROAD", "DR", "DRIVE", "CRES", "CR", "CRESCENT", "BLVD", "BOUL", "BOULEVARD",
         "BV", "PL", "PLACE", "CRT", "CT", "CO", "COURT", "TRAIL", "TR", "WAY", "WY", "CLOSE", "CL", "GATE", "GA", "LANE", "LN", "HTS",
         "HEIGHTS", "HT", "GREEN", "GR", "PARK", "PA", "PK", "TERR", "TERRACE", "TC", "CIR", "CIRCLE", "CI", "MANOR", "MR", "POINT", "PT",
         "RISE", "RI", "SQ", "SQUARE", "VIEW", "VW", "BAY", "BA", "RUE", "CH", "CHEMIN", "MONTEE", "MTEE", "RANG", "PLACE", "ALLEE",
         "COMMON", "CM", "LINK", "LI", "MEWS", "ME", "HILL", "HL", "PKY", "PARKWAY", "HWY", "HIGHWAY", "GDNS", "GARDENS", "GD", "ROW",
         "WALK", "WK", "LANDING", "LD", "CV", "COVE", "GROVE", "GV", "ESTATES", "ESTS", "BEND", "BN", "HEATH", "ISLAND", "VILLAGE",
         "RU", "BO", "RT", "RTE", "ROUTE", "MO", "RG", "CA", "CARRE", "CROIS", "CROISSANT", "IMP", "IMPASSE", "PROM", "PROMENADE",
         "TSSE", "TERRASSE", "AL", "PLACE", "CHE", "AU", "AUT", "AUTOROUTE", "SENTIER", "SENT", "COTE", "QUAI", "PARC", "CERCLE", "CE"}
DIRS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW", "NORTH", "SOUTH", "EAST", "WEST", "EST", "OUEST", "NORD", "SUD", "O"}
PARTICLES = {"DE", "LA", "LE", "DU", "DES", "L", "D", "THE"}


def plain(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"\(.*?\)", " ", s)
    return re.sub(r"[^A-Z0-9 ]", " ", s)


def street_core(street):
    allt = [t for t in plain(street).split() if t not in DIRS and t not in PARTICLES]
    toks = [t for t in allt if t not in TYPES] or allt[:1]      # "VIEW ST" keeps VIEW
    toks = [re.sub(r"^(\d+)(ST|ND|RD|TH)$", r"\1", t) for t in toks]   # 42ND -> 42
    toks = ["SAINT" if t in ("ST", "STE", "SAINTE") else t for t in toks]
    toks = [{"TWP": "TOWNSHIP", "RGE": "RANGE", "RR": "RANGE", "MT": "MOUNT"}.get(t, t) for t in toks]
    return " ".join(toks)


def street_dir(street):
    d = [t for t in plain(street).split() if t in DIRS]
    m = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "EST": "E", "OUEST": "W", "O": "W", "NORD": "N", "SUD": "S"}
    return "".join(m.get(x, x) for x in d)


def norm_num(x):
    x = re.sub(r"[^0-9A-Z]", "", plain(x))
    return x.lstrip("0") or ("0" if x else "")


def key(unit, civic, street):
    return f"{norm_num(unit)}|{norm_num(civic)}|{street_core(street)}|{street_dir(street)}"


def split_nar_civic(civic):
    """NAR civic is 'UNIT-NUMBER' or 'NUMBER'."""
    if "-" in civic:
        u, c = civic.rsplit("-", 1)
        return u, c
    return "", civic


# Canonical street type, so "15 DEERMEADE PL" and "15 DEERMEADE RD" stay different properties.
_TYPE_GROUPS = [("ST", "ST", "STREET"), ("AVE", "AVE", "AV", "AVENUE"), ("RD", "RD", "ROAD"), ("DR", "DR", "DRIVE"),
                ("CRES", "CRES", "CR", "CRESCENT", "CROIS", "CROISSANT"), ("PL", "PL", "PLACE"), ("CT", "CT", "CRT", "CO", "COURT"),
                ("BAY", "BAY", "BA"), ("CL", "CL", "CLOSE"), ("WAY", "WAY", "WY"), ("GATE", "GATE", "GA"), ("LANE", "LANE", "LN"),
                ("TERR", "TERR", "TERRACE", "TC"), ("CIR", "CIR", "CIRCLE", "CI"), ("HTS", "HTS", "HEIGHTS", "HT"),
                ("GR", "GREEN", "GR"), ("PARK", "PARK", "PA", "PK"), ("MEWS", "MEWS", "ME"), ("BLVD", "BLVD", "BOUL", "BV", "BOULEVARD", "BO"),
                ("GV", "GROVE", "GV"), ("RISE", "RISE", "RI"), ("VIEW", "VIEW", "VW"), ("MR", "MANOR", "MR"), ("PT", "POINT", "PT"),
                ("SQ", "SQ", "SQUARE"), ("CM", "COMMON", "CM"), ("LINK", "LINK", "LI"), ("HL", "HILL", "HL"), ("LD", "LANDING", "LD"),
                ("CV", "COVE", "CV"), ("TR", "TRAIL", "TR"), ("HWY", "HWY", "HIGHWAY"), ("RUE", "RUE", "RU"), ("CH", "CH", "CHEMIN"),
                ("RTE", "RTE", "RT", "ROUTE"), ("PKY", "PKY", "PKWY", "PARKWAY"), ("ROW", "ROW"), ("WALK", "WALK", "WK"), ("ALLEE", "ALLEE", "AL")]
_TYPE_OF = {v: g[0] for g in _TYPE_GROUPS for v in g[1:]}


def stype(street):
    toks = [t for t in plain(street).split() if t not in DIRS]
    hits = [_TYPE_OF[t] for t in toks if t in _TYPE_OF]
    return hits[-1] if hits else ""


def key3(unit, civic, street):
    """Address key including the street type (for per-property files: legal descriptions, history)."""
    return key(unit, civic, street) + "|" + stype(street)
