"""LLM-backed mutation proposal generation with strict validation."""

from __future__ import annotations

import json
import logging
from typing import Protocol

from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from config.env import get_settings
from models.mutation import MutationProposal
from models.narrative_context import NarrativeContext

__all__ = [
    "LLMMutationParseError",
    "LLMMutationProposer",
    "LLMMutationProviderError",
    "LLMMutationSchemaError",
]

LOGGER = logging.getLogger(__name__)


class LLMMutationProposerError(RuntimeError):
    """Base class for typed LLM mutation-proposer failures."""


class LLMMutationProviderError(LLMMutationProposerError):
    """Raised when the underlying LLM provider cannot return a proposal."""


class LLMMutationParseError(LLMMutationProposerError):
    """Raised when provider output is not valid JSON text."""


class LLMMutationSchemaError(LLMMutationProposerError):
    """Raised when parsed output does not match the mutation proposal schema."""


class _MutationProposalProvider(Protocol):
    """Protocol for structured-output mutation proposal providers."""

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        """Generate a raw JSON proposal response for the supplied prompt."""
        ...


class _OpenAIMutationProposalProvider:
    """Generate mutation proposals with ChatOpenAI."""

    def __init__(self, *, model_name: str | None = None) -> None:
        settings = get_settings()
        self._client = ChatOpenAI(
            model=model_name or settings.openai_model,  # type: ignore[call-arg]  # LangChain's stub omits the runtime constructor signature.
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )

    def generate_mutation_proposal(self, *, prompt: str) -> str:
        """Return the raw text content from the LLM response."""

        response = self._client.invoke(prompt)
        content = getattr(response, "content", None)
        if not isinstance(content, str):
            raise LLMMutationProviderError(
                "mutation provider returned non-text content"
            )

        stripped_content = content.strip()
        if not stripped_content:
            raise LLMMutationProviderError("mutation provider returned empty content")

        return stripped_content


class LLMMutationProposer:
    """Produce mutation proposals from narrative context using an LLM."""

    def __init__(self, provider: _MutationProposalProvider | None = None) -> None:
        self._provider = provider

    def propose(self, narrative_context: NarrativeContext) -> MutationProposal:
        """Generate and validate one structured mutation proposal."""

        prompt = self._build_prompt(narrative_context)
        try:
            raw_response = self._provider_for_cycle().generate_mutation_proposal(
                prompt=prompt
            )
        except LLMMutationProviderError:
            raise
        except Exception as error:  # pragma: no cover - external provider boundary
            raise LLMMutationProviderError("mutation provider call failed") from error

        proposal = self._parse_proposal(raw_response)
        LOGGER.debug(
            "validated structured mutation proposal %s for session %s",
            proposal.decision_id,
            proposal.session_id,
        )
        return proposal

    def _provider_for_cycle(self) -> _MutationProposalProvider:
        if self._provider is None:
            LOGGER.debug("creating default OpenAI mutation proposal provider")
            self._provider = _OpenAIMutationProposalProvider()

        return self._provider

    def _build_prompt(self, narrative_context: NarrativeContext) -> str:
        schema_json = json.dumps(
            MutationProposal.model_json_schema(),
            sort_keys=True,
            separators=(",", ":"),
        )
        context_json = json.dumps(
            narrative_context.model_dump(mode="json"),
            sort_keys=True,
            separators=(",", ":"),
        )
        return (
            "You are an LLM mutation proposer for a narrative hypergraph.\n"
            "Return exactly one JSON object that validates against the MutationProposal schema.\n"
            "Do not include markdown, code fences, or commentary.\n"
            "\n"
            "AVAILABLE NODES (you MUST use only these node IDs):\n"
            f"  - previous_scene_node_id: {narrative_context.previous_scene_node_id}\n"
            f"  - current_scene_node_id: {narrative_context.current_scene_node_id}\n"
            "\n"
            "ACTION TYPE GUIDANCE:\n"
            "  - ADD_NODE: target_ids[0] = anchor node (parent to attach to). "
            "Use current_scene_node_id to branch from the current scene.\n"
            "  - ADD_EDGE: target_ids = [source_node_id, target_node_id]. "
            "Both must exist in available nodes above.\n"
            "  - REMOVE_EDGE: target_ids[0] = edge ID to remove. "
            "Use format: 'previous_scene_node_id->current_scene_node_id'\n"
            "  - REWRITE_NODE: target_ids[0] = node ID to rewrite. "
            "Use current_scene_node_id to rewrite the current scene.\n"
            "  - PRUNE_BRANCH: target_ids[0] = root node ID of branch to remove.\n"
            "  - NO_OP: target_ids can be empty or [actor_node_id].\n"
            "\n"
            "IMPORTANT: target_ids must ONLY contain node IDs that exist in the graph "
            "(from available nodes listed above). Do NOT invent new node IDs.\n"
            "\n"
            f"MutationProposal schema: {schema_json}\n"
            f"NarrativeContext: {context_json}"
        )

    def _parse_proposal(self, raw_response: str) -> MutationProposal:
        if not isinstance(raw_response, str):
            raise LLMMutationParseError("mutation proposal response must be text")

        proposal_text = raw_response.strip()
        if not proposal_text:
            raise LLMMutationParseError("mutation proposal response was empty")

        try:
            proposal_payload = json.loads(proposal_text)
        except json.JSONDecodeError as error:
            raise LLMMutationParseError(
                "mutation proposal response was not valid JSON"
            ) from error

        try:
            return MutationProposal.model_validate(proposal_payload)
        except ValidationError as error:
            raise LLMMutationSchemaError(
                "mutation proposal response did not match the schema"
            ) from error
