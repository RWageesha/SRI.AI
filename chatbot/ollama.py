"""Ollama local inference client."""

from __future__ import annotations

import re
from typing import Any

import requests

from chatbot.prompt import FALLBACK_ANSWER


SINHALA_RE = re.compile(r"[\u0D80-\u0DFF]")

PROMPT_LEAK_MARKERS: tuple[str, ...] = (
    "context:",
    "user question",
    "[json",
    "[text",
    "උපරිම අක්ෂර",
    "පිළිතුර අනිවාර්යයෙන්",
    "පළමු වාක්‍ය",
    "දෙවන වාක්‍ය",
    "සිංහලෙන් පමණක්",
)


class OllamaClient:
    """Simple wrapper over Ollama generate API for offline local inference."""

    def __init__(self, base_url: str = "http://localhost:11434", timeout_seconds: int = 90) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _tags(self) -> dict[str, Any] | None:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=8)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            return None

    def is_available(self) -> bool:
        """Check whether local Ollama server is running."""
        return self._tags() is not None

    def list_models(self) -> list[str]:
        """Return installed local Ollama model names."""
        tags = self._tags()
        if tags is None:
            return []
        return [str(item.get("name", "")).strip() for item in tags.get("models", []) if item.get("name")]

    @staticmethod
    def _dedupe_names(names: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for name in names:
            key = name.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(name.strip())
        return deduped

    def _resolve_requested_models(self, requested_models: list[str]) -> list[str]:
        """Resolve user/model-prefix requests against installed model names."""
        installed = self.list_models()
        if not installed:
            return self._dedupe_names(requested_models)

        resolved: list[str] = []
        installed_lower = {name.lower(): name for name in installed}

        for requested in requested_models:
            key = requested.strip().lower()
            if not key:
                continue

            if key in installed_lower:
                resolved.append(installed_lower[key])
                continue

            # Prefix matching supports requests like: gemma, llama, mistral.
            matches = [name for name in installed if name.lower().startswith(key)]
            if matches:
                resolved.append(matches[0])

        return self._dedupe_names(resolved)

    def _post_generate(self, candidate: str, prompt: str, temperature: float) -> str:
        payload = {
            "model": candidate,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": 420,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            },
        }
        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout_seconds,
        )
        if response.status_code != 200:
            raise RuntimeError(f"{response.status_code}: {response.text}")

        raw = str(response.json().get("response", "")).strip()
        return self._enforce_sinhala(raw)

    @staticmethod
    def _score_candidate_answer(answer: str) -> float:
        """Score candidate outputs, preferring clean brief explanatory answers."""
        text = answer.strip()
        if not text:
            return -1.0

        lowered = " ".join(re.split(r"\s+", text.lower()))
        if any(marker in lowered for marker in PROMPT_LEAK_MARKERS):
            return -1.0
        if re.search(r"(\b\S+\b)(?:\s+\1){3,}", lowered):
            return -0.8
        if re.search(r"(^|\n)\s*(#{1,6}\s+|[-*]\s+|\d+\.\s+)", text):
            return -0.7

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        sentence_count = len(sentences)
        length = len(text)

        score = 0.0
        if sentence_count >= 4:
            score += 1.4
        elif sentence_count == 3:
            score += 1.0
        elif sentence_count == 2:
            score += 0.6
        elif sentence_count == 1:
            score += 0.2

        if 220 <= length <= 900:
            score += 1.1
        elif 130 <= length <= 1000:
            score += 0.6

        # Penalize low-diversity token repetition.
        tokens = re.findall(r"\S+", lowered)
        if len(tokens) >= 16:
            token_counts: dict[str, int] = {}
            for token in tokens:
                token_counts[token] = token_counts.get(token, 0) + 1
            unique_ratio = len(token_counts) / len(tokens)
            max_token_ratio = max(token_counts.values()) / len(tokens)
            if unique_ratio < 0.40 or max_token_ratio > 0.22:
                score -= 0.8

        # Slightly reward outputs that include actionable wording.
        for token in ("කරන්න", "යුතුය", "උපකාරී", "වැදගත්"):
            if token in text:
                score += 0.1

        return score

    def _resolve_model(self, requested: str = "gemma") -> list[str]:
        """Resolve model candidates while preferring gemma as required."""
        tags = self._tags()
        if tags is None:
            return [requested]

        installed = [str(item.get("name", "")).strip() for item in tags.get("models", []) if item.get("name")]
        if not installed:
            return [requested]

        lower_map = {name.lower(): name for name in installed}
        if requested.lower() in lower_map:
            return [lower_map[requested.lower()]]

        gemma_variants = [name for name in installed if name.lower().startswith("gemma")]
        ordered = [requested] + gemma_variants + [installed[0]]

        deduped: list[str] = []
        seen: set[str] = set()
        for item in ordered:
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def generate(self, prompt: str, model: str = "gemma", temperature: float = 0.1) -> str:
        """Generate grounded Sinhala answer from Ollama."""
        last_error = ""
        for candidate in self._resolve_model(model):
            try:
                return self._post_generate(candidate=candidate, prompt=prompt, temperature=temperature)
            except requests.RequestException as exc:
                raise RuntimeError("Ollama server is not reachable") from exc
            except RuntimeError as exc:
                last_error = str(exc)

        raise RuntimeError(f"Ollama generation failed: {last_error}")

    def generate_multi(self, prompt: str, preferred_models: list[str], temperature: float = 0.15) -> tuple[str, str, list[str]]:
        """Generate with multiple requested model families and return the best result."""
        model_requests = self._dedupe_names(preferred_models + ["gemma", "llama", "mistral"])
        candidates = self._resolve_requested_models(model_requests)
        if not candidates:
            raise RuntimeError("No matching Ollama models are installed")

        generated: list[tuple[str, str]] = []
        errors: list[str] = []

        for candidate in candidates:
            try:
                answer = self._post_generate(candidate=candidate, prompt=prompt, temperature=temperature)
                if answer and answer != FALLBACK_ANSWER:
                    score = self._score_candidate_answer(answer)
                    if score >= 0.0:
                        generated.append((candidate, answer))
                        # Use first good answer in preference order for stable behavior.
                        return answer, candidate, [model for model, _ in generated]
            except requests.RequestException as exc:
                raise RuntimeError("Ollama server is not reachable") from exc
            except RuntimeError as exc:
                errors.append(f"{candidate}: {exc}")

        if not generated:
            if errors:
                raise RuntimeError("; ".join(errors))
            raise RuntimeError("No valid output generated by selected models")

        # Safety net: this path is unlikely because first valid answer returns above.
        best_model, best_answer = generated[0]
        tried_models = [model for model, _ in generated]
        return best_answer, best_model, tried_models

    @staticmethod
    def _enforce_sinhala(answer: str) -> str:
        """Guardrail: return fallback when output is not Sinhala."""
        cleaned = OllamaClient._sanitize_generated_text(answer)
        if not cleaned:
            return FALLBACK_ANSWER
        if SINHALA_RE.search(cleaned) is None:
            return FALLBACK_ANSWER
        return cleaned

    @staticmethod
    def _sanitize_generated_text(answer: str) -> str:
        """Remove leaked prompt labels and retrieval headers from model output."""
        text = answer.strip()

        # Remove quoted prompt-instruction fragments leaked by some models.
        text = re.sub(
            r'["“][^"”\n]{0,220}(?:උපරිම අක්ෂර|පිළිතුර අනිවාර්යයෙන්|පළමු වාක්‍ය|දෙවන වාක්‍ය|User Question|Context)[^"”\n]*["”]',
            " ",
            text,
            flags=re.IGNORECASE,
        )

        for marker in (
            "පිළිතුර (සිංහලෙන් පමණක්):",
            "Final Answer (සිංහලෙන් පමණක්):",
            "Final Answer:",
            "Answer:",
        ):
            if marker in text:
                text = text.split(marker)[-1].strip()

        blocked_prefixes = (
            "ඔබ සිංහල",
            "කාර්ය නියමය",
            "ඔබගේ කාර්ය",
            "නීති:",
            "Context:",
            "User Question:",
            "[JSON",
            "[TEXT",
            "මූලාශ්‍රය:",
            "මාතෘකාව:",
            "තොරතුර:",
            "අන්තර්ගතය:",
        )

        blocked_fragments = (
            "උපරිම අක්ෂර",
            "පිළිතුර අනිවාර්යයෙන්",
            "පළමු වාක්‍ය",
            "දෙවන වාක්‍ය",
            "user question",
            "context:",
            "[json",
            "[text",
        )

        cleaned_lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line == "---":
                continue
            lowered = line.lower()
            if lowered.startswith("sure") or lowered.startswith("here is") or lowered.startswith("here's"):
                continue
            if line.startswith(blocked_prefixes):
                continue
            if any(fragment in lowered for fragment in blocked_fragments):
                continue
            if line.startswith("*") and (
                "Context" in line
                or "සිංහලෙන්" in line
                or "ප්‍රශ්නය" in line
                or "පිළිතුර" in line
            ):
                continue
            cleaned_lines.append(line)

        cleaned = "\n".join(cleaned_lines).strip()
        if cleaned:
            return cleaned
        return text
