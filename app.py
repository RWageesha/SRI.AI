import streamlit as st
import ollama


st.set_page_config(
    page_title="SRI.AI Sinhala Offline Chatbot",
    page_icon="💬",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --bg-1: #fff8ef;
        --bg-2: #f0f6ff;
        --accent: #0e7c86;
        --accent-2: #f39c12;
        --text-main: #1f2937;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 10%, rgba(14, 124, 134, 0.08), transparent 35%),
            radial-gradient(circle at 90% 20%, rgba(243, 156, 18, 0.10), transparent 40%),
            linear-gradient(135deg, var(--bg-1), var(--bg-2));
    }

    .main-title {
        color: var(--text-main);
        font-family: "Nirmala UI", "Noto Sans Sinhala", "Iskoola Pota", sans-serif;
        letter-spacing: 0.2px;
        margin-bottom: 0.2rem;
    }

    .sub-title {
        color: #4b5563;
        font-family: "Nirmala UI", "Noto Sans Sinhala", "Iskoola Pota", sans-serif;
        margin-top: 0;
        margin-bottom: 1.4rem;
    }

    .status-ok {
        padding: 0.6rem 0.9rem;
        border-radius: 10px;
        border: 1px solid #b8e0c0;
        background: #f0fff4;
        color: #166534;
        font-size: 0.95rem;
    }

    .status-err {
        padding: 0.6rem 0.9rem;
        border-radius: 10px;
        border: 1px solid #f2b8b8;
        background: #fff5f5;
        color: #991b1b;
        font-size: 0.95rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h1 class="main-title">SRI.AI - Sinhala Offline Chatbot</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-title">අන්තර්ජාලය නොමැතිව ක්‍රියාත්මක වන සිංහල කතාබහ පද්ධතිය</p>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Settings")
    model_name = st.text_input("Ollama Model", value="llama3.2:3b")
    temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=0.4, step=0.1)

    if st.button("Clear Chat", type="primary", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

client = ollama.Client(host="http://127.0.0.1:11434")


def check_ollama_status() -> tuple[bool, str]:
    try:
        response = client.list()
        models = response.get("models", [])
        model_names = [m.get("model", "") for m in models]

        if model_name in model_names:
            return True, f"Ollama is ready. Model found: {model_name}"
        return False, (
            f"Ollama is running, but model '{model_name}' is not downloaded. "
            f"Run: ollama pull {model_name}"
        )
    except Exception as exc:
        return False, (
            "Cannot connect to Ollama on http://127.0.0.1:11434. "
            "Start Ollama first. Error: " + str(exc)
        )


status_ok, status_message = check_ollama_status()
if status_ok:
    st.markdown(f'<div class="status-ok">{status_message}</div>', unsafe_allow_html=True)
else:
    st.markdown(f'<div class="status-err">{status_message}</div>', unsafe_allow_html=True)

system_prompt = (
    "ඔබ සිංහලෙන් පමණක් පිළිතුරු දෙන උපකාරක චැට්බොට් කෙනෙකි. "
    "පරිශීලකයා වෙනත් භාෂාවකින් ලියුවත් සිංහලෙන්ම පිළිතුරු දෙන්න. "
    "පිළිතුරු සරල, පැහැදිලි, සහ ගෞරවනීයව ලබා දෙන්න."
)

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


user_prompt = st.chat_input("ඔබේ පණිවිඩය සිංහලෙන් ටයිප් කරන්න...")

if user_prompt:
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)

    if not status_ok:
        assistant_text = (
            "සමාවන්න, Ollama සේවාව හෝ model එක සකස් කර නැහැ. "
            "කරුණාකර sidebar හි දක්වා ඇති උපදෙස් අනුගමනය කරන්න."
        )
        with st.chat_message("assistant"):
            st.markdown(assistant_text)
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
    else:
        with st.chat_message("assistant"):
            try:
                conversation = [{"role": "system", "content": system_prompt}] + st.session_state.messages

                def stream_response():
                    stream = client.chat(
                        model=model_name,
                        messages=conversation,
                        options={"temperature": temperature},
                        stream=True,
                    )
                    for chunk in stream:
                        text = chunk.get("message", {}).get("content", "")
                        if text:
                            yield text

                assistant_text = st.write_stream(stream_response())
            except Exception as exc:
                assistant_text = f"දෝෂයක් සිදු වුණා: {exc}"
                st.error(assistant_text)

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
