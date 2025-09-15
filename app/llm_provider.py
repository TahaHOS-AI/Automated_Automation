# file: app/llm_provider.py
import os
from dotenv import load_dotenv

load_dotenv()

from langchain_ollama import ChatOllama

# Ollama (local, free) for planner + validator
ollama_llm = ChatOllama(model="gemma3:1b", temperature=0)

# Gemini (paid) for generator
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    gemini_llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        temperature=0,
        google_api_key=os.getenv("GOOGLE_API_KEY"),
    )
except (ImportError, Exception) as e:
    gemini_llm = None
    print(f"Warning: Gemini LLM unavailable ({e}). Using Ollama fallback.")
