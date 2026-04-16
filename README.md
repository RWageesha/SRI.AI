# SRI.AI - Sinhala Offline Chatbot (Ollama + Streamlit)

This project is a Sinhala chatbot that runs fully offline using:
- Python
- Ollama (local LLM inference)
- Streamlit (web UI)

## Features

- Sinhala input and output
- Fully offline execution (no cloud API)
- Session-based chat history
- Clear Chat button
- Unicode Sinhala text support
- Streaming response effect
- Basic error handling for Ollama/model issues

## 1. Prerequisites

- Windows, Linux, or macOS
- Python 3.10+
- Ollama installed locally

## 2. Install Ollama

### Windows
1. Download and install from: https://ollama.com/download
2. Open a terminal and verify:
   - `ollama --version`

## 3. Download a local model

Use one of these:
- `ollama pull llama3.2:3b`
- `ollama pull mistral:7b`

Tip: For lower latency on low-spec devices, use smaller models (for example 3B).

## 4. Setup Python environment

```powershell
cd d:\Repos\SRI.AI
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 5. Run Ollama (if not already running)

Ollama usually runs in the background service mode after installation.
If needed, start it with:

```powershell
ollama serve
```

## 6. Run Streamlit app

```powershell
streamlit run app.py
```

Open the local URL shown in terminal, usually:
- http://localhost:8501

## 7. Offline verification checklist

1. Turn off Wi-Fi or disconnect internet.
2. Ensure model is already pulled locally.
3. Run:
   - `ollama serve`
   - `streamlit run app.py`
4. Chat in Sinhala and verify responses continue working.

## 8. Example Sinhala prompts

See:
- `test_prompts.md`

## 9. Troubleshooting

- Error: Cannot connect to Ollama
  - Fix: Start Ollama service (`ollama serve`) and retry.
- Error: model not found
  - Fix: Pull the model:
    - `ollama pull llama3.2:3b`
- Slow response
  - Fix: Use a smaller model, close heavy apps, lower temperature.

## 10. Important constraints satisfied

- No OpenAI API
- No Hugging Face online API
- No internet dependency during runtime
- Sinhala-first prompt behavior
