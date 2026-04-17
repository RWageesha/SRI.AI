from pathlib import Path
import base64
import json
import re
from datetime import datetime

import ollama
import streamlit as st


BASE_DIR = Path(__file__).parent
KNOWLEDGE_FILE = BASE_DIR / "knowledge.txt"
CONVERSATIONS_FILE = BASE_DIR / "conversations.txt"
CHAT_HISTORY_DIR = BASE_DIR / "chat_history"
ICON_FILE = BASE_DIR / "Images" / "Iconlogo.png"
HEADER_LOGO_FILE = BASE_DIR / "Images" / "Namelogo.png"
FULL_LOGO_FILE = BASE_DIR / "Images" / "Fulllogo.png"
SINHALA_RE = re.compile(r"[\u0D80-\u0DFF]")


def load_text_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def load_logo_base64(path: Path) -> str:
    if not path.exists():
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def ensure_chat_history_dir() -> None:
    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def list_chat_files() -> list[Path]:
    ensure_chat_history_dir()
    return sorted(CHAT_HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)


def create_chat_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def chat_file_path(chat_id: str) -> Path:
    return CHAT_HISTORY_DIR / f"{chat_id}.json"


def load_chat_history(chat_id: str) -> list[dict]:
    path = chat_file_path(chat_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_chat_history(chat_id: str, messages: list[dict]) -> None:
    ensure_chat_history_dir()
    path = chat_file_path(chat_id)
    path.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")


def build_conversation_examples(raw_text: str, max_pairs: int = 6) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    examples: list[str] = []
    current: list[str] = []

    for line in lines:
        if line.startswith("User:") or line.startswith("Assistant:"):
            current.append(line)
            if len(current) == 2:
                examples.append("\n".join(current))
                current = []
                if len(examples) >= max_pairs:
                    break

    return "\n\n".join(examples)


def build_system_prompt(conversation_examples: str, knowledge_text: str) -> str:
    instructions = (
        "ඔබ සිංහලයෙන් පමණක් පිළිතුරු දෙන උපකාරක චැට්බොට් කෙනෙකි. "
        "පිළිතුරු කෙටි, පැහැදිලි, ගෞරවනීය වශයෙන් ලබා දෙන්න. "
        "පරිශීලකයා වෙනත් භාෂාවකින් ලියුවත් සිංහලෙන්ම පිළිතුරු දෙන්න. "
        "පහත දැනුම් කට්ටලය හා සංවාද උදාහරණ මත පදනම්ව පිළිතුරු සකස් කරන්න. "
        "අර්ථ රහිත නැවතීම්, අසම්බන්ධ වාක්‍ය, හෝ වරක් වරක් සමාන වචන නැවත නැවත ලියීමෙන් වළකින්න."
    )

    sections = ["[System Instructions]", instructions]

    if conversation_examples:
        sections.extend(["\n[Conversation Examples]", conversation_examples])

    if knowledge_text:
        sections.extend(["\n[Knowledge Base]", knowledge_text])

    return "\n".join(sections)


def check_ollama_status(client: ollama.Client, model_name: str) -> tuple[bool, str]:
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


def normalize_text(text: str) -> str:
    return " ".join(text.strip().split())


def sinhala_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    sinhala_count = sum(1 for ch in letters if SINHALA_RE.search(ch))
    return sinhala_count / len(letters)


def is_low_quality_response(text: str) -> bool:
    normalized = normalize_text(text)
    if len(normalized) < 8:
        return True
    if sinhala_ratio(normalized) < 0.6:
        return True
    tokens = normalized.split()
    if not tokens:
        return True
    max_ratio = max(tokens.count(token) for token in set(tokens)) / len(tokens)
    return max_ratio > 0.35


def rule_based_reply(prompt: str) -> str:
    text = normalize_text(prompt)
    if "නම" in text and "මොකක්" in text:
        return "මගේ නම SRI.AI."
    if "කොහොමද" in text:
        return "මම හොඳින් ඉන්නවා. ඔබට කොහොමද?"
    if "උදව්" in text:
        return "ඔව්, ඔබට අවශ්‍ය දේ පැහැදිලිව කියන්න."
    if "ස්තුතියි" in text:
        return "ඔබට ස්තූතියි."
    if "ඉංග්‍රීසි" in text:
        return "සමාවන්න, මම සිංහලෙන් පමණක් පිළිතුරු දෙන්නෙමි."
    return "කරුණාකර ඔබේ ප්‍රශ්නය පැහැදිලිව නැවත කියන්න."


st.set_page_config(
    page_title="SRI.AI Sinhala Offline Chatbot",
    page_icon=str(ICON_FILE),
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --bg: #f2f6f9;
        --card: #ffffff;
        --line: #d9e3eb;
        --text: #1f2937;
        --muted: #667085;
        --accent: #1ea3b1;
        --accent-dark: #1d4ed8;
        --accent-soft: #e8f8fb;
    }

    .stApp {
        background: var(--bg);
    }

    .block-container {
        padding-top: 0.4rem;
    }

    .topbar-anchor + div[data-testid="stHorizontalBlock"] {
        align-items: center;
        background: #ffffff;
        border-bottom: 1px solid var(--line);
        border-radius: 0 0 14px 14px;
        margin-bottom: 0.6rem;
        padding: 0.2rem 0.7rem;
        box-shadow: 0 6px 18px rgba(16, 24, 40, 0.04);
    }

    .topbar-anchor + div[data-testid="stHorizontalBlock"] > div:last-child {
        display: flex;
        justify-content: flex-end;
    }

    .topbar-logo img {
        height: 42px;
        width: auto;
        display: block;
    }

    .top-right-wrap {
        display: flex;
        justify-content: flex-end;
        align-items: center;
    }

    .settings-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: 12px;
        border: 1px solid #bde8ec;
        background: linear-gradient(135deg, #ddf6f8, #c9ecf1);
        font-size: 1.05rem;
        box-shadow: 0 6px 16px rgba(30, 163, 177, 0.14);
    }

    div[data-testid="stPopover"] > details > summary {
        border: 0 !important;
        background: transparent !important;
        padding: 0 !important;
    }

    .page-title {
        font-size: 0.95rem;
        color: var(--muted);
        margin: 0.25rem 0 0.7rem;
    }

    .panel {
        background: var(--card);
        border: 1px solid var(--line);
        border-radius: 20px;
        padding: 1rem;
        box-shadow: 0 10px 26px rgba(17, 24, 39, 0.05);
    }

    .panel-title {
        font-weight: 600;
        color: var(--text);
        margin-bottom: 0.6rem;
    }

    .start-chat-btn button {
        background: linear-gradient(120deg, #1ea3b1, #1d4ed8) !important;
        color: #ffffff !important;
        border: none !important;
    }

    .history-meta {
        padding: 0.18rem 0.1rem 0.75rem;
        border-bottom: 1px solid #eef3f7;
        margin-bottom: 0.55rem;
    }

    .history-item {
        padding: 0.7rem 0.6rem;
        border-radius: 12px;
        border: 1px solid transparent;
        margin-bottom: 0.5rem;
        transition: all 0.2s ease;
        text-align: left;
        width: 100%;
    }

    .history-item:hover {
        border-color: var(--line);
        background: #faf9ff;
    }

    .history-title {
        font-weight: 600;
        color: var(--text);
        font-size: 0.92rem;
    }

    .history-sub {
        color: var(--muted);
        font-size: 0.78rem;
    }

    .hero {
        text-align: center;
        padding: 2.4rem 1rem 1rem;
    }

    .hero .full-logo {
        width: 340px;
        max-width: 80%;
        margin: 0 auto 1.2rem;
    }

    .hero h2 {
        margin: 0;
        color: var(--text);
        font-size: 1.5rem;
    }

    .hero p {
        margin: 0.6rem auto 1.2rem;
        color: var(--muted);
        font-size: 1rem;
        max-width: 680px;
        line-height: 1.55;
    }

    .mini-brand {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        justify-content: center;
        margin-bottom: 0.4rem;
    }

    .mini-brand .icon {
        width: 38px;
        height: 38px;
        border-radius: 10px;
        background: linear-gradient(135deg, #e7fbff, #d9f0ff);
        display: inline-flex;
        align-items: center;
        justify-content: center;
    }

    .mini-brand .icon img {
        width: 24px;
        height: 24px;
        object-fit: contain;
    }

    .mini-brand .wordmark img {
        height: 34px;
        width: auto;
        object-fit: contain;
    }

    .chat-shell {
        min-height: 520px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    div[data-testid="stChatInput"] textarea {
        border-radius: 999px !important;
        border: 1px solid var(--line) !important;
        padding: 0.75rem 1rem !important;
        background: #fdfefe !important;
    }

    .sidebar-collapsed {
        padding: 0.4rem;
        display: flex;
        justify-content: center;
    }

    @media (max-width: 960px) {
        .topbar-logo img {
            height: 34px;
        }
        .hero .full-logo {
            width: 250px;
        }
        .hero h2 {
            font-size: 1.22rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

header_logo_b64 = load_logo_base64(HEADER_LOGO_FILE)
full_logo_b64 = load_logo_base64(FULL_LOGO_FILE)
icon_logo_b64 = load_logo_base64(ICON_FILE)
logo_html = (
    f"<img src='data:image/png;base64,{header_logo_b64}' alt='SRI.AI' />"
    if header_logo_b64
    else "SRI.AI"
)
wordmark_html = (
    f"<img src='data:image/png;base64,{header_logo_b64}' alt='SRI.AI wordmark' />"
    if header_logo_b64
    else "SRI.AI"
)
icon_html = (
    f"<img src='data:image/png;base64,{icon_logo_b64}' alt='SRI.AI icon' />"
    if icon_logo_b64
    else ""
)

model_name = "llama3.2:3b"
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.2
if "show_sidebar" not in st.session_state:
    st.session_state.show_sidebar = True

if "chat_id" not in st.session_state:
    st.session_state.chat_id = create_chat_id()
if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("<div class='topbar-anchor'></div>", unsafe_allow_html=True)
top_cols = st.columns([6, 1])
with top_cols[0]:
    st.markdown(f"<div class='topbar-logo'>{logo_html}</div>", unsafe_allow_html=True)
with top_cols[1]:
    st.markdown("<div class='top-right-wrap'>", unsafe_allow_html=True)
    with st.popover("⚙️", use_container_width=False):
        st.markdown("**Settings**")
        st.slider(
            "Temperature Level",
            min_value=0.0,
            max_value=1.0,
            step=0.05,
            value=st.session_state.temperature,
            key="temperature",
        )
        if st.button("Clear Session Chat History", use_container_width=True):
            st.session_state.messages = []
            save_chat_history(st.session_state.chat_id, st.session_state.messages)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='page-title'>Sinhala Offline Chatbot</div>", unsafe_allow_html=True)

ensure_chat_history_dir()
chat_files = list_chat_files()

client = ollama.Client(host="http://127.0.0.1:11434")
status_ok, status_message = check_ollama_status(client, model_name)

if status_ok:
    st.caption(status_message)
else:
    st.caption(status_message)

conversation_text = load_text_file(CONVERSATIONS_FILE)
knowledge_text = load_text_file(KNOWLEDGE_FILE)
examples_block = build_conversation_examples(conversation_text)
system_prompt = build_system_prompt(examples_block, knowledge_text)

if not conversation_text:
    st.warning("conversations.txt not found. Please add Sinhala conversation examples.")
if not knowledge_text:
    st.warning("knowledge.txt not found. Please add Sinhala knowledge entries.")

if st.session_state.show_sidebar:
    left_col, right_col = st.columns([1.1, 2.6], gap="large")
else:
    left_col, right_col = st.columns([0.34, 2.66], gap="large")

with left_col:
    st.markdown("<div class='panel'>", unsafe_allow_html=True)
    if st.session_state.show_sidebar:
        header_cols = st.columns([6, 1])
        with header_cols[0]:
            st.markdown(
                f"<div class='panel-title'>Previous Chats ({len(chat_files):02d})</div>",
                unsafe_allow_html=True,
            )
        with header_cols[1]:
            if st.button("☰", key="toggle_sidebar"):
                st.session_state.show_sidebar = not st.session_state.show_sidebar
                st.rerun()
    else:
        st.markdown("<div class='sidebar-collapsed'>", unsafe_allow_html=True)
        if st.button("☰", key="toggle_sidebar_compact"):
            st.session_state.show_sidebar = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.show_sidebar:
        st.markdown("<div class='start-chat-btn'>", unsafe_allow_html=True)
        if st.button("+ Start New Chat", use_container_width=True):
            st.session_state.chat_id = create_chat_id()
            st.session_state.messages = []
            save_chat_history(st.session_state.chat_id, st.session_state.messages)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

        for chat_path in chat_files[:8]:
            chat_id = chat_path.stem
            preview_messages = load_chat_history(chat_id)
            title = "New Chat"
            preview = ""
            for msg in preview_messages:
                if msg.get("role") == "user":
                    title = normalize_text(str(msg.get("content", "")))[:28] or "New Chat"
                    break
            for msg in preview_messages:
                if msg.get("role") == "assistant":
                    preview = normalize_text(str(msg.get("content", "")))[:40]
                    break

            timestamp = datetime.fromtimestamp(chat_path.stat().st_mtime).strftime("%d/%m/%Y %I:%M %p")

            if st.button(f"{title}", key=f"chat_{chat_id}", use_container_width=True):
                st.session_state.chat_id = chat_id
                st.session_state.messages = preview_messages
                st.rerun()

            st.markdown(
                f"<div class='history-meta history-sub'>{timestamp} • {preview}</div>",
                unsafe_allow_html=True,
            )

    st.markdown("</div>", unsafe_allow_html=True)

with right_col:
    st.markdown("<div class='panel chat-shell'>", unsafe_allow_html=True)
    if not st.session_state.messages:
        st.markdown(
            f"""
            <div class="hero">
                <div class="mini-brand">
                    <div class="icon">{icon_html}</div>
                    <div class="wordmark">{wordmark_html}</div>
                </div>
                <div class="full-logo"></div>
                <h2>Welcome to SRI.AI</h2>
                <p>
                    SRI.AI ඔබගේ සිංහල උපකාරක සහකාරයායි. ඔබට ලිවීම, අදහස් විමසීම,
                    හෝ මිතුරැ කතාබස් අවශ්‍ය නම්, පහත කොටුවෙන් ඔබේ ප්‍රශ්නය ඇතුළත් කරන්න.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if full_logo_b64:
            st.markdown(
                f"""
                <style>
                .hero .full-logo {{
                    background: url('data:image/png;base64,{full_logo_b64}') no-repeat center;
                    background-size: contain;
                    height: 160px;
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_prompt = st.chat_input("ඔබේ පණිවිඩය සිංහලෙන් ටයිප් කරන්න...")
    st.markdown("</div>", unsafe_allow_html=True)

if user_prompt:
    user_prompt = normalize_text(user_prompt)
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    save_chat_history(st.session_state.chat_id, st.session_state.messages)
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
        save_chat_history(st.session_state.chat_id, st.session_state.messages)
    else:
        history = st.session_state.messages[-6:]
        conversation = [{"role": "system", "content": system_prompt}] + history

        with st.chat_message("assistant"):
            response = client.chat(
                model=model_name,
                messages=conversation,
                options={"temperature": st.session_state.temperature},
                stream=False,
            )
            assistant_text = normalize_text(str(response.get("message", {}).get("content", "")))

            if is_low_quality_response(assistant_text):
                assistant_text = rule_based_reply(user_prompt)

            st.markdown(assistant_text)

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        save_chat_history(st.session_state.chat_id, st.session_state.messages)
