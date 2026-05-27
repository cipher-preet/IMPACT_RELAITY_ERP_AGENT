from langchain_openai import ChatOpenAI

openai_llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0
)