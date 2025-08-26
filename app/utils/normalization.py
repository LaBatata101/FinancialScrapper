import re

COIN_SYMBOL_RE = re.compile(r"(|R\$|US\$|€|\$|\s)", re.IGNORECASE)
MULTIPLIERS = {
    "k": 1e3,
    "mil": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mi": 1e6,
    "milhão": 1e6,
    "milhões": 1e6,
    "million": 1e6,
    "b": 1e9,
    "bi": 1e9,
    "bilhão": 1e9,
    "bilhões": 1e9,
    "billion": 1e9,
    "t": 1e12,
    "tri": 1e12,
    "trilhão": 1e12,
    "trilhões": 1e12,
    "trillion": 1e12,
}


def normalize_aum_value(raw_value: str) -> float | None:
    """
    Converts raw AUM values to a standardized numeric format (float).
    Examples:
    - "R$ 2,3 bi" -> 2.3e9
    - "$500 million" -> 5.0e8
    - "1.5 trilhão" -> 1.5e12
    """
    text = raw_value.lower()

    if text.isalpha():
        return None

    text = re.sub(COIN_SYMBOL_RE, "", text).strip()

    # check if the string is in the 123.456,78 format.
    if "." in text and "," in text:
        text = text.replace(".", "").replace(",", ".")
    else:
        text = text.replace(",", ".")

    number_part_str = ""
    multiplier_part_str = ""

    for char in text:
        if char.isdigit() or char == ".":
            number_part_str += char
        else:
            multiplier_part_str += char

    try:
        number = float(number_part_str)
        multiplier = 1.0

        if multiplier_part_str in MULTIPLIERS:
            multiplier = MULTIPLIERS[multiplier_part_str]

        return number * multiplier
    except (ValueError, TypeError):
        return None
