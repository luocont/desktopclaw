"""Data models for iterative web research."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ClaimType = Literal["fact", "opinion", "procedure"]
ClaimStatus = Literal["corroborated", "single_source", "conflicting", "pending"]
Relevance = Literal["high", "medium", "low"]
SourceType = Literal["official", "blog", "news", "forum", "unknown"]
Confidence = Literal["low", "medium", "high"]


@dataclass
class Claim:
    """A verifiable or attributable statement gathered from sources."""

    text: str
    type: ClaimType = "fact"
    sources: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    status: ClaimStatus = "pending"

    def normalized_text(self) -> str:
        return " ".join(self.text.lower().split())


@dataclass
class PageClaim:
    """Raw claim extracted from a single page."""

    text: str
    type: ClaimType = "fact"
    quote_hint: str = ""


@dataclass
class PageNote:
    """Summary of a single fetched page."""

    url: str
    title: str = ""
    relevance: Relevance = "medium"
    source_type: SourceType = "unknown"
    claims: list[PageClaim] = field(default_factory=list)
    summary: str = ""
    error: str | None = None


@dataclass
class ResearchState:
    """Working memory for an in-progress research session."""

    question: str
    round: int = 0
    pages_budget: int = 15
    max_pages: int = 15
    # Constraints supplied by the main agent's analysis (recency, region,
    # source preferences, scope limits). Steers planning + synthesis.
    constraints: str = ""
    searched_queries: list[str] = field(default_factory=list)
    read_urls: set[str] = field(default_factory=set)
    known_facts: list[Claim] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    disputed_claims: list[Claim] = field(default_factory=list)
    page_notes: list[PageNote] = field(default_factory=list)
    confidence: Confidence = "low"
    last_round_new_facts: int = 0

    def snapshot_for_llm(self) -> str:
        """Compact state summary for LLM prompts."""
        lines = [
            f"Question: {self.question}",
            f"Round: {self.round}",
            f"Pages remaining budget: {self.pages_budget}",
            f"Confidence: {self.confidence}",
            f"Searched queries: {', '.join(self.searched_queries) or 'none'}",
            f"Open questions: {self.open_questions or ['none']}",
        ]
        if self.constraints:
            lines.insert(1, f"Constraints: {self.constraints}")
        if self.known_facts:
            lines.append("Known facts:")
            for c in self.known_facts[:20]:
                lines.append(f"  - [{c.status}] {c.text} (domains: {', '.join(c.domains)})")
        if self.disputed_claims:
            lines.append("Disputed:")
            for c in self.disputed_claims[:10]:
                lines.append(f"  - {c.text}")
        return "\n".join(lines)


@dataclass
class ResearchReport:
    """Final output of a research session."""

    question: str
    markdown: str
    rounds_used: int = 0
    pages_read: int = 0
    confidence: Confidence = "low"
    source_urls: list[str] = field(default_factory=list)
