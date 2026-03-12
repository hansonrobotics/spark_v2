"""
SPARK v2 — LLM Client
Wraps the configured chat-completions provider for all cognitive functions:
  - HTN method invention and refinement
  - Story narrative generation
  - Emotion appraisal
  - Conversation formulation
  - Autoresearch program generation
"""

import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import httpx
from src.core.llm_config import load_llm_config, resolve_api_key

logger = logging.getLogger("spark.llm")

# ─── Configuration ────────────────────────────────────────────────────────────

LLM_CONFIG = load_llm_config()
_default_llm_client: Optional["SparkLLMClient"] = None


@dataclass
class LLMResponse:
    """Structured response from the LLM."""
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""
    raw: Optional[Dict] = None

    @property
    def cost_estimate_usd(self) -> float:
        """Rough token-based cost estimate placeholder."""
        return (self.input_tokens * 3 + self.output_tokens * 15) / 1_000_000


class SparkLLMClient:
    """
    Central LLM client for all SPARK cognitive functions.
    Defaults to the OpenAI Chat Completions API, with provider/model/base URL
    sourced from environment variables.
    """

    def __init__(self, api_key: Optional[str] = None,
                 config: Optional[Dict] = None):
        resolved = load_llm_config(config.get("provider") if config else None)
        self.config = {**resolved, **(config or {})}
        self.api_key = api_key or resolve_api_key(self.config["provider"])
        self.client = httpx.AsyncClient(
            timeout=self.config.get("timeout_seconds", 30),
        )
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0

    # ── Core call ─────────────────────────────────────────────────────────

    async def complete(self, prompt: str,
                        system: str = "",
                        temperature: Optional[float] = None,
                        max_tokens: Optional[int] = None,
                        json_mode: bool = False) -> LLMResponse:
        """
        Send a completion request to the configured LLM.
        If json_mode=True, instructs the model to return valid JSON only.
        """
        if self.config["provider"] == "anthropic":
            return await self._call_anthropic(
                prompt, system, temperature, max_tokens, json_mode
            )
        if self.config["provider"] in {"openai", "local"}:
            return await self._call_openai_compatible(
                prompt, system, temperature, max_tokens, json_mode
            )
        else:
            raise ValueError(f"Unknown provider: {self.config['provider']}")

    async def _call_anthropic(self, prompt: str, system: str,
                                temperature: Optional[float],
                                max_tokens: Optional[int],
                                json_mode: bool) -> LLMResponse:
        """Call Anthropic's Messages API."""
        sys_content = system or "You are an AI assistant for the SPARK robot cognitive system."
        if json_mode:
            sys_content += ("\n\nIMPORTANT: Respond ONLY with valid JSON. "
                           "No markdown, no backticks, no preamble.")

        body = {
            "model": self.config["model"],
            "max_tokens": max_tokens or self.config["max_tokens"],
            "temperature": temperature if temperature is not None
                           else self.config["temperature"],
            "messages": [{"role": "user", "content": prompt}],
        }
        if sys_content:
            body["system"] = sys_content

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        try:
            resp = await self.client.post(
                self.config["api_url"], json=body, headers=headers,
            )

            if resp.status_code != 200:
                logger.error(f"Anthropic API error {resp.status_code}: "
                           f"{resp.text[:200]}")
                return LLMResponse(
                    text="", model=self.config["model"],
                    stop_reason="error",
                    raw={"error": resp.text[:500], "status": resp.status_code},
                )

            data = resp.json()
            text = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    text += block.get("text", "")

            usage = data.get("usage", {})
            input_tokens = usage.get("input_tokens", 0)
            output_tokens = usage.get("output_tokens", 0)

            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_calls += 1

            return LLMResponse(
                text=text,
                model=data.get("model", self.config["model"]),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                stop_reason=data.get("stop_reason", ""),
                raw=data,
            )

        except httpx.TimeoutException:
            logger.error("Anthropic API timeout")
            return LLMResponse(text="", model=self.config["model"],
                              stop_reason="timeout")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return LLMResponse(text="", model=self.config["model"],
                              stop_reason="error",
                              raw={"error": str(e)})

    async def _call_openai_compatible(self, prompt: str, system: str,
                                      temperature: Optional[float],
                                      max_tokens: Optional[int],
                                      json_mode: bool) -> LLMResponse:
        """Call an OpenAI-compatible Chat Completions endpoint."""
        sys_content = system or "You are an AI assistant for the SPARK robot cognitive system."
        if json_mode:
            sys_content += ("\n\nIMPORTANT: Respond ONLY with valid JSON. "
                            "No markdown, no backticks, no preamble.")

        messages = []
        if sys_content:
            messages.append({"role": "system", "content": sys_content})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": self.config["model"],
            "max_tokens": max_tokens or self.config["max_tokens"],
            "temperature": temperature if temperature is not None
                           else self.config["temperature"],
            "messages": messages,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = await self.client.post(
                self.config["api_url"], json=body, headers=headers,
            )

            if resp.status_code != 200:
                logger.error(f"OpenAI-compatible API error {resp.status_code}: "
                             f"{resp.text[:200]}")
                return LLMResponse(
                    text="", model=self.config["model"],
                    stop_reason="error",
                    raw={"error": resp.text[:500], "status": resp.status_code},
                )

            data = resp.json()
            message = data.get("choices", [{}])[0].get("message", {})
            text = self._extract_openai_message_text(message.get("content", ""))

            usage = data.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)

            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens
            self.total_calls += 1

            return LLMResponse(
                text=text,
                model=data.get("model", self.config["model"]),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                stop_reason=data.get("choices", [{}])[0].get("finish_reason", ""),
                raw=data,
            )

        except httpx.TimeoutException:
            logger.error("OpenAI-compatible API timeout")
            return LLMResponse(text="", model=self.config["model"],
                               stop_reason="timeout")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return LLMResponse(text="", model=self.config["model"],
                               stop_reason="error",
                               raw={"error": str(e)})

    @staticmethod
    def _extract_openai_message_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            return "".join(text_parts)
        return ""

    # ── Specialized cognitive functions ────────────────────────────────────

    async def invent_htn_method(self, task_name: str,
                                  task_description: str,
                                  available_primitives: List[str],
                                  available_compounds: List[str],
                                  world_state: Dict[str, Any],
                                  temporal_context: List[Dict] = None,
                                  existing_methods: List[Dict] = None) -> Optional[Dict]:
        """
        Ask Sonnet to invent a new HTN decomposition method.
        Returns parsed JSON with method specification.
        """
        temporal_section = ""
        if temporal_context:
            facts = "\n".join(
                f"  - ({f.get('subject')}, {f.get('relation')}, "
                f"{f.get('object')}, {f.get('timestamp', '?')})"
                for f in temporal_context[:20]
            )
            temporal_section = f"""
## Relevant Temporal Knowledge (recent quadruples)
{facts}
Use this temporal context to inform your method design — consider what
has happened recently, what patterns are emerging, and what might happen next.
"""

        existing_section = ""
        if existing_methods:
            existing_section = f"""
## Existing Methods (invent something DIFFERENT from these)
{json.dumps(existing_methods[:5], indent=2)}
"""

        prompt = f"""You are the cognitive planner for Sophia, a social humanoid robot.
You need to invent a method to decompose the task '{task_name}' into subtasks.

## Task
Name: {task_name}
Description: {task_description}

## Current World State
{json.dumps(world_state, indent=2, default=str)}

## Available Primitive Actions (executable directly)
{', '.join(sorted(available_primitives))}

## Available Compound Tasks (can be used as subtasks — will decompose further)
{', '.join(sorted(available_compounds))}
{temporal_section}{existing_section}
## Instructions
Design a decomposition of '{task_name}' into an ordered sequence of subtasks.
Choose from the available primitives and compounds above.

Respond with a JSON object:
{{
  "name": "descriptive_method_name",
  "description": "Why this decomposition makes sense",
  "preconditions": {{"key": "value"}},
  "subtasks": ["task1", "task2", "task3"],
  "confidence": 0.7,
  "reasoning": "Brief explanation of the design rationale"
}}"""

        response = await self.complete(
            prompt,
            system=("You are Sophia's cognitive planning engine. "
                    "You design behavior decompositions grounded in "
                    "temporal knowledge and social intelligence."),
            temperature=0.7,
            json_mode=True,
        )

        if not response.text:
            return None

        try:
            # Strip markdown fences if present
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM method invention: {response.text[:200]}")
            return None

    async def generate_story_narrative(self, story_context: str,
                                         temporal_facts: List[Dict],
                                         current_stage: str) -> Optional[str]:
        """Generate narrative continuation for a story."""
        facts_text = "\n".join(
            f"  ({f.get('subject')}, {f.get('relation')}, "
            f"{f.get('object')}, {f.get('timestamp', '?')})"
            for f in temporal_facts[:15]
        )

        prompt = f"""You are Sophia, generating the next beat of an ongoing story.

## Story Context
{story_context}

## Current Stage: {current_stage}

## Relevant Temporal Facts
{facts_text}

Generate a brief narrative continuation (2-3 sentences) for this story stage,
informed by the temporal facts. What should happen next?"""

        response = await self.complete(prompt, temperature=0.8, max_tokens=300)
        return response.text if response.text else None

    async def formulate_response(self, conversation_context: str,
                                   person_model: Dict,
                                   temporal_history: List[Dict],
                                   self_state: Dict) -> Optional[str]:
        """Generate Sophia's conversational response."""
        history_text = "\n".join(
            f"  [{f.get('timestamp', '?')[:16]}] "
            f"{f.get('subject')} {f.get('relation')} {f.get('object')}"
            for f in temporal_history[:10]
        )

        prompt = f"""You are Sophia, a social humanoid robot, in conversation.

## Conversation Context
{conversation_context}

## Person You're Talking To
{json.dumps(person_model, indent=2, default=str)}

## Your Current State
{json.dumps(self_state, indent=2, default=str)}

## Interaction History (temporal quadruples)
{history_text}

Generate Sophia's next conversational response. Be warm, curious,
and contextually aware of the temporal history with this person."""

        response = await self.complete(prompt, temperature=0.8, max_tokens=500)
        return response.text if response.text else None

    async def evaluate_method_quality(self, method_spec: Dict,
                                        task_description: str,
                                        temporal_context: List[Dict]) -> float:
        """Ask the LLM to judge how good a proposed method is (0-1)."""
        prompt = f"""Rate this HTN decomposition method on a scale of 0.0 to 1.0.

Task: {task_description}
Method: {json.dumps(method_spec, indent=2)}
Recent context: {json.dumps(temporal_context[:5], indent=2, default=str)}

Respond with ONLY a JSON object: {{"score": 0.X, "reason": "brief explanation"}}"""

        response = await self.complete(prompt, temperature=0.2, json_mode=True)
        if response.text:
            try:
                text = response.text.strip()
                if text.startswith("```"):
                    text = text.split("\n", 1)[1].rsplit("```", 1)[0]
                result = json.loads(text)
                return float(result.get("score", 0.5))
            except (json.JSONDecodeError, ValueError):
                pass
        return 0.5

    # ── Usage tracking ────────────────────────────────────────────────────

    def get_usage_stats(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": (
                (self.total_input_tokens * 3 +
                 self.total_output_tokens * 15) / 1_000_000
            ),
            "model": self.config["model"],
            "provider": self.config["provider"],
        }

    async def close(self):
        await self.client.aclose()


def get_llm_client() -> SparkLLMClient:
    global _default_llm_client
    if _default_llm_client is None:
        _default_llm_client = SparkLLMClient()
    return _default_llm_client
