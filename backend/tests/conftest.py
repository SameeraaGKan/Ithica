import os

# Tests run offline: no local Ollama and no Gemini, so the canned/fallback path is what gets exercised.
os.environ.update({"OLLAMA_URL": "", "ORACLE_PROVIDERS": "gemini", "GEMINI_API_KEY": ""})
