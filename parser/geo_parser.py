###finn_project/parser/geo_parser.py

###
import re
###

STOP_WORDS = {
    "legg til som favoritt", "smidig bilhandel", "scale", "service", "privat", "forhandler",
    "bensin", "diesel", "el", "electro", "elektrisk", "hybrid", "plug-in hybrid",
    "automat", "manuell", "bakhjulsdrift", "forhjulsdrift", "firehjulsdrift",
    "4wd", "awd", "suv", "stasjonsvogn", "sedan", "kombi", "coupe", "cabriolet",
    "sammenlign", "merkeforhandler"
}

def extract_location(card) -> str:
    """Вытаскивает чистый город из HTML-карточки объявления."""
    location = "Не указано"
    strings = [s.strip() for s in card.stripped_strings if s.strip()]

    for i in range(len(strings) - 1, max(-1, len(strings) - 12), -1):
        if strings[i].lower() in ("forhandler", "privat"):
            neighbors = []
            if i > 0:
                neighbors.append(strings[i - 1])
            if i + 1 < len(strings):
                neighbors.append(strings[i + 1])

            for candidate in neighbors:
                cand_clean = re.split(r'\s*[•·∙‧・]\s*', candidate)[0].strip()
                cand_lower = cand_clean.lower()
                if (
                    not re.search(r'\d', cand_clean)
                    and len(cand_clean) > 2
                    and cand_lower not in STOP_WORDS
                    and "annonsen" not in cand_lower
                    and cand_lower != "kr"
                ):
                    location = cand_clean
                    break

            if location != "Не указано":
                break

    if location == "Не указано":
        for s in reversed(strings[-6:]):
            s = re.split(r'\s*[•·∙‧・]\s*', s)[0].strip()
            s_low = s.lower()

            if (
                not re.search(r'\d', s)
                and 2 < len(s) <= 35
                and s_low not in STOP_WORDS
                and "annonsen" not in s_low
                and not re.search(r'\b(as|bil|motor|auto|gruppen|norge)\b', s_low)
            ):
                location = s
                break

    if location != "Не указано":
        location = re.split(r'\s*[•·∙‧・]\s*', location)[0].strip()
        if len(location) <= 2 or location.lower() in STOP_WORDS:
            location = "Не указано"

    return location
