"""Streamlit app for offline Sinhala Hybrid RAG chatbot."""

from __future__ import annotations

import base64
import html
import json
from datetime import datetime
from pathlib import Path
import re

import streamlit as st

from chatbot.hybrid_retriever import HybridResult, HybridRetriever
from chatbot.memory import SessionMemory
from chatbot.ollama import OllamaClient
from chatbot.prompt import FALLBACK_ANSWER, build_prompt


PROJECT_ROOT = Path(__file__).resolve().parent
PAGE_ICON_PATH = PROJECT_ROOT / "Iconlogo.png"
HEADER_LOGO_PATH = PROJECT_ROOT / "Namelogo.png"
MAIN_UI_LOGO_PATH = PROJECT_ROOT / "Full logo.png"
USER_AVATAR_PATH = PROJECT_ROOT / "user.png"
HEADER_SETTINGS_ICON_PATH = PROJECT_ROOT / "Setting_Icon.png"
CHAT_SEND_ICON_PATH = PROJECT_ROOT / "Send_Icon.png"
CHAT_HISTORY_DIR = PROJECT_ROOT / "chat_history"

REFUSAL_PATTERNS: tuple[str, ...] = (
    "the context does not provide",
    "context does not provide",
    "cannot generate an answer",
    "cannot answer from the provided context",
    "provided context does not",
    "insufficient information in the context",
)

PROMPT_LEAK_PATTERNS: tuple[str, ...] = (
    "user question",
    "context:",
    "[json",
    "[text",
    "උපරිම අක්ෂර",
    "පිළිතුර අනිවාර්යයෙන්",
    "පළමු වාක්‍ය",
    "දෙවන වාක්‍ය",
    "සිංහලෙන් පමණක්",
)

QUERY_NOISE_TOKENS: set[str] = {
    "කියන්නේ",
    "මොකක්ද",
    "මොනවද",
    "මොනවාද",
    "කොහොමද",
    "ද",
    "ද?",
    "the",
    "what",
    "is",
    "are",
}

QUERY_ALIASES: dict[str, str] = {
    "os": "operating system ඔපරේටින් පද්ධතිය",
    "ai": "artificial intelligence",
    "ml": "machine learning",
}

MODEL_FAMILIES: tuple[str, str, str] = ("gemma", "llama", "mistral")

DIRECT_JSON_SCORE_THRESHOLD = 0.58
DIRECT_JSON_FOCUS_WEIGHT = 0.05
DIRECT_JSON_MIN_FOCUS = 1.2
MIN_BRIEF_SENTENCES = 4
MAX_BRIEF_SENTENCES = 8
MAX_BRIEF_CHARS = 1600


@st.cache_data(show_spinner=False)
def load_header_logo_data_uri() -> str | None:
    """Load header logo PNG and return a data URI."""
    if HEADER_LOGO_PATH.exists() and HEADER_LOGO_PATH.is_file():
        data = HEADER_LOGO_PATH.read_bytes()
        encoded = base64.b64encode(data).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    # Fallback for alternate folders/names.
    search_dirs = [
        PROJECT_ROOT,
        PROJECT_ROOT / "assets",
        PROJECT_ROOT / "static",
        PROJECT_ROOT / "images",
        PROJECT_ROOT / "Images",
    ]

    candidates: list[Path] = []
    seen: set[Path] = set()
    for directory in search_dirs:
        if not directory.exists() or not directory.is_dir():
            continue
        for pattern in ("*logo*.png", "*sri*.png", "*.png"):
            for path in sorted(directory.glob(pattern)):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                candidates.append(path)

    if not candidates:
        return None

    data = candidates[0].read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@st.cache_data(show_spinner=False)
def load_settings_icon_data_uri() -> str | None:
    """Load settings icon PNG and return a data URI."""
    if not HEADER_SETTINGS_ICON_PATH.exists() or not HEADER_SETTINGS_ICON_PATH.is_file():
        return None

    data = HEADER_SETTINGS_ICON_PATH.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@st.cache_data(show_spinner=False)
def load_main_ui_logo_data_uri() -> str | None:
    """Load main branding full-logo PNG and return a data URI."""
    if not MAIN_UI_LOGO_PATH.exists() or not MAIN_UI_LOGO_PATH.is_file():
        return None

    data = MAIN_UI_LOGO_PATH.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@st.cache_data(show_spinner=False)
def load_user_avatar_data_uri() -> str | None:
    """Load user avatar PNG and return a data URI."""
    if not USER_AVATAR_PATH.exists() or not USER_AVATAR_PATH.is_file():
        return None

    data = USER_AVATAR_PATH.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@st.cache_data(show_spinner=False)
def load_send_icon_data_uri() -> str | None:
    """Load chat send icon PNG and return a data URI."""
    if not CHAT_SEND_ICON_PATH.exists() or not CHAT_SEND_ICON_PATH.is_file():
        return None

    data = CHAT_SEND_ICON_PATH.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@st.cache_resource(show_spinner=False)
def get_retriever(data_signature: tuple[int, int, int]) -> HybridRetriever:
    """Load hybrid retriever once per Streamlit worker."""
    _ = data_signature
    return HybridRetriever(project_root=PROJECT_ROOT, rebuild=False)


@st.cache_resource(show_spinner=False)
def get_ollama() -> OllamaClient:
    """Load Ollama HTTP client once per Streamlit worker."""
    return OllamaClient()


