import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
PLANNING_MODEL = os.getenv("OPENAI_PLANNING_MODEL", "gpt-5.5")


def _chat_model(model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        temperature=0,
    )


openai_llm = _chat_model(DEFAULT_MODEL)
openai_planning_llm = _chat_model(PLANNING_MODEL)
