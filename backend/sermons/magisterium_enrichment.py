from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from django.conf import settings
from pydantic import BaseModel, Field
from simpleai import SimpleAIException, run_prompt
from simpleai.exceptions import ModelResolutionError, SettingsError

from .magisterium_client import MagisteriumClient, MagisteriumCitation
from .models import StudyArtifact
from .openai_transcriber import CleanedTranscript
from .processing import (
    PermanentProcessingError,
    RetryableProcessingError,
    StudyArtifactResult,
)

logger = logging.getLogger(__name__)

MAGISTERIUM_ARTIFACT_KINDS = frozenset(
    {
        StudyArtifact.Kind.RELATED_SOURCES,
        StudyArtifact.Kind.DOCTRINAL_REVIEW,
    }
)

Severity = Literal["heretical", "borderline"]


class SearchQueryOutput(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=5)


class AssertionOutput(BaseModel):
    assertion: str = Field(min_length=1)
    why_review: str = Field(min_length=1)


class AssertionListOutput(BaseModel):
    assertions: list[AssertionOutput] = Field(default_factory=list, max_length=8)


class DoctrinalFindingOutput(BaseModel):
    assertion: str = Field(min_length=1)
    severity: Severity
    explanation: str = Field(min_length=1)
    citation_indexes: list[int] = Field(default_factory=list)


class DoctrinalFindingsOutput(BaseModel):
    findings: list[DoctrinalFindingOutput] = Field(default_factory=list, max_length=8)
    summary: str = Field(default="")


@dataclass(frozen=True)
class MagisteriumArtifacts:
    study_artifacts: tuple[StudyArtifactResult, ...]