def build_data_signature() -> tuple[int, int, int]:
    """Create cache key from knowledge/docs/index file state."""
    tracked_files: list[Path] = [
        PROJECT_ROOT / "data" / "knowledge.json",
        PROJECT_ROOT / "vectorstore" / "json_index.faiss",
        PROJECT_ROOT / "vectorstore" / "text_index.faiss",
    ]
    tracked_files.extend(sorted((PROJECT_ROOT / "data" / "documents").glob("*.txt")))

    existing = [path for path in tracked_files if path.exists()]
    if not existing:
        return (0, 0, 0)

    latest_mtime = int(max(path.stat().st_mtime for path in existing))
    total_size = int(sum(path.stat().st_size for path in existing))
    return (latest_mtime, len(existing), total_size)


def generate_session_id() -> str:
    """Create a unique session ID for each chat thread."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def has_user_messages(chat_log: list[dict[str, str]]) -> bool:
    """Return True if chat contains at least one user message."""
    return any(item.get("role") == "user" and item.get("content", "").strip() for item in chat_log)


def save_session_history(session_id: str, chat_log: list[dict[str, str]]) -> None:
    """Persist a chat session when at least one user message exists."""
    if not session_id or not has_user_messages(chat_log):
        return

    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_id": session_id,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "messages": chat_log,
    }
    session_path = CHAT_HISTORY_DIR / f"{session_id}.json"
    session_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_session_history(session_id: str) -> list[dict[str, str]]:
    """Load chat messages for a previously saved session."""
    session_path = CHAT_HISTORY_DIR / f"{session_id}.json"
    if not session_path.exists() or not session_path.is_file():
        return []

    try:
        payload = json.loads(session_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    messages = payload.get("messages", [])
    if not isinstance(messages, list):
        return []

    cleaned: list[dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            cleaned.append({"role": role, "content": content})
    return cleaned


def rebuild_memory_from_chat(memory: SessionMemory, chat_log: list[dict[str, str]]) -> None:
    """Rehydrate short-term memory from loaded chat history."""
    memory.clear()
    for item in chat_log:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            memory.add(role, content)


def list_saved_sessions() -> list[dict[str, str]]:
    """Return saved sessions sorted by most recent update time."""
    if not CHAT_HISTORY_DIR.exists() or not CHAT_HISTORY_DIR.is_dir():
        return []

    sessions: list[dict[str, str]] = []
    for session_path in sorted(CHAT_HISTORY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        session_id = session_path.stem
        preview = ""
        try:
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            messages = payload.get("messages", [])
            if isinstance(messages, list):
                for item in messages:
                    if isinstance(item, dict) and item.get("role") == "user":
                        preview = str(item.get("content", "")).strip()
                        break
        except (json.JSONDecodeError, OSError):
            preview = ""

        preview_short = (preview[:32] + "...") if len(preview) > 32 else preview
        label = f"{session_id} | {preview_short}" if preview_short else session_id
        sessions.append({"session_id": session_id, "label": label})

    return sessions


def render_chat_message(role: str, text: str) -> None:
    """Render a styled chat bubble for user/assistant messages."""
    safe_text = html.escape(text).replace("\n", "<br>")

    if role == "user":
        row_class = "sri-chat-row-user"
        avatar_class = "sri-chat-avatar-user"
        bubble_class = "sri-chat-bubble-user"
        avatar_label = "You"
        avatar_html = (
            f'<img class="sri-chat-avatar-img" src="{user_avatar_data_uri}" alt="User" />'
            if user_avatar_data_uri
            else avatar_label
        )
    else:
        row_class = "sri-chat-row-assistant"
        avatar_class = "sri-chat-avatar-assistant"
        bubble_class = "sri-chat-bubble-assistant"
        avatar_label = "AI"
        avatar_html = avatar_label

    st.markdown(
        f"""
        <div class="sri-chat-row {row_class}">
            <div class="sri-chat-avatar {avatar_class}">{avatar_html}</div>
            <div class="sri-chat-bubble {bubble_class}">{safe_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_grounded_backup_answer(result: HybridResult) -> str:
    """Build a context-only Sinhala answer when the model returns fallback."""
    focused = narrow_result_to_primary_topic(result)
    parts: list[str] = []
    fingerprints: list[str] = []

    if focused.json_hits:
        top_json = focused.json_hits[0].content.strip()
        json_key = _fingerprint_text(top_json)
        if top_json and _is_distinct_piece(json_key, fingerprints):
            parts.append(top_json)
            fingerprints.append(json_key)

    for hit in focused.text_hits[:2]:
        content = hit.content.strip()
        content_key = _fingerprint_text(content)
        if content and _is_distinct_piece(content_key, fingerprints):
            parts.append(content)
            fingerprints.append(content_key)

    if not parts:
        return FALLBACK_ANSWER

    return make_brief_answer(clean_answer_text("\n\n".join(parts)), focused)


def _split_sentences(text: str) -> list[str]:
    """Split Sinhala/English text into simple sentence units."""
    normalized = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    if not normalized:
        return []

    # Sinhala output usually ends with . ! ? even when mixed with English terms.
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]
    return sentences if sentences else [normalized]


