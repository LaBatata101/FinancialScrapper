import logging
import os
import re

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.db.models import AUMSnapshot, Company
from app.services.budget_manager import BudgetManager
from app.utils.extraction import MAX_TOKENS, encoding, extract_relevant_chunks
from app.utils.normalization import normalize_aum_value

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

EXTRACTION_PROMPT = """
Qual é o patrimônio sob gestão (AUM) anunciado por {company_name}?

Analise o conteúdo fornecido e responda APENAS com:
- O valor numérico e unidade (ex.: R$ 2,3 bi)
- OU "NAO_DISPONIVEL" se não encontrar

Também indique a fonte exata onde encontrou a informação.

Conteúdo para análise:
{relevant_content}
"""

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


def truncate_prompt_if_needed(prompt: str, max_tokens: int) -> str:
    tokens = encoding.encode(prompt)
    if len(tokens) > max_tokens:
        return encoding.decode(tokens[:max_tokens])
    return prompt


class AIExtractionAgent(Agent):
    def __init__(self):
        super().__init__(model=OpenAIChat(id="gpt-4o", max_tokens=150, api_key=OPENAI_API_KEY))

    async def extract_aum(self, company: Company, scraped_pages, db: AsyncSession):
        company_id = company.id
        company_name = company.name

        logger.info(f"Starting AUM extraction for {company_name}")

        content = ""
        for page in scraped_pages:
            source = page["url"]
            html_content = page["content"]
            relevant_content = extract_relevant_chunks(html_content)

            if not relevant_content:
                logger.info(f"No relevant content for AUM found in {source}")
                continue

            content += f"SOURCE: {source}\n{relevant_content}\n"

        prompt = EXTRACTION_PROMPT.format(company_name=company_name, relevant_content=content)
        prompt = truncate_prompt_if_needed(prompt, MAX_TOKENS)

        budget_manager = BudgetManager(db)

        try:
            response = await self.arun(prompt)

            result_text = response.get_content_as_string().strip()
            total_tokens_used = response.metrics["total_tokens"][0]

            await budget_manager.log_usage(company_id, "aum_extraction", total_tokens_used)

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return

        if "NAO_DISPONIVEL" in result_text.upper():
            logger.info(f"AUM not available for {company_name} according to AI.")
            snapshot = AUMSnapshot(company_id=company_id, aum_value="NAO_DISPONIVEL")
            db.add(snapshot)
            await db.commit()
            return

        [raw_value, _, source_url] = result_text.splitlines()
        standardized_value = normalize_aum_value(raw_value)

        if standardized_value:
            unit_search = re.search(r"(|R\$|US\$|€|\$)", raw_value, re.IGNORECASE)
            unit = unit_search.group(1) if unit_search else "USD"

            snapshot = AUMSnapshot(
                company_id=company_id,
                aum_value=raw_value,
                aum_unit=unit,
                standardized_value=int(standardized_value),
                source_url=source_url.lstrip("Fonte: "),
            )
            db.add(snapshot)
            await db.commit()
            logger.info(f"SUCCESS! AUM of {standardized_value} saved for {company_name}")
        else:
            logger.warning(f"AI returned a value, but it could not be normalized: '{raw_value}'")
