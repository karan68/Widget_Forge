import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # LLM - Groq (primary, fast cloud inference)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")

    # LLM - Google Gemini (fallback)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # LLM - Ollama local (last resort)
    OLLAMA_ENDPOINT: str = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "mistral")

    # LLM provider priority: groq → gemini → ollama
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")  # auto, groq, gemini, ollama

    # LLM - OpenAI/Azure (optional)
    AZURE_OPENAI_ENDPOINT: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    AZURE_OPENAI_API_KEY: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    AZURE_OPENAI_DEPLOYMENT: str = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Google (for Google Calendar/Gmail)
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI: str = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/callback/google")

    # ADO
    ADO_ORG: str = os.getenv("ADO_ORG", "")
    ADO_PROJECT: str = os.getenv("ADO_PROJECT", "")
    ADO_PAT: str = os.getenv("ADO_PAT", "")

    # GitHub
    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME", "")

    # RapidAPI (Cricket, etc.)
    RAPIDAPI_KEY: str = os.getenv("RAPIDAPI_KEY", "")

    # WeatherAPI.com
    WEATHERAPI_KEY: str = os.getenv("WEATHERAPI_KEY", "")

    # NewsData.io
    NEWSDATA_KEY: str = os.getenv("NEWSDATA_KEY", "")

    # Serpstack (Google Search)
    SERPSTACK_KEY: str = os.getenv("SERPSTACK_KEY", "")

settings = Settings()