def _candidate_explanatory_sentences(result: HybridResult | None) -> list[str]:
    """Collect candidate explanatory sentences from retrieval evidence."""
    if result is None:
        return []

    candidate_blocks: list[str] = []
    candidate_blocks.extend(hit.content for hit in result.text_hits[:2])
    candidate_blocks.extend(hit.content for hit in result.json_hits[:2])

    sentences: list[str] = []
    fingerprints: list[str] = []
    for block in candidate_blocks:
        for sentence in _split_sentences(block):
            key = _fingerprint_text(sentence)
            if len(key) < 10 or not _is_distinct_piece(key, fingerprints):
                continue
            sentences.append(sentence)
            fingerprints.append(key)

    return sentences


def make_brief_answer(answer: str, result: HybridResult | None = None) -> str:
    """Constrain answers to short, readable responses."""
    if answer.strip() == FALLBACK_ANSWER:
        return FALLBACK_ANSWER

    cleaned = clean_answer_text(answer)
    sentences = _split_sentences(cleaned)
    if not sentences:
        return cleaned

    if len(sentences) < MIN_BRIEF_SENTENCES:
        existing_fingerprints = [_fingerprint_text(sentence) for sentence in sentences if sentence.strip()]
        for candidate in _candidate_explanatory_sentences(result):
            key = _fingerprint_text(candidate)
            if len(key) < 10 or not _is_distinct_piece(key, existing_fingerprints):
                continue
            sentences.append(candidate)
            existing_fingerprints.append(key)
            if len(sentences) >= MIN_BRIEF_SENTENCES:
                break

    brief = " ".join(sentences[:MAX_BRIEF_SENTENCES]).strip()
    if len(brief) <= MAX_BRIEF_CHARS:
        return brief

    trimmed = brief[:MAX_BRIEF_CHARS].rsplit(" ", 1)[0].strip()
    if not trimmed:
        trimmed = brief[:MAX_BRIEF_CHARS].strip()
    if trimmed and trimmed[-1] not in ".!?":
        trimmed += "."
    return trimmed


def build_direct_topic_answer(result: HybridResult) -> str | None:
    """Return concise top-topic answer when JSON retrieval is highly confident."""
    if not result.json_hits:
        return None

    top_json = result.json_hits[0]
    if top_json.score < DIRECT_JSON_SCORE_THRESHOLD:
        return None

    concise = make_brief_answer(top_json.content, result)
    return concise if concise else None


def _normalize_text_for_match(text: str) -> str:
    """Normalize Sinhala/English text for lightweight lexical matching."""
    normalized = text.lower()
    for alias, expansion in QUERY_ALIASES.items():
        normalized = re.sub(rf"\\b{re.escape(alias)}\\b", f" {expansion} ", normalized)
    normalized = re.sub(r"[^0-9a-z\u0D80-\u0DFF\s]", " ", normalized)
    return " ".join(normalized.split())


def _query_tokens(question: str) -> list[str]:
    """Extract useful lexical tokens from the user query."""
    normalized = _normalize_text_for_match(question)
    tokens = [token for token in normalized.split() if len(token) >= 2 and token not in QUERY_NOISE_TOKENS]
    return tokens


def _query_focus_score(tokens: list[str], evidence_text: str) -> float:
    """Score how strongly the query focuses on a specific evidence text."""
    if not tokens:
        return 0.0

    evidence = _normalize_text_for_match(evidence_text)
    score = 0.0
    for token in tokens:
        if token not in evidence:
            continue
        if re.search(r"[a-z]", token):
            score += 1.4
        elif len(token) >= 5:
            score += 1.0
        else:
            score += 0.6
    return score


def _rerank_json_hits(question: str, json_hits: list) -> list:
    """Re-rank JSON hits by retrieval score plus query-focus evidence."""
    if not json_hits:
        return []

    tokens = _query_tokens(question)
    if not tokens or len(json_hits) == 1:
        return list(json_hits)

    scored_hits: list[tuple[float, object]] = []
    for rank, hit in enumerate(json_hits):
        focus = _query_focus_score(tokens, f"{hit.topic} {hit.content}")
        hybrid_score = hit.score + (focus * DIRECT_JSON_FOCUS_WEIGHT) - (0.01 * rank)
        scored_hits.append((hybrid_score, hit))

    scored_hits.sort(key=lambda item: item[0], reverse=True)
    return [hit for _, hit in scored_hits]


def _compose_context(json_hits: list, text_hits: list) -> str:
    """Compose prompt context from selected JSON and text hits."""
    context_parts: list[str] = []
    if json_hits:
        context_parts.append("[JSON දත්ත සාරාංශ]")
        for hit in json_hits:
            context_parts.append(f"මාතෘකාව: {hit.topic}")
            context_parts.append(f"තොරතුර: {hit.content}")

    if text_hits:
        context_parts.append("\n[TEXT දත්ත විස්තර]")
        for hit in text_hits:
            context_parts.append(f"මූලාශ්‍රය: {hit.source}")
            context_parts.append(f"මාතෘකාව: {hit.topic}")
            context_parts.append(f"අන්තර්ගතය: {hit.content}")

    return "\n".join(context_parts).strip()


def narrow_result_to_primary_topic(result: HybridResult, question: str = "") -> HybridResult:
    """Keep only the dominant topic to avoid mixed-topic responses."""
    json_hits = _rerank_json_hits(question, result.json_hits) if question else list(result.json_hits)

    topic_scores: dict[str, float] = {}
    for hit in json_hits:
        topic_scores[hit.topic] = topic_scores.get(hit.topic, 0.0) + hit.score
    for hit in result.text_hits:
        topic_scores[hit.topic] = topic_scores.get(hit.topic, 0.0) + hit.score

    if len(topic_scores) <= 1:
        if question:
            context = _compose_context(json_hits, result.text_hits)
            return HybridResult(context=context, json_hits=json_hits, text_hits=result.text_hits)
        return result

    if question and json_hits:
        primary_topic = json_hits[0].topic
    else:
        primary_topic = max(topic_scores.items(), key=lambda item: item[1])[0]

    json_hits = [hit for hit in json_hits if hit.topic == primary_topic][:2]
    text_hits = [hit for hit in result.text_hits if hit.topic == primary_topic][:3]

    context = _compose_context(json_hits, text_hits)
    return HybridResult(context=context, json_hits=json_hits, text_hits=text_hits)


