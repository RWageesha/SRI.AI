"""Ollama local inference client."""

from __future__ import annotations

import re
from typing import Any

import requests

from chatbot.prompt import FALLBACK_ANSWER


SINHALA_RE = re.compile(r"[\u0D80-\u0DFF]")


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
            payload = {
                "model": candidate,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": 220,
                    "top_p": 0.9,
                    "repeat_penalty": 1.1,
                },
            }
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                raise RuntimeError("Ollama server is not reachable") from exc

            if response.status_code == 200:
                text = str(response.json().get("response", "")).strip()
                return self._enforce_sinhala(text)

            last_error = f"{response.status_code}: {response.text}"

        raise RuntimeError(f"Ollama generation failed: {last_error}")

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
