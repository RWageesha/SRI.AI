# Sinhala Hybrid RAG Chatbot (Offline)

Complete Sinhala chatbot system using Hybrid RAG (JSON + Text), Streamlit UI, FAISS retrieval, and Ollama local inference.

## Assignment Coverage

- Fully offline capable at runtime
- Ollama local LLM inference (`http://localhost:11434/api/generate`)
- Streamlit chat interface
- Sinhala Unicode input/output
- In-session memory for recent conversation turns (last 10)
- Hybrid retrieval flow:
  1. JSON semantic retrieval (Top 2)
  2. Text semantic retrieval from selected topics (Top 3)
  3. Context merge and grounded generation

## Project Structure

```
project/
├── app.py
├── chatbot/
│   ├── hybrid_retriever.py
│   ├── json_retriever.py
│   ├── text_retriever.py
│   ├── embeddings.py
│   ├── prompt.py
│   ├── ollama.py
│   ├── memory.py
│   ├── build_indexes.py
│   └── test_queries.py
├── data/
│   ├── knowledge.json
│   └── documents/
│       ├── headache.txt
│       ├── stress.txt
│       └── ...
├── vectorstore/
│   ├── json_index.faiss
│   └── text_index.faiss
├── requirements.txt
└── README.md
```

## Offline Requirements

1. Ollama must be installed locally.
2. Gemma model must already exist locally.
3. Sentence-transformers embedding model must be locally available.

Runtime code uses local-only embedding loading by default (`EMBEDDING_LOCAL_ONLY=1`).

## Install

```powershell
pip install -r requirements.txt
```

## Run Ollama Offline

```powershell
ollama serve
ollama pull gemma
```

After model pull is completed once, usage is local/offline.

## Build FAISS Indexes

```powershell
python -m chatbot.build_indexes
```

This generates:

- `vectorstore/json_index.faiss`
- `vectorstore/text_index.faiss`

## Run Streamlit Chatbot

```powershell
streamlit run app.py --server.port 8501
```

Open:

- http://localhost:8501

## Prompt Policy

The exact assignment prompt is used in `chatbot/prompt.py` with strict fallback:

"මට ඒ පිළිබඳ ප්‍රමාණවත් තොරතුරු නොමැත"

## Testing (20 Sinhala Queries)

Run retrieval tests:

```powershell
python -m chatbot.test_queries
```

The script includes 20 Sinhala test cases and checks retrieval correctness by expected topic.

## Notes

- No keyword matching is used for retrieval.
- Full dataset is never sent to the model.
- Only retrieved context is sent to Ollama.