def is_direct_answer_safe(question: str, result: HybridResult) -> bool:
    """Check whether direct JSON answering is aligned with the user query."""
    if not result.json_hits:
        return False

    top_json = result.json_hits[0]
    if top_json.score < DIRECT_JSON_SCORE_THRESHOLD:
        return False

    tokens = _query_tokens(question)
    if not tokens:
        return top_json.score >= 0.60

    top_focus = _query_focus_score(tokens, f"{top_json.topic} {top_json.content}")
    if top_focus >= DIRECT_JSON_MIN_FOCUS:
        return True

    if len(result.json_hits) == 1:
        return top_json.score >= 0.72

    runner_up = result.json_hits[1]
    runner_up_focus = _query_focus_score(tokens, f"{runner_up.topic} {runner_up.content}")
    return top_focus > runner_up_focus and top_json.score >= 0.68


def is_retrieval_relevant(question: str, result: HybridResult) -> bool:
    """Return True when retrieval evidence is strong enough for answering."""
    if not result.json_hits and not result.text_hits:
        return False

    top_json = result.json_hits[0].score if result.json_hits else 0.0
    top_text = result.text_hits[0].score if result.text_hits else 0.0
    top_score = max(top_json, top_text)

    if top_score >= 0.72:
        return True

    tokens = _query_tokens(question)
    if not tokens:
        return top_score >= 0.62

    evidence_parts: list[str] = []
    evidence_parts.extend(hit.topic for hit in result.json_hits)
    evidence_parts.extend(hit.topic for hit in result.text_hits)
    evidence_parts.extend(hit.content for hit in result.json_hits[:2])
    evidence_parts.extend(hit.content for hit in result.text_hits[:2])
    evidence = _normalize_text_for_match(" ".join(evidence_parts))

    match_count = sum(1 for token in tokens if token in evidence)
    coverage = match_count / max(1, len(tokens))

    if coverage >= 0.42 and top_score >= 0.30:
        return True
    if coverage >= 0.30 and top_score >= 0.40:
        return True
    return False


def _fingerprint_text(text: str) -> str:
    """Create a compact fingerprint for de-duplication."""
    normalized = _normalize_text_for_match(text)
    return re.sub(r"\s+", "", normalized)


def _single_char_token_ratio(text: str) -> float:
    """Return ratio of single-character tokens in a response."""
    tokens = re.findall(r"\S+", text)
    if not tokens:
        return 0.0
    single_chars = sum(1 for token in tokens if len(token) == 1)
    return single_chars / len(tokens)


def _sinhala_char_ratio(text: str) -> float:
    """Estimate Sinhala character ratio among letters to detect garbling."""
    letters = re.findall(r"[A-Za-z\u0D80-\u0DFF]", text)
    if not letters:
        return 0.0
    sinhala_letters = sum(1 for ch in letters if "\u0D80" <= ch <= "\u0DFF")
    return sinhala_letters / len(letters)


def _is_distinct_piece(candidate: str, existing: list[str]) -> bool:
    """Check whether candidate text is sufficiently different from existing pieces."""
    if not candidate:
        return False
    for item in existing:
        if not item:
            continue
        if candidate == item:
            return False
        if len(candidate) >= 24 and candidate in item:
            return False
        if len(item) >= 24 and item in candidate:
            return False
    return True


def clean_answer_text(answer: str) -> str:
    """Remove repeated/overlapping lines from generated Sinhala output."""
    lines = [line.strip() for line in answer.splitlines()]
    cleaned_lines: list[str] = []
    fingerprints: list[str] = []

    for line in lines:
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        # Strip common markdown formatting leaks before de-duplication.
        line = re.sub(r"^#{1,6}\s*", "", line)
        line = re.sub(r"^\s*(?:[-*•]+|\d+[.)])\s+", "", line)
        line = line.replace("**", "").replace("__", "").strip('"“”')
        if not line:
            continue

        key = _fingerprint_text(line)
        if len(key) >= 10 and not _is_distinct_piece(key, fingerprints):
            continue

        cleaned_lines.append(line)
        if len(key) >= 10:
            fingerprints.append(key)

    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned or answer.strip()


def remove_question_echo(answer: str, question: str) -> str:
    """Drop leading sentences that mostly restate the user question."""
    # Remove exact question echo prefix if model starts by repeating the query.
    answer = answer.strip()
    question = question.strip().strip('"“”')
    if question:
        escaped_question = re.escape(question)
        answer = re.sub(
            rf'^\s*["“”]?\s*{escaped_question}\s*[?.,:;\-]*\s*',
            "",
            answer,
            count=1,
            flags=re.IGNORECASE,
        ).strip()

    sentences = _split_sentences(answer)
    if not sentences:
        return answer

    q_tokens = _query_tokens(question)
    if not q_tokens:
        return answer

    kept: list[str] = []
    for sentence in sentences:
        sentence_norm = _normalize_text_for_match(sentence)
        if not sentence_norm:
            continue

        overlap = sum(1 for token in q_tokens if token in sentence_norm)
        ratio = overlap / max(1, len(q_tokens))

        # Skip sentence if it mostly echoes the question and adds little information.
        if ratio >= 0.72 and len(sentence_norm.split()) <= max(8, len(q_tokens) + 3):
            continue
        kept.append(sentence)

    return " ".join(kept).strip() if kept else answer


