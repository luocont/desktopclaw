"""Rule-based and LLM-assisted cross-verification of research claims."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from loguru import logger

from desktopclaw.agent.research.state import (
    Claim,
    ClaimStatus,
    ClaimType,
    Confidence,
    PageClaim,
    PageNote,
    ResearchState,
)
from desktopclaw.providers.base import LLMProvider

_OPPOSITE_MARKERS = (
    ("supports", "does not support"),
    ("does not", "does"),
    ("cannot", "can"),
    ("no ", "yes "),
    ("not recommended", "recommended"),
)


def registrable_domain(url: str) -> str:
    """Extract a coarse registrable domain for source independence."""
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host
    except Exception:
        return url


def normalize_claim_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())


def claims_similar(a: str, b: str) -> bool:
    na, nb = normalize_claim_text(a), normalize_claim_text(b)
    if na == nb:
        return True
    if len(na) > 20 and len(nb) > 20 and (na in nb or nb in na):
        return True
    return False


def claims_conflict(a: str, b: str) -> bool:
    na, nb = normalize_claim_text(a), normalize_claim_text(b)
    for x, y in _OPPOSITE_MARKERS:
        if x in na and y in nb:
            return True
        if y in na and x in nb:
            return True
    return False


class ResearchVerifier:
    """Merge page notes into research state with cross-source validation."""

    def __init__(self, provider: LLMProvider, model: str):
        self.provider = provider
        self.model = model

    def apply_rules(self, state: ResearchState, round_notes: list[PageNote]) -> None:
        """Rule-based claim merge and status assignment."""
        state.last_round_new_facts = 0
        for note in round_notes:
            if note.error or not note.claims:
                continue
            domain = registrable_domain(note.url)
            for pc in note.claims:
                self._merge_claim(state, pc, note.url, domain)

    def _merge_claim(
        self,
        state: ResearchState,
        pc: PageClaim,
        url: str,
        domain: str,
    ) -> None:
        text = pc.text.strip()
        if not text:
            return

        claim_type: ClaimType = pc.type if pc.type in ("fact", "opinion", "procedure") else "fact"

        for existing in state.known_facts:
            if claims_similar(existing.text, text):
                if url not in existing.sources:
                    existing.sources.append(url)
                if domain not in existing.domains:
                    existing.domains.append(domain)
                existing.status = self._status_for_domains(existing.domains)
                if claims_conflict(existing.text, text):
                    existing.status = "conflicting"
                    if existing not in state.disputed_claims:
                        state.disputed_claims.append(existing)
                return

        for existing in state.known_facts:
            if claims_conflict(existing.text, text):
                disputed = Claim(
                    text=text,
                    type=claim_type,
                    sources=[url],
                    domains=[domain],
                    status="conflicting",
                )
                state.disputed_claims.append(disputed)
                state.known_facts.append(disputed)
                if f"Conflict: '{existing.text}' vs '{text}'" not in state.open_questions:
                    state.open_questions.append(
                        f"Conflict: '{existing.text}' vs '{text}' — find authoritative source"
                    )
                return

        new_claim = Claim(
            text=text,
            type=claim_type,
            sources=[url],
            domains=[domain],
            status=self._status_for_domains([domain]),
        )
        state.known_facts.append(new_claim)
        state.last_round_new_facts += 1

        if new_claim.status == "single_source" and claim_type == "fact":
            q = f"Verify single-source fact: {text}"
            if q not in state.open_questions:
                state.open_questions.append(q)

    @staticmethod
    def _status_for_domains(domains: list[str]) -> ClaimStatus:
        unique = list(dict.fromkeys(domains))
        if len(unique) >= 2:
            return "corroborated"
        return "single_source"

    async def llm_verify_round(
        self,
        state: ResearchState,
        round_notes: list[PageNote],
    ) -> None:
        """LLM-assisted verification and open-question update."""
        notes_text = self._format_round_notes(round_notes)
        if not notes_text:
            return

        prompt = f"""You are a research verifier. Cross-check new page summaries against known facts.

Research question: {state.question}

Current state:
{state.snapshot_for_llm()}

New page summaries this round:
{notes_text}

Respond with JSON only:
{{
  "open_questions": ["sub-questions still needing search"],
  "disputed": ["brief descriptions of unresolved conflicts"],
  "confidence": "low|medium|high",
  "remove_open_questions": ["questions now answered"]
}}"""

        try:
            response = await self.provider.chat_with_retry(
                messages=[
                    {"role": "system", "content": "You output valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                temperature=0.2,
                max_tokens=1024,
            )
            data = _parse_json(response.content or "")
            if not data:
                return

            for q in data.get("remove_open_questions", []):
                state.open_questions = [x for x in state.open_questions if x != q]

            for q in data.get("open_questions", []):
                if isinstance(q, str) and q not in state.open_questions:
                    state.open_questions.append(q)

            for d in data.get("disputed", []):
                if isinstance(d, str) and d not in state.open_questions:
                    state.open_questions.append(f"Disputed: {d}")

            conf = data.get("confidence")
            if conf in ("low", "medium", "high"):
                state.confidence = conf
        except Exception as e:
            logger.warning("LLM verify round failed: {}", e)

    async def verify_and_update(
        self,
        state: ResearchState,
        round_notes: list[PageNote],
    ) -> None:
        self.apply_rules(state, round_notes)
        await self.llm_verify_round(state, round_notes)

    @staticmethod
    def _format_round_notes(notes: list[PageNote]) -> str:
        parts: list[str] = []
        for n in notes:
            if n.error:
                parts.append(f"URL: {n.url} ERROR: {n.error}")
                continue
            claims = "; ".join(c.text for c in n.claims[:5])
            parts.append(
                f"URL: {n.url}\nTitle: {n.title}\nRelevance: {n.relevance}\n"
                f"Summary: {n.summary}\nClaims: {claims}"
            )
        return "\n\n".join(parts)


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import json_repair

            return json_repair.loads(text)
        except Exception:
            return None
