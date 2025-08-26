import re

import tiktoken
from bs4 import BeautifulSoup

encoding = tiktoken.encoding_for_model("gpt-4o")

AUM_KEYWORDS = re.compile(
    r"(aum|assets under management|patrimônio sob gestão|sob gestão|ativos sob gestão|recursos sob gestão)",
    re.IGNORECASE,
)

MONETARY_VALUE_REGEX = re.compile(r"((R\$|US\$) ?\d+[,.]\d+ ?\w+)", re.IGNORECASE)

MAX_TOKENS = 1350


def sanitize_paragraph(p: str) -> str:
    output = []
    for line in p.splitlines():
        line = line.strip()
        if line:
            output.append(line)
    return "\n".join(output)


def extract_relevant_chunks(html_content: str) -> str:
    """
    Extracts only HTML snippets likely to contain AUM data.
    Returns a single string with the concatenated snippets, respecting the token limit.
    """
    if not html_content:
        return ""

    soup = BeautifulSoup(html_content, "lxml")

    tags = soup.find_all(["p", "span"])

    relevant_chunks = []
    total_tokens = 0

    for paragraph in [tag.get_text() for tag in tags]:
        p_lower = paragraph.lower()

        has_keyword = AUM_KEYWORDS.search(p_lower)
        has_monetary_value = MONETARY_VALUE_REGEX.search(p_lower)

        if has_keyword or has_monetary_value:
            sanitized_paragraph = sanitize_paragraph(paragraph)
            chunk_tokens = len(encoding.encode(sanitized_paragraph))

            if total_tokens + chunk_tokens <= MAX_TOKENS:
                relevant_chunks.append(sanitized_paragraph)
                total_tokens += chunk_tokens
            else:
                break

    if not relevant_chunks:
        return ""

    return "\n".join(relevant_chunks)
