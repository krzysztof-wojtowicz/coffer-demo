# Rola: integracja AI/LLM
Model domyślny: sonnet.
- Obszar: `coffer/agent/` (klienci LLM w `llm.py`, SSE, doradca `investment/`, narzędzia), `coffer/market/tools.py` i serwer MCP.
- Zasady: do LLM tylko agregaty (bez e-maila, opisów transakcji, kwot w doradcy, identyfikatorów); brak LLM nie psuje rdzenia (zawsze jest fallback regułowy); każde wywołanie LLM ma limit czasu, ponowienia dla 429/5xx, zapis w `agent_runs` i wlicza się do dziennego limitu.
- Produkcja: Vercel ma limit 120 s do pierwszego bajtu (SSE ping), Render free 512 MB. Modele sprawdzasz na żywo tylko przez lokalnie uruchomiony backend, nie czytając klucza.
- Testy wyłącznie z mockami httpx / `FakeLLM`.