def is_weak_fallback(answer: str) -> bool:
    """Detect model outputs that effectively collapse to fallback text."""
    normalized = answer.replace('"', "").strip()
    lowered = " ".join(re.split(r"\s+", normalized.lower()))
    if normalized == FALLBACK_ANSWER:
        return True
    if FALLBACK_ANSWER in normalized and len(normalized) <= len(FALLBACK_ANSWER) + 50:
        return True
    if any(pattern in lowered for pattern in REFUSAL_PATTERNS):
        return True
    if any(pattern in lowered for pattern in PROMPT_LEAK_PATTERNS):
        return True

    # Reject heavy repetition that often appears in malformed generations.
    if re.search(r"(\b\S+\b)(?:\s+\1){3,}", lowered):
        return True

    # Reject answers containing too many instruction-like quotes.
    if normalized.count('"') >= 2 and len(normalized) < 420:
        return True

    return False


def is_low_quality_answer(answer: str, result: HybridResult) -> bool:
    """Detect malformed or weakly grounded answers that should be replaced."""
    normalized = _normalize_text_for_match(answer)
    if len(normalized) < 18:
        return True

    # Reject markdown-style heading/list formatting in final answer text.
    if re.search(r"(^|\n)\s*(#{1,6}\s+|[-*]\s+|\d+\.\s+)", answer):
        return True

    # Reject noisy quoted fragments that usually indicate prompt leakage.
    quote_count = answer.count('"') + answer.count("“") + answer.count("”")
    if quote_count >= 4:
        return True

    # Reject tokenized/gibberish outputs with too many single-character tokens.
    if len(answer) >= 80 and _single_char_token_ratio(answer) >= 0.22:
        return True

    # Prefer Sinhala-heavy responses; treat low Sinhala ratio as malformed.
    if len(answer) >= 120 and _sinhala_char_ratio(answer) < 0.28:
        return True

    # Penalize answers with too much repetition.
    if re.search(r"(\b\S+\b)(?:\s+\1){3,}", normalized):
        return True

    sentences = _split_sentences(answer)
    if len(sentences) < 2 and len(normalized) < 60:
        return True

    tokens = [token for token in normalized.split() if len(token) >= 2 and token not in QUERY_NOISE_TOKENS]
    if not tokens:
        return True

    # Reject low-diversity text where few tokens are repeated excessively.
    token_counts: dict[str, int] = {}
    for token in tokens:
        token_counts[token] = token_counts.get(token, 0) + 1
    if len(tokens) >= 16:
        unique_ratio = len(token_counts) / len(tokens)
        max_token_ratio = max(token_counts.values()) / len(tokens)
        if unique_ratio < 0.42 or max_token_ratio > 0.20:
            return True

    evidence_parts: list[str] = []
    evidence_parts.extend(hit.topic for hit in result.json_hits)
    evidence_parts.extend(hit.content for hit in result.json_hits[:2])
    evidence_parts.extend(hit.topic for hit in result.text_hits)
    evidence_parts.extend(hit.content for hit in result.text_hits[:2])
    evidence = _normalize_text_for_match(" ".join(evidence_parts))

    overlap = sum(1 for token in tokens if token in evidence)
    coverage = overlap / max(1, len(tokens))
    return coverage < 0.23


def find_cached_answer(chat_log: list[dict[str, str]], question: str) -> str | None:
    """Disable cache reuse to avoid repeating previously wrong answers."""
    _ = chat_log
    _ = question
    return None


def build_generation_model_preferences(selected_model: str) -> list[str]:
    """Build preferred model list with stable default to Gemma."""
    requested = selected_model.strip()
    ordered = [requested] if requested else []

    # Keep generation stable by defaulting to Gemma first.
    if not any(name.lower().startswith("gemma") for name in ordered):
        ordered.append("gemma")

    deduped: list[str] = []
    seen: set[str] = set()
    for name in ordered:
        key = name.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(name.strip())
    return deduped


def get_installed_models_safe(client: OllamaClient) -> list[str]:
    """Return installed model names with compatibility fallbacks."""
    try:
        list_models = getattr(client, "list_models", None)
        if callable(list_models):
            models = list_models()
            if isinstance(models, list):
                return [str(model).strip() for model in models if str(model).strip()]
    except Exception:
        pass

    try:
        tags_fn = getattr(client, "_tags", None)
        if callable(tags_fn):
            tags = tags_fn() or {}
            raw = tags.get("models", []) if isinstance(tags, dict) else []
            models: list[str] = []
            for item in raw:
                if isinstance(item, dict) and item.get("name"):
                    models.append(str(item["name"]).strip())
            return [model for model in models if model]
    except Exception:
        pass

    return []


