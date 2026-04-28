from __future__ import annotations

from abc import ABC
from pathlib import Path

from app.llm.gateway import LLMGateway
from app.models.seed import ResearchSeed


class BaseAgent(ABC):
    """Shared utilities for bounded LLM-backed agents."""

    prompt_name: str

    def __init__(self, *, gateway: LLMGateway) -> None:
        self.gateway = gateway
        self._prompt_path = (
            Path(__file__).resolve().parent.parent / "llm" / "prompts" / self.prompt_name
        )

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @property
    def route_name(self) -> str:
        return self.prompt_name.removesuffix(".txt")

    def load_prompt(self) -> str:
        return self._prompt_path.read_text(encoding="utf-8")

    def seed_prompt(self, seed: ResearchSeed) -> str:
        if not seed.domain:
            return seed.raw_text
        label = {
            "ecc_research": "ECC / defensive cryptography research",
            "smart_contract_audit": "smart-contract audit research",
        }.get(seed.domain, seed.domain)
        return f"Selected domain: {label}\nUser seed:\n{seed.raw_text}"

    def parse_labeled_sections(self, response: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {}
        current_label: str | None = None

        for raw_line in response.splitlines():
            line = raw_line.rstrip()
            if not line.strip():
                if current_label is not None:
                    sections[current_label].append("")
                continue

            if ":" in line and not line.startswith(("-", " ")):
                label, value = line.split(":", 1)
                current_label = label.strip().lower()
                sections[current_label] = [value.strip()] if value.strip() else []
                continue

            if current_label is not None:
                sections[current_label].append(line)

        return {
            key: "\n".join(value).strip()
            for key, value in sections.items()
            if "\n".join(value).strip()
        }
