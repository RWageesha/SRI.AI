# SRI.AI - Sinhala Offline Chatbot (Ollama + Streamlit)

SRI.AI is a simple Sinhala chatbot that runs fully offline using Ollama and a Streamlit web UI. It uses local UTF-8 text files for conversation examples and knowledge.

## Features

- 100% offline execution (no internet API calls)
- Local LLM inference with Ollama (any local model)
- Streamlit chat UI
- Sinhala Unicode input/output (UTF-8)
- Session-based chat history
- Clean and focused prompt design

## Project Structure

```
SRI-AI/
├── app.py
├── knowledge.txt
├── conversations.txt
├── requirements.txt
└── README.md
```

## 1. Prerequisites

- Windows, Linux, or macOS
- Python 3.10+
- Ollama installed locally

## 2. Install Ollama

1. Download from: https://ollama.com/download
2. Verify:
   - `ollama --version`

## 3. Download an Ollama Model

```powershell
ollama pull llama3.2:3b
```

You can use any model you have locally. Update the model name in the sidebar.

## 4. Setup Python Environment

```powershell
cd d:\Repos\SRI.AI
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## 5. Run Offline

```powershell
ollama serve
streamlit run app.py
```

Open the local URL shown in the terminal, usually:
- http://localhost:8501

## 6. Local Data Files

### conversations.txt
Example human-like Sinhala conversations:

```
User: ඔබ කොහොමද?
Assistant: මම හොඳින් ඉන්නවා! ඔබට කොහොමද?
```

### knowledge.txt
Short Sinhala knowledge facts (IT, Maths, general):

```
Python යනු ප්‍රෝග්‍රැමින් භාෂාවකි.
Algorithm යනු ගැටළුවක් විසඳන පියවර මාලාවකි.
```

Both files are loaded using UTF-8 encoding.

## 7. Offline Verification Checklist

1. Turn off Wi-Fi or disconnect internet.
2. Ensure the model is already pulled.
3. Run:
   - `ollama serve`
   - `streamlit run app.py`
4. Chat in Sinhala and verify responses.

## 8. Important Constraints Satisfied

- No internet APIs
- No translation pipelines
- No external databases
- Sinhala-only output enforced by prompt