def generate_answer_with_available_client(
    client: OllamaClient,
    prompt: str,
    selected_model: str,
) -> tuple[str, str, list[str]]:
    """Generate answer using multi-model API when available, else single-model fallback."""
    generate_multi = getattr(client, "generate_multi", None)
    if callable(generate_multi):
        answer, used_model, tried_models = generate_multi(
            prompt=prompt,
            preferred_models=build_generation_model_preferences(selected_model),
        )
        return answer, used_model, tried_models

    # Backward compatibility for older OllamaClient implementations.
    model = selected_model.strip() or "gemma"
    answer = client.generate(prompt=prompt, model=model)
    return answer, model, [model]


st.set_page_config(
    page_title="SRI.AI – Offline Sinhala Chatbot",
    page_icon=str(PAGE_ICON_PATH) if PAGE_ICON_PATH.exists() else "🤖",
    layout="wide",
)

if "memory" not in st.session_state:
    st.session_state.memory = SessionMemory(max_messages=10)
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "model_name" not in st.session_state:
    st.session_state.model_name = "gemma"
if "active_session_id" not in st.session_state:
    st.session_state.active_session_id = generate_session_id()

logo_data_uri = load_header_logo_data_uri()
settings_icon_data_uri = load_settings_icon_data_uri()
main_ui_logo_data_uri = load_main_ui_logo_data_uri()
user_avatar_data_uri = load_user_avatar_data_uri()
send_icon_data_uri = load_send_icon_data_uri()