class MagisteriumEnricher:
    def __init__(
        self,
        client: MagisteriumClient | None = None,
        runner: Callable[..., Any] = run_prompt,
    ):
        self.client = client or MagisteriumClient()
        self.runner = runner

    def enrich(self, transcript: CleanedTranscript) -> MagisteriumArtifacts:
        if not self.client.configured:
            logger.info("Skipping Magisterium enrichment: MAGISTERIUM_API_KEY unset.")
            return MagisteriumArtifacts(
                study_artifacts=(
                    _related_sources_artifact(()),
                    _doctrinal_review_artifact(
                        findings=(),
                        summary=(
                            "Doctrinal review was not available "
                            "(Magisterium API key not configured)."
                        ),
                        citations=(),
                    ),
                )
            )

        try:
            related = self._related_sources(transcript)
            doctrinal = self._doctrinal_review(transcript)
        except (PermanentProcessingError, RetryableProcessingError) as error:
            logger.warning("Magisterium enrichment failed: %s", error)
            return MagisteriumArtifacts(
                study_artifacts=(
                    _related_sources_artifact(()),
                    _doctrinal_review_artifact(
                        findings=(),
                        summary=(
                            "Doctrinal review and related sources were unavailable "
                            f"({error})."
                        ),
                        citations=(),
                    ),
                )
            )
        except Exception:
            logger.exception("Unexpected Magisterium enrichment failure.")
            return MagisteriumArtifacts(
                study_artifacts=(
                    _related_sources_artifact(()),
                    _doctrinal_review_artifact(
                        findings=(),
                        summary=(
                            "Doctrinal review and related sources were unavailable "
                            "due to an unexpected error."
                        ),
                        citations=(),
                    ),
                )
            )

        return MagisteriumArtifacts(study_artifacts=(related, doctrinal))

    def _related_sources(self, transcript: CleanedTranscript) -> StudyArtifactResult:
        queries = self._search_queries(transcript)
        hits = []
        seen: set[str] = set()
        for query in queries:
            for hit in self.client.search(query, num_results=4, category="auto"):
                key = hit.title.casefold()
                if key in seen:
                    continue
                seen.add(key)
                hits.append(
                    {
                        "title": hit.title,
                        "author": hit.author,
                        "year": hit.year,
                        "excerpt": hit.excerpt,
                        "source_url": hit.source_url,
                        "category": hit.category,
                        "query": query,
                    }
                )
                if len(hits) >= 8:
                    break
            if len(hits) >= 8:
                break
        return _related_sources_artifact(tuple(hits))

    def _doctrinal_review(self, transcript: CleanedTranscript) -> StudyArtifactResult:
        assertions = self._candidate_assertions(transcript)
        if not assertions:
            return _doctrinal_review_artifact(
                findings=(),
                summary=(
                    "No assertions were flagged as heretical or borderline "
                    "relative to Catholic teaching."
                ),
                citations=(),
            )

        assertion_block = "\n".join(
            f"{index}. {item.assertion}\n   Why review: {item.why_review}"
            for index, item in enumerate(assertions, start=1)
        )
        prompt = f"""
You are reviewing sermon assertions for consistency with the Catholic Church's
Magisterium. Be careful, charitable, and precise. Do not invent citations —
ground every concern in Catholic magisterial or scholarly sources available to you.

Only flag assertions that are heretical or borderline (ambiguous / potentially
misleading / in tension with Catholic teaching). Omit orthodox or merely
incomplete pastoral language.

For each flagged assertion, explain the concern and cite specific documents.

Assertions from the sermon:
{assertion_block}
""".strip()
        chat = self.client.chat(prompt)
        findings = self._structure_doctrinal_findings(
            chat.content,
            chat.citations,
            assertions,
        )
        if not findings:
            return _doctrinal_review_artifact(
                findings=(),
                summary=(
                    chat.content.strip()
                    or (
                        "No assertions were flagged as heretical or borderline "
                        "relative to Catholic teaching."
                    )
                ),
                citations=chat.citations,
            )
        return _doctrinal_review_artifact(
            findings=findings,
            summary="",
            citations=chat.citations,
        )

    def _search_queries(self, transcript: CleanedTranscript) -> tuple[str, ...]:
        prompt = f"""
Extract three to five concise natural-language search queries a Catholic
reader could use to find magisterial or scholarly sources for further study
of this sermon. Prefer topics, doctrines, and questions the sermon raises —
not the preacher's name or local anecdotes.

Transcript:
<transcript>
{transcript.text[:12000]}
</transcript>
""".strip()
        try:
            output = self.runner(
                prompt,
                model=settings.SERMON_ARTIFACT_MODEL,
                output_format=SearchQueryOutput,
                reasoning_level=settings.SERMON_ARTIFACT_REASONING_LEVEL,
            )
        except (SettingsError, ModelResolutionError, SimpleAIException):
            fallback = " ".join(transcript.text.split())[:240]
            return (fallback,) if fallback else ("Catholic teaching on the Gospel",)
        queries = tuple(
            " ".join(query.split())[:1024]
            for query in output.queries
            if query.strip()
        )
        return queries or ("Catholic teaching related to this Gospel sermon",)

    def _candidate_assertions(
        self,
        transcript: CleanedTranscript,
    ) -> tuple[AssertionOutput, ...]:
        prompt = f"""
From the sermon transcript, extract up to eight specific theological or moral
assertions that a careful Catholic reviewer should check against Church teaching.
Prefer claims about God, sacraments, salvation, morality, Scripture, Tradition,
authority, or the Church. Quote or closely paraphrase the sermon's wording.
If the sermon makes no such claims, return an empty list.

Transcript:
<transcript>
{transcript.text[:12000]}
</transcript>
""".strip()
        try:
            output = self.runner(
                prompt,
                model=settings.SERMON_ARTIFACT_MODEL,
                output_format=AssertionListOutput,
                reasoning_level=settings.SERMON_ARTIFACT_REASONING_LEVEL,
            )
        except (SettingsError, ModelResolutionError, SimpleAIException):
            return ()
        return tuple(
            AssertionOutput(
                assertion=item.assertion.strip(),
                why_review=item.why_review.strip(),
            )
            for item in output.assertions
            if item.assertion.strip()
        )

    def _structure_doctrinal_findings(
        self,
        chat_content: str,
        citations: tuple[MagisteriumCitation, ...],
        assertions: tuple[AssertionOutput, ...],
    ) -> tuple[dict[str, Any], ...]:
        citation_block = "\n".join(
            f"[{index}] {citation.document_title}"
            f"{f' ({citation.document_author})' if citation.document_author else ''}"
            f"{f' §{citation.document_reference}' if citation.document_reference else ''}"
            f"\n{citation.cited_text}"
            for index, citation in enumerate(citations)
        ) or "(no citations returned)"
        assertion_block = "\n".join(
            f"- {item.assertion}" for item in assertions
        )
        prompt = f"""
Convert the Magisterium review below into structured findings.
Only include assertions that are heretical or borderline. Use citation_indexes
referring to the numbered citations (0-based). If nothing is problematic,
return an empty findings list and a short summary saying so.

Original assertions:
{assertion_block}

Magisterium review:
{chat_content}

Citations:
{citation_block}
""".strip()
        try:
            output = self.runner(
                prompt,
                model=settings.SERMON_ARTIFACT_MODEL,
                output_format=DoctrinalFindingsOutput,
                reasoning_level=settings.SERMON_ARTIFACT_REASONING_LEVEL,
            )
        except (SettingsError, ModelResolutionError, SimpleAIException):
            if not chat_content.strip():
                return ()
            return (
                {
                    "assertion": assertions[0].assertion if assertions else "Sermon claims",
                    "severity": "borderline",
                    "explanation": chat_content.strip(),
                    "citations": [_citation_dict(citation) for citation in citations],
                },
            )

        findings: list[dict[str, Any]] = []
        for item in output.findings:
            selected = [
                _citation_dict(citations[index])
                for index in item.citation_indexes
                if 0 <= index < len(citations)
            ]
            if not selected and citations:
                selected = [_citation_dict(citation) for citation in citations[:2]]
            findings.append(
                {
                    "assertion": item.assertion.strip(),
                    "severity": item.severity,
                    "explanation": item.explanation.strip(),
                    "citations": selected,
                }
            )
        return tuple(findings)


def without_magisterium_artifacts(
    artifacts: tuple[StudyArtifactResult, ...],
) -> tuple[StudyArtifactResult, ...]:
    return tuple(
        artifact
        for artifact in artifacts
        if artifact.kind not in MAGISTERIUM_ARTIFACT_KINDS
    )


def _related_sources_artifact(sources: tuple[dict[str, Any], ...]) -> StudyArtifactResult:
    return StudyArtifactResult(
        kind=StudyArtifact.Kind.RELATED_SOURCES,
        content=json.dumps({"sources": list(sources)}, ensure_ascii=False),
    )


def _doctrinal_review_artifact(
    *,
    findings: tuple[dict[str, Any], ...],
    summary: str,
    citations: tuple[MagisteriumCitation, ...],
) -> StudyArtifactResult:
    payload = {
        "findings": list(findings),
        "summary": summary.strip(),
        "citations": [_citation_dict(citation) for citation in citations],
    }
    return StudyArtifactResult(
        kind=StudyArtifact.Kind.DOCTRINAL_REVIEW,
        content=json.dumps(payload, ensure_ascii=False),
    )


def _citation_dict(citation: MagisteriumCitation) -> dict[str, str]:
    return {
        "document_title": citation.document_title,
        "document_author": citation.document_author,
        "document_year": citation.document_year,
        "document_reference": citation.document_reference,
        "cited_text": citation.cited_text,
        "source_url": citation.source_url,
    }
