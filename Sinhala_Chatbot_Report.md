# Sinhala Offline Chatbot Report

## Title
Sinhala Language Chatbot Running Fully Offline using Ollama and Streamlit

## 1. Introduction

### 1.1 What is a Chatbot?
A chatbot is a software system that accepts user text input and generates human-like responses.

### 1.2 Why a Sinhala Chatbot?
Most AI chat systems are English-focused. A Sinhala chatbot improves accessibility for Sinhala-speaking users in education, daily productivity, and local support tasks.

### 1.3 Importance of Offline AI
Offline AI is important for:
- Privacy (data stays on local machine)
- Reliability (works without internet)
- Low operational cost (no cloud API billing)
- Use in low-connectivity areas

## 2. System Architecture

### 2.1 Architecture Overview
User -> Streamlit UI -> Python Backend -> Ollama Local Model -> Response -> Streamlit UI

### 2.2 Components
- Streamlit UI: Captures Sinhala input and displays responses
- Python Backend: Maintains chat history and orchestrates inference calls
- Ollama Engine: Runs the local LLM (e.g., llama3.2:3b or mistral:7b)
- Session State: Stores message history during current session

## 3. Flowchart

Start
-> User enters Sinhala text
-> Python backend receives input
-> Add user message to session history
-> Send context + input to Ollama
-> Generate response (streamed)
-> Display response in Streamlit chat
-> Save assistant response in session history
-> Repeat until user exits

## 4. Code Explanation

### 4.1 Ollama Call
- The app uses the local Ollama Python client
- Endpoint: http://127.0.0.1:11434
- Chat is generated with stream=True to create typing effect

### 4.2 Streamlit UI
- st.chat_input for user input
- st.chat_message for rendering user/assistant messages
- Sidebar contains model selection and Clear Chat button

### 4.3 Chat History
- Messages are stored in st.session_state.messages
- History includes role and content for each turn
- Clear Chat resets session messages

### 4.4 Sinhala Enforcement
A Sinhala-only system prompt is included in every chat request so the assistant replies in Sinhala even if the user asks in another language.

## 5. Testing

### 5.1 Test Method
- Execute chatbot with internet disconnected
- Send 20 Sinhala prompts
- Verify Sinhala output and stable behavior

### 5.2 Sample Test Table

| Input | Output (Example) |
|---|---|
| ඔබ කොහොමද | මම හොඳින්, ඔබට ස්තුතියි |
| අද කාලගුණය | අද දින කාලගුණය සාමාන්‍යයෙන් උණුසුම් විය හැක |

Full 20 prompts are in test_prompts.md.

## 6. Screenshots

Include the following screenshots in final PDF:
1. Streamlit home screen
2. Sinhala conversation example
3. Clear Chat button usage
4. Model status in sidebar

## 7. Video Proof (Very Important)

Record a short demo video showing:
1. Ollama service running locally
2. Streamlit app running
3. Wi-Fi OFF (or network disconnected)
4. Sinhala question and Sinhala response

Video link:
- Add your video URL here

## 8. Constraints and Compliance

- No internet API used
- No OpenAI/HuggingFace cloud API
- Local-only inference via Ollama
- Sinhala-first responses
- Single report document can be exported as PDF (keep under 15 pages)

## 9. Conclusion

The developed system successfully demonstrates an offline Sinhala chatbot using local AI inference with Ollama and an interactive Streamlit interface. It supports Sinhala communication, session memory, and practical deployment in offline environments.