st.markdown(
    """
    <style>
    .main .block-container {
        position: relative;
        padding-top: 0.35rem;
    }

    .sri-header-outer {
        width: 100%;
        margin-left: 0;
        margin-right: 0;
        margin-top: -0.25rem;
        margin-bottom: 1.05rem;
    }

    .sri-header-bar {
        display: flex;
        align-items: center;
        justify-content: flex-start;
        min-height: 92px;
        padding: 0.95rem 4.3rem 0.95rem 1.15rem;
        border: 1px solid rgba(120, 130, 150, 0.22);
        border-radius: 0;
        background: linear-gradient(90deg, #0f172a 0%, #1e293b 55%, #334155 100%);
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.18);
    }

    .sri-header-settings-popover-wrap {
        position: absolute;
        top: 1.12rem;
        right: 1.15rem;
        z-index: 40;
    }

    div[data-testid="stPopover"] > button {
        width: 42px;
        height: 42px;
        border-radius: 12px;
        border: 0;
        background: linear-gradient(145deg, #7c5cff 0%, #6958ff 100%);
        color: transparent;
        font-size: 0;
        box-shadow: 0 8px 20px rgba(104, 88, 255, 0.45);
    }

    div[data-testid="stPopover"] > button:hover {
        filter: brightness(1.04);
    }

    div[data-testid="stPopover"] {
        margin: 0;
    }

    .sri-header-left {
        display: flex;
        align-items: center;
        gap: 0.55rem;
    }

    .sri-logo-dot {
        width: 0.8rem;
        height: 0.8rem;
        border-radius: 999px;
        background: #22d3ee;
        box-shadow: 0 0 12px rgba(34, 211, 238, 0.8);
    }

    .sri-logo-img {
        height: 2.65rem;
        width: auto;
        display: block;
        object-fit: contain;
    }

    .sri-logo-text {
        color: #f8fafc;
        font-size: 1.06rem;
        letter-spacing: 0.08em;
        font-weight: 700;
    }

    .sri-settings {
        position: relative;
    }

    .sri-settings-btn {
        width: 42px;
        height: 42px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        border: 0;
        border-radius: 12px;
        background: linear-gradient(145deg, #7c5cff 0%, #6958ff 100%);
        color: #eef2ff;
        font-size: 1.1rem;
        cursor: pointer;
        box-shadow: 0 8px 20px rgba(104, 88, 255, 0.45);
    }

    .sri-settings-icon {
        width: 22px;
        height: 22px;
        display: block;
        object-fit: contain;
    }

    .sri-settings-menu {
        position: absolute;
        right: 0;
        top: 50px;
        min-width: 210px;
        background: #0f172a;
        border: 1px solid rgba(125, 135, 155, 0.32);
        border-radius: 12px;
        padding: 0.65rem 0.8rem;
        color: #e2e8f0;
        z-index: 20;
        box-shadow: 0 12px 28px rgba(2, 6, 23, 0.5);
    }

    .sri-settings summary {
        list-style: none;
    }

    .sri-settings summary::-webkit-details-marker {
        display: none;
    }

    .sri-settings-menu-title {
        margin: 0 0 0.35rem 0;
        font-size: 0.92rem;
        font-weight: 600;
        color: #f8fafc;
    }

    .sri-settings-menu-note {
        margin: 0;
        font-size: 0.8rem;
        line-height: 1.35;
        color: #cbd5e1;
    }

    .sri-main-brand {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        gap: 0.35rem;
        margin: 0.4rem auto 1.15rem auto;
    }

    .sri-main-logo {
        width: min(360px, 78vw);
        height: auto;
        display: block;
        object-fit: contain;
        margin-bottom: 0.1rem;
    }

    .sri-main-title {
        margin: 0;
        font-size: clamp(1.45rem, 2.2vw, 2.2rem);
        font-weight: 700;
        letter-spacing: 0.01em;
    }

    .sri-main-caption {
        margin: 0;
        font-size: clamp(0.92rem, 1.1vw, 1.02rem);
        opacity: 0.88;
    }

    .sri-chat-row {
        display: flex;
        align-items: flex-end;
        gap: 0.55rem;
        margin: 0.3rem 0 0.75rem 0;
        animation: sriChatRise 0.22s ease-out;
    }

    .sri-chat-row-user {
        justify-content: flex-start;
        flex-direction: row-reverse;
    }

    .sri-chat-row-assistant {
        justify-content: flex-start;
    }

    .sri-chat-avatar {
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        flex-shrink: 0;
        overflow: hidden;
    }

    .sri-chat-avatar-img {
        width: 100%;
        height: 100%;
        border-radius: 999px;
        object-fit: cover;
        display: block;
    }

    .sri-chat-avatar-user {
        background: #000000;
        color: #eff6ff;
        box-shadow: 0 8px 18px rgba(14, 165, 233, 0.35);
    }

    .sri-chat-avatar-assistant {
        background: #000000;
        color: #e2e8f0;
        box-shadow: 0 8px 18px rgba(15, 23, 42, 0.3);
    }

    .sri-chat-bubble {
        max-width: min(840px, 76vw);
        padding: 0.74rem 0.9rem;
        border-radius: 14px;
        line-height: 1.5;
        word-break: break-word;
        font-size: 0.97rem;
        border: 1px solid transparent;
        box-shadow: 0 8px 22px rgba(15, 23, 42, 0.08);
    }

    .sri-chat-bubble-user {
        background: linear-gradient(135deg, #1d4ed8 0%, #0284c7 100%);
        color: #eff6ff;
        border-color: rgba(147, 197, 253, 0.35);
        border-bottom-right-radius: 6px;
    }

    .sri-chat-bubble-assistant {
        background: transparent;
        color: #e5e7eb;
        border: 0;
        box-shadow: none;
        padding: 0.15rem 0.1rem;
        border-radius: 0;
        max-width: min(900px, 82vw);
    }

    .sri-chat-row-assistant .sri-chat-avatar {
        display: none;
    }

    @keyframes sriChatRise {
        from {
            opacity: 0;
            transform: translateY(6px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1220 0%, #111c33 50%, #18253f 100%);
        border-right: 1px solid rgba(135, 152, 182, 0.28);
    }

    section[data-testid="stSidebar"] > div {
        background: transparent;
    }

    section[data-testid="stSidebar"] .block-container {
        padding-top: 1rem;
        padding-left: 0.85rem;
        padding-right: 0.85rem;
    }

    section[data-testid="stSidebar"] h3 {
        color: #f8fafc;
        letter-spacing: 0.02em;
        margin-bottom: 0.35rem;
    }

    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
        color: #cbd5e1;
    }

    section[data-testid="stSidebar"] .stButton > button {
        width: 100%;
        min-height: 42px;
        border-radius: 12px;
        border: 1px solid rgba(133, 154, 186, 0.35);
        background: linear-gradient(135deg, #1d4ed8 0%, #0ea5e9 100%);
        color: #f8fafc;
        font-weight: 600;
        box-shadow: 0 8px 20px rgba(14, 165, 233, 0.22);
        transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
    }

    section[data-testid="stSidebar"] .stButton > button:hover {
        transform: translateY(-1px);
        filter: brightness(1.04);
        box-shadow: 0 10px 24px rgba(14, 165, 233, 0.3);
    }

    section[data-testid="stSidebar"] .stButton > button:active {
        transform: translateY(0);
    }

    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
        scrollbar-width: thin;
        scrollbar-color: rgba(103, 132, 178, 0.8) transparent;
    }

    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar {
        width: 8px;
    }

    section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, rgba(59, 130, 246, 0.8), rgba(14, 165, 233, 0.8));
        border-radius: 10px;
    }

    @media (max-width: 760px) {
        .main .block-container {
            padding-top: 0.2rem;
        }

        .sri-header-bar {
            min-height: 84px;
            padding: 0.8rem 4rem 0.8rem 0.85rem;
        }

        .sri-header-settings-popover-wrap {
            top: 0.92rem;
            right: 0.85rem;
        }

        .sri-logo-img {
            height: 2.1rem;
        }

        .sri-main-logo {
            width: min(420px, 88vw);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if send_icon_data_uri:
    st.markdown(
        f"""
        <style>
        div[data-testid="stChatInput"] button {{
            width: 42px;
            height: 42px;
            border-radius: 12px;
            background-image: url("{send_icon_data_uri}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: 22px 22px;
        }}

        div[data-testid="stChatInput"] button svg {{
            opacity: 0;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

if settings_icon_data_uri:
    st.markdown(
        f"""
        <style>
        .sri-header-settings-popover-wrap div[data-testid="stPopover"] > button {{
            background-image: url("{settings_icon_data_uri}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: 22px 22px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

logo_html = (
    f'<img class="sri-logo-img" src="{logo_data_uri}" alt="SRI.AI logo" />'
    if logo_data_uri
    else '<div class="sri-logo-dot"></div><div class="sri-logo-text">SRI.AI</div>'
)
main_logo_html = (
    f'<img class="sri-main-logo" src="{main_ui_logo_data_uri}" alt="SRI.AI Full Logo" />'
    if main_ui_logo_data_uri
    else '<div class="sri-logo-text">SRI.AI</div>'
)
st.markdown(
    f"""
    <div class="sri-header-outer">
      <div class="sri-header-bar">
        <div class="sri-header-left">
          {logo_html}
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

retriever = get_retriever(build_data_signature())
ollama_client = get_ollama()
installed_models = get_installed_models_safe(ollama_client)

st.markdown('<div class="sri-header-settings-popover-wrap">', unsafe_allow_html=True)
with st.popover("⚙", use_container_width=False):
        st.subheader("පද්ධති තත්ත්වය")
        st.write(f"Ollama Running: {ollama_client.is_available()}")
        st.write(f"JSON Topics: {len(retriever.json_retriever.entries)}")
        st.write(f"Text Chunks: {len(retriever.text_retriever.chunks)}")
        st.write(f"Installed Models: {', '.join(installed_models) if installed_models else 'none'}")
        family_status = {
            family: any(model.lower().startswith(family) for model in installed_models)
            for family in MODEL_FAMILIES
        }
        st.write(
            "Model Families (gemma/llama/mistral): "
            + ", ".join(f"{key}={'yes' if value else 'no'}" for key, value in family_status.items())
        )
        st.text_input("Ollama Model", key="model_name")
st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
        f"""
        <div class="sri-main-brand">
            {main_logo_html}
            <h1 class="sri-main-title">SRI.AI – Offline Sinhala Chatbot</h1>
            <p class="sri-main-caption">OLLAMA සහ Streamlit භාවිතා කර නිර්මාණය කළ දේශීය AI සංවාද පද්ධතිය</p>
        </div>
        """,
        unsafe_allow_html=True,
)

with st.sidebar:
    st.subheader("Chat Sessions")
    if st.button("Start New Chat", use_container_width=True):
        save_session_history(st.session_state.active_session_id, st.session_state.chat_log)
        st.session_state.active_session_id = generate_session_id()
        st.session_state.memory.clear()
        st.session_state.chat_log = []
        st.rerun()

    st.caption(f"Current: {st.session_state.active_session_id}")
    st.markdown("### History")
    saved_sessions = list_saved_sessions()
    if not saved_sessions:
        st.caption("No saved sessions yet.")
    else:
        for session in saved_sessions:
            is_current = session["session_id"] == st.session_state.active_session_id
            button_label = session["label"] + (" (Current)" if is_current else "")
            if st.button(button_label, key=f"session_{session['session_id']}", use_container_width=True):
                loaded_chat = load_session_history(session["session_id"])
                st.session_state.active_session_id = session["session_id"]
                st.session_state.chat_log = loaded_chat
                rebuild_memory_from_chat(st.session_state.memory, loaded_chat)
                st.rerun()

for item in st.session_state.chat_log:
    render_chat_message(item["role"], item["content"])

if user_input := st.chat_input("ඔබේ ප්‍රශ්නය සිංහලෙන් ටයිප් කරන්න..."):
    user_text = user_input.strip()
    cached_answer = find_cached_answer(st.session_state.chat_log, user_text)
    used_generation_model = ""
    tried_generation_models: list[str] = []
    result: HybridResult | None = None

    st.session_state.chat_log.append({"role": "user", "content": user_text})
    st.session_state.memory.add("user", user_text)
    save_session_history(st.session_state.active_session_id, st.session_state.chat_log)

    render_chat_message("user", user_text)

    with st.spinner("සෙවීම සහ පිළිතුරු සකසමින්..."):
        if cached_answer is not None:
            answer = make_brief_answer(cached_answer)
        else:
            result = narrow_result_to_primary_topic(retriever.retrieve(user_text), question=user_text)
            if not result.context or not is_retrieval_relevant(user_text, result):
                answer = FALLBACK_ANSWER
            else:
                prompt = build_prompt(context=result.context, question=user_text)
                try:
                    answer, used_generation_model, tried_generation_models = generate_answer_with_available_client(
                        client=ollama_client,
                        prompt=prompt,
                        selected_model=st.session_state.model_name,
                    )
                except RuntimeError:
                    answer = FALLBACK_ANSWER

                if is_weak_fallback(answer):
                    if is_direct_answer_safe(user_text, result):
                        answer = build_direct_topic_answer(result) or build_grounded_backup_answer(result)
                    else:
                        answer = build_grounded_backup_answer(result)
                elif is_low_quality_answer(answer, result):
                    if is_direct_answer_safe(user_text, result):
                        answer = build_direct_topic_answer(result) or build_grounded_backup_answer(result)
                    else:
                        answer = build_grounded_backup_answer(result)

            answer = remove_question_echo(answer, user_text)
            answer = make_brief_answer(answer, result)
            if result is not None and (is_weak_fallback(answer) or is_low_quality_answer(answer, result)):
                answer = make_brief_answer(build_grounded_backup_answer(result), result)

    render_chat_message("assistant", answer)

    if cached_answer is None:
        with st.expander("Retrieved Context"):
            if used_generation_model:
                st.markdown(f"**Generation Model:** {used_generation_model}")
            if tried_generation_models:
                st.markdown(f"**Models Used:** {', '.join(tried_generation_models)}")

            if result.json_hits:
                st.markdown("**JSON Retrieval (Top 2):**")
                for idx, hit in enumerate(result.json_hits, start=1):
                    st.markdown(f"{idx}. {hit.topic} (score={hit.score:.3f})")
            else:
                st.markdown("JSON Retrieval: none")

            if result.text_hits:
                st.markdown("**Text Retrieval (Top 3):**")
                for idx, hit in enumerate(result.text_hits, start=1):
                    st.markdown(f"{idx}. {hit.source} / {hit.topic} (score={hit.score:.3f})")
            else:
                st.markdown("Text Retrieval: none")

    st.session_state.chat_log.append({"role": "assistant", "content": answer})
    st.session_state.memory.add("assistant", answer)
    save_session_history(st.session_state.active_session_id, st.session_state.chat_log)
