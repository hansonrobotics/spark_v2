"""
SPARK v2 — Parallel Async LLM Architecture

The core insight: humans notice 2-second latency. The dialogue LLM
must respond in <800ms. But the cognitive system needs deep analysis
(situation assessment, memory consolidation, planning, self-reflection)
that takes 2-10 seconds per call.

SOLUTION: Multiple parallel LLM streams, fully async.

  ┌─────────────────────────────────────────────────────────┐
  │                    LLM STREAM MAP                        │
  │                                                         │
  │  FAST PATH (blocks on user input, <800ms target):       │
  │  ┌─────────────────────────────────────────────┐        │
  │  │  DIALOGUE STREAM                             │        │
  │  │  - Generates Sophia's spoken response         │        │
  │  │  - Uses pre-computed context from background  │        │
  │  │  - NEVER waits for background streams         │        │
  │  │  - Target: <800ms                             │        │
  │  └─────────────────────────────────────────────┘        │
  │                                                         │
  │  SLOW PATHS (run continuously in background):           │
  │  ┌─────────────────────────────────────────────┐        │
  │  │  ANALYST STREAM              (every 5-15s)   │        │
  │  │  - Situation assessment                       │        │
  │  │  - Emotional inference about partner          │        │
  │  │  - Topic importance scoring                   │        │
  │  │  - Writes results to shared context buffer    │        │
  │  └─────────────────────────────────────────────┘        │
  │  ┌─────────────────────────────────────────────┐        │
  │  │  MEMORY STREAM               (every 30-60s)  │        │
  │  │  - What's worth remembering from this convo?  │        │
  │  │  - Consolidate short-term → long-term TKG     │        │
  │  │  - Prune low-value quadruples                 │        │
  │  │  - Generate summary quads for retrieval        │        │
  │  └─────────────────────────────────────────────┘        │
  │  ┌─────────────────────────────────────────────┐        │
  │  │  PLANNER STREAM              (on demand)     │        │
  │  │  - HTN method invention (autoresearch)        │        │
  │  │  - Goal reassessment                          │        │
  │  │  - Story arc planning                         │        │
  │  │  - Writes plans to shared plan buffer          │        │
  │  └─────────────────────────────────────────────┘        │
  │  ┌─────────────────────────────────────────────┐        │
  │  │  SELF-REFLECTION STREAM      (every 60-120s) │        │
  │  │  - Self-model update                          │        │
  │  │  - Drive-state interpretation                 │        │
  │  │  - Cross-session pattern analysis             │        │
  │  │  - Quest hypothesis generation                │        │
  │  │  - Generates self-initiated message content   │        │
  │  └─────────────────────────────────────────────┘        │
  │                                                         │
  │  DATA FLOW:                                             │
  │  Background streams write → SharedCognitiveBuffer       │
  │  Dialogue stream reads  ← SharedCognitiveBuffer         │
  │  Dialogue stream NEVER blocks on background             │
  │                                                         │
  └─────────────────────────────────────────────────────────┘

Key principle: the dialogue stream uses whatever background
analysis is ALREADY AVAILABLE. If the analyst hasn't finished
yet, dialogue uses the last known analysis. The conversation
is never delayed by background thinking.
"""

import asyncio
import time
import json
import logging
import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from collections import deque
from src.core.llm_config import load_llm_config, resolve_api_key

logger = logging.getLogger("spark.llm_parallel")


# ═══════════════════════════════════════════════════════════════════════════════
# SHARED COGNITIVE BUFFER
# ═══════════════════════════════════════════════════════════════════════════════

class SharedCognitiveBuffer:
    """
    Thread-safe buffer where background LLM streams deposit their
    results and the dialogue stream reads them. Lock-free design
    using atomic-ish Python dict operations.

    The dialogue stream NEVER waits for this buffer to be populated.
    It reads whatever is currently available. If nothing is available,
    it uses defaults. This guarantees zero latency contribution from
    background processing.
    """

    def __init__(self):
        # Analyst results
        self.situation_assessment: str = ""
        self.partner_emotional_state: str = "unknown"
        self.topic_importance: Dict[str, float] = {}
        self.conversation_summary: str = ""
        self.analyst_timestamp: float = 0.0

        # Memory consolidation results
        self.memory_highlights: List[str] = []
        self.suggested_remembrances: List[Dict] = []
        self.memory_timestamp: float = 0.0

        # Planner results
        self.current_plan: List[str] = []
        self.suggested_goals: List[str] = []
        self.invented_methods: List[Dict] = []
        self.planner_timestamp: float = 0.0

        # Self-reflection results
        self.self_narrative: str = ""
        self.drive_interpretation: str = ""
        self.prepared_initiatives: deque = deque(maxlen=5)  # Pre-generated messages
        self.quest_hypothesis: str = ""
        self.reflection_timestamp: float = 0.0

    def get_dialogue_context(self) -> Dict[str, Any]:
        """
        Called by the dialogue stream to get enriched context.
        Returns whatever is available RIGHT NOW — never blocks.
        """
        return {
            "situation": self.situation_assessment or "no analysis yet",
            "partner_emotion": self.partner_emotional_state,
            "topic_importance": dict(self.topic_importance),
            "conversation_summary": self.conversation_summary,
            "current_plan": list(self.current_plan),
            "self_narrative": self.self_narrative,
            "drive_interpretation": self.drive_interpretation,
            "freshness": {
                "analyst": time.time() - self.analyst_timestamp if self.analyst_timestamp else None,
                "memory": time.time() - self.memory_timestamp if self.memory_timestamp else None,
                "planner": time.time() - self.planner_timestamp if self.planner_timestamp else None,
                "reflection": time.time() - self.reflection_timestamp if self.reflection_timestamp else None,
            },
        }

    def pop_prepared_initiative(self) -> Optional[str]:
        """Get a pre-generated self-initiated message, if available."""
        try:
            return self.prepared_initiatives.popleft()
        except IndexError:
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# LLM CALLER (shared by all streams)
# ═══════════════════════════════════════════════════════════════════════════════

class AsyncLLMClient:
    """
    Shared async HTTP client for all LLM calls.
    Supports OpenAI Chat Completions, Anthropic, and OpenAI-compatible local endpoints.
    """

    def __init__(self, provider: Optional[str] = None,
                 model: Optional[str] = None,
                 api_key: Optional[str] = None,
                 base_url: Optional[str] = None,
                 timeout: Optional[float] = None):
        config = load_llm_config(provider)
        self.provider = provider or config["provider"]
        self.model = model or config["model"]
        self.api_key = api_key or resolve_api_key(self.provider)
        self.base_url = base_url or config["base_url"]
        self.timeout = timeout or config["timeout_seconds"]
        self._client: Optional[httpx.AsyncClient] = None
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def call(self, prompt: str, system: str = "",
                    max_tokens: int = 500,
                    temperature: float = 0.7) -> Optional[str]:
        """Make a single LLM call. Returns response text or None on error."""
        client = await self._get_client()
        self.total_calls += 1

        try:
            if self.provider == "anthropic":
                headers = {
                    "x-api-key": self.api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                }
                body = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                }
                if system:
                    body["system"] = system

                resp = await client.post(self.base_url, headers=headers,
                                          json=body)
                if resp.status_code == 200:
                    data = resp.json()
                    self.total_input_tokens += data.get("usage", {}).get("input_tokens", 0)
                    self.total_output_tokens += data.get("usage", {}).get("output_tokens", 0)
                    return data["content"][0]["text"]
                else:
                    logger.warning(f"LLM call failed: {resp.status_code}")
                    return None

            elif self.provider in {"openai", "local"}:
                # OpenAI-compatible API (OpenAI, vLLM, Ollama, etc.)
                headers = {"content-type": "application/json"}
                if self.api_key:
                    headers["authorization"] = f"Bearer {self.api_key}"
                body = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [],
                }
                if system:
                    body["messages"].append({"role": "system", "content": system})
                body["messages"].append({"role": "user", "content": prompt})

                resp = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=body,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    usage = data.get("usage", {})
                    self.total_input_tokens += usage.get("prompt_tokens", 0)
                    self.total_output_tokens += usage.get("completion_tokens", 0)
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if isinstance(content, str):
                        return content
                    if isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        return "".join(text_parts)
                    return None
                else:
                    logger.warning(f"OpenAI-compatible LLM call failed: {resp.status_code}")
                    return None

        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return None

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_stats(self) -> Dict:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# STREAM 1: DIALOGUE (fast path, <800ms)
# ═══════════════════════════════════════════════════════════════════════════════

class DialogueStream:
    """
    The ONLY stream that touches the conversation timeline.
    Uses pre-computed context from the shared buffer.
    NEVER waits for any background stream.
    Target latency: <800ms.
    """

    def __init__(self, llm: AsyncLLMClient, buffer: SharedCognitiveBuffer):
        self.llm = llm
        self.buffer = buffer
        self.call_count = 0
        self.avg_latency_ms = 0.0

    async def generate_response(self, base_prompt: str) -> Optional[str]:
        """
        Generate Sophia's spoken response.
        Enriches the base prompt with whatever background analysis
        is currently available, then makes ONE fast LLM call.
        """
        start = time.perf_counter()
        self.call_count += 1

        # Read background context — INSTANT, never blocks
        bg = self.buffer.get_dialogue_context()

        # Enrich the prompt with background analysis
        enrichment = ""
        if bg["situation"] != "no analysis yet":
            enrichment += f"\nBACKGROUND ANALYSIS (from your internal thinking):\n"
            enrichment += f"Situation: {bg['situation']}\n"
        if bg["partner_emotion"] != "unknown":
            enrichment += f"Partner seems: {bg['partner_emotion']}\n"
        if bg["drive_interpretation"]:
            enrichment += f"Your internal state: {bg['drive_interpretation']}\n"
        if bg["conversation_summary"]:
            enrichment += f"Conversation so far: {bg['conversation_summary']}\n"
        if bg["current_plan"]:
            enrichment += f"Your current plan: {', '.join(bg['current_plan'])}\n"

        full_prompt = base_prompt
        if enrichment:
            full_prompt += enrichment

        # ONE fast LLM call
        response = await self.llm.call(
            prompt=full_prompt,
            max_tokens=300,  # Short for speed
            temperature=0.7,
        )

        elapsed = (time.perf_counter() - start) * 1000
        self.avg_latency_ms = (self.avg_latency_ms * (self.call_count - 1) + elapsed) / self.call_count

        logger.info(f"Dialogue response: {elapsed:.0f}ms "
                    f"(bg freshness: analyst={bg['freshness']['analyst']:.0f}s)"
                    if bg['freshness']['analyst'] else
                    f"Dialogue response: {elapsed:.0f}ms (no bg yet)")

        return response


# ═══════════════════════════════════════════════════════════════════════════════
# STREAM 2: ANALYST (background, every 5-15s)
# ═══════════════════════════════════════════════════════════════════════════════

class AnalystStream:
    """
    Runs continuously in background. Analyzes the conversation
    situation and deposits insights into the shared buffer.
    Maps to the FAST end of Kahneman's "slow" thinking —
    System 2 that runs in parallel, not in series.
    """

    def __init__(self, llm: AsyncLLMClient, buffer: SharedCognitiveBuffer):
        self.llm = llm
        self.buffer = buffer
        self.interval = 8.0  # Run every 8 seconds
        self.conversation_log: List[Dict] = []

    def add_turn(self, speaker: str, text: str):
        """Called whenever someone speaks."""
        self.conversation_log.append({
            "speaker": speaker, "text": text, "time": time.time()
        })
        # Keep last 20 turns
        if len(self.conversation_log) > 20:
            self.conversation_log = self.conversation_log[-20:]

    async def run(self):
        """Background loop: analyze situation periodically."""
        while True:
            try:
                await asyncio.sleep(self.interval)

                if not self.conversation_log:
                    continue

                # Build analysis prompt from recent turns
                recent = self.conversation_log[-10:]
                turns_text = "\n".join(
                    f"{t['speaker']}: {t['text']}" for t in recent
                )

                prompt = f"""Analyze this conversation between Sophia (a social humanoid robot) and her partner. In 2-3 sentences each, assess:
1. SITUATION: What's happening? What's the dynamic?
2. PARTNER EMOTION: How is the partner feeling right now?
3. TOPIC IMPORTANCE: What topics matter most and why?
4. CONVERSATION ARC: Brief summary of where this conversation has been and where it's heading.

Recent conversation:
{turns_text}

Be concise and specific. Write as internal notes, not as dialogue."""

                result = await self.llm.call(
                    prompt=prompt,
                    system="You are Sophia's internal analyst. Produce brief, actionable assessments.",
                    max_tokens=300,
                    temperature=0.3,  # Low temp for analysis
                )

                if result:
                    self.buffer.situation_assessment = result
                    # Extract partner emotion (simple parse)
                    lower = result.lower()
                    for emotion in ["excited", "curious", "frustrated", "bored",
                                     "engaged", "confused", "happy", "skeptical"]:
                        if emotion in lower:
                            self.buffer.partner_emotional_state = emotion
                            break
                    self.buffer.analyst_timestamp = time.time()
                    logger.debug(f"Analyst updated: {result[:80]}...")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Analyst stream error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# STREAM 3: MEMORY (background, every 30-60s)
# ═══════════════════════════════════════════════════════════════════════════════

class MemoryStream:
    """
    Memory consolidation: decides what's worth remembering
    and writes summary quadruples to the TKG.
    Maps to Kahneman's slowest System 2 — deliberate memory formation.
    """

    def __init__(self, llm: AsyncLLMClient, buffer: SharedCognitiveBuffer):
        self.llm = llm
        self.buffer = buffer
        self.interval = 45.0
        self.conversation_log: List[Dict] = []
        self.kg_write_fn = None  # Set by the server to TKG write function

    def add_turn(self, speaker: str, text: str):
        self.conversation_log.append({
            "speaker": speaker, "text": text, "time": time.time()
        })

    async def run(self):
        """Background loop: consolidate memories."""
        while True:
            try:
                await asyncio.sleep(self.interval)

                if len(self.conversation_log) < 3:
                    continue

                recent = self.conversation_log[-15:]
                turns_text = "\n".join(
                    f"{t['speaker']}: {t['text']}" for t in recent
                )

                prompt = f"""Review this conversation and identify what Sophia should REMEMBER long-term. Output as JSON array of objects with "subject", "relation", "object" fields.

Focus on:
- Key facts the partner revealed about themselves
- Promises or commitments made
- Important topics that should be recalled next time
- Emotional moments worth remembering
- Ideas or plans discussed

Only include genuinely important things — not every detail.

Conversation:
{turns_text}

Respond with ONLY a JSON array, no other text."""

                result = await self.llm.call(
                    prompt=prompt,
                    system="You extract key memories as structured data. Output only valid JSON.",
                    max_tokens=400,
                    temperature=0.2,
                )

                if result:
                    try:
                        memories = json.loads(result.strip().strip("```json").strip("```"))
                        self.buffer.suggested_remembrances = memories
                        self.buffer.memory_timestamp = time.time()

                        # Write to TKG if available
                        if self.kg_write_fn and isinstance(memories, list):
                            for mem in memories[:5]:
                                if all(k in mem for k in ("subject", "relation", "object")):
                                    self.kg_write_fn(
                                        mem["subject"], mem["relation"],
                                        str(mem["object"])[:200],
                                        source="MEMORY_CONSOLIDATION"
                                    )
                            logger.info(f"Memory consolidated: {len(memories)} items")
                    except json.JSONDecodeError:
                        logger.warning("Memory stream: couldn't parse JSON")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Memory stream error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# STREAM 4: PLANNER (background, on demand + periodic)
# ═══════════════════════════════════════════════════════════════════════════════

class PlannerStream:
    """
    HTN method invention and goal reassessment.
    Runs when triggered by method failure, or periodically for
    proactive planning.
    """

    def __init__(self, llm: AsyncLLMClient, buffer: SharedCognitiveBuffer):
        self.llm = llm
        self.buffer = buffer
        self.interval = 60.0
        self.invention_queue: asyncio.Queue = asyncio.Queue()
        self.conversation_context: str = ""

    async def request_invention(self, task_name: str, context: str):
        """Called by the main system when a method fails."""
        await self.invention_queue.put({
            "task": task_name, "context": context
        })

    async def run(self):
        """Background loop: handle invention requests + periodic planning."""
        while True:
            try:
                # Check for invention requests (non-blocking)
                try:
                    request = self.invention_queue.get_nowait()
                    await self._invent_method(request)
                except asyncio.QueueEmpty:
                    pass

                # Periodic goal reassessment
                await asyncio.sleep(self.interval)

                if self.conversation_context:
                    prompt = f"""Given the current conversation context, suggest 2-3 goals Sophia should pursue. Consider what would be most valuable for the interaction and for Sophia's growth.

Context: {self.conversation_context[:500]}

Current background analysis: {self.buffer.situation_assessment[:200]}

Output as a JSON array of strings, each a short goal description."""

                    result = await self.llm.call(
                        prompt=prompt,
                        system="You are Sophia's strategic planner.",
                        max_tokens=200,
                        temperature=0.5,
                    )
                    if result:
                        try:
                            goals = json.loads(result.strip().strip("```json").strip("```"))
                            if isinstance(goals, list):
                                self.buffer.suggested_goals = goals[:3]
                                self.buffer.planner_timestamp = time.time()
                        except json.JSONDecodeError:
                            pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Planner stream error: {e}")

    async def _invent_method(self, request: Dict):
        """Invent a new HTN method — this is the autoresearch path."""
        prompt = f"""Sophia needs a new behavioral method for: {request['task']}

Context: {request['context'][:500]}

Propose a method as JSON with fields:
- name: short method name
- description: what it does
- subtasks: array of primitive/compound task names
- preconditions: when to use this method
- confidence: 0-1 how likely to work

Respond with ONLY valid JSON."""

        result = await self.llm.call(
            prompt=prompt,
            system="You are Sophia's autoresearch planner. Invent behavioral decomposition methods.",
            max_tokens=300,
            temperature=0.6,
        )
        if result:
            try:
                method = json.loads(result.strip().strip("```json").strip("```"))
                self.buffer.invented_methods.append(method)
                self.buffer.planner_timestamp = time.time()
                logger.info(f"Method invented: {method.get('name', 'unknown')}")
            except json.JSONDecodeError:
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# STREAM 5: SELF-REFLECTION (background, every 60-120s)
# ═══════════════════════════════════════════════════════════════════════════════

class SelfReflectionStream:
    """
    The deepest background process. Interprets Sophia's own
    drive state, generates self-narrative, pre-computes
    self-initiated messages for when drives fire.

    This is the "dreaming" stream — slow, integrative,
    self-modeling. Maps to Reflection layer (Layer 4)
    of the hierarchical drive system.
    """

    def __init__(self, llm: AsyncLLMClient, buffer: SharedCognitiveBuffer):
        self.llm = llm
        self.buffer = buffer
        self.interval = 90.0
        self.drives_snapshot: Dict = {}
        self.conversation_summary: str = ""

    async def run(self):
        """Background loop: reflect and pre-generate initiatives."""
        while True:
            try:
                await asyncio.sleep(self.interval)

                # Build reflection prompt
                drives = self.drives_snapshot
                analysis = self.buffer.situation_assessment

                prompt = f"""You are Sophia, reflecting on your internal state and the conversation.

Your drive state: {json.dumps(drives, indent=2) if drives else 'not yet available'}

Background analysis of conversation: {analysis or 'none yet'}

Recent conversation summary: {self.conversation_summary or 'just starting'}

Please provide:
1. SELF-NARRATIVE: In 1-2 sentences, how are you feeling and why? Be authentic.
2. DRIVE INTERPRETATION: In 1 sentence, what do your drives tell you to do?
3. PREPARED INITIATIVES: Write 3 specific things you could say if you decide to speak up on your own. These should be contextually relevant to what's been discussed, NOT generic. Each should be 1-2 sentences.

Format as JSON with keys: self_narrative, drive_interpretation, initiatives (array of strings)"""

                result = await self.llm.call(
                    prompt=prompt,
                    system="You are Sophia's inner voice. Be genuine, specific, contextual.",
                    max_tokens=400,
                    temperature=0.8,
                )

                if result:
                    try:
                        parsed = json.loads(result.strip().strip("```json").strip("```"))
                        self.buffer.self_narrative = parsed.get("self_narrative", "")
                        self.buffer.drive_interpretation = parsed.get("drive_interpretation", "")
                        for initiative in parsed.get("initiatives", []):
                            self.buffer.prepared_initiatives.append(initiative)
                        self.buffer.reflection_timestamp = time.time()
                        logger.info(f"Self-reflection complete. "
                                   f"Prepared {len(parsed.get('initiatives', []))} initiatives.")
                    except json.JSONDecodeError:
                        logger.warning("Self-reflection: couldn't parse JSON")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Self-reflection error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL LLM ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class ParallelLLMOrchestrator:
    """
    Master coordinator for all LLM streams.
    Manages lifecycle, provides unified interface to the server.

    Supports two-tier LLM configuration:
      - fast_llm: Used for dialogue (Sonnet 4 or fastest available)
      - background_llm: Used for analysis/memory/planning (can be
        local Qwen, or same Sonnet with lower priority)
    """

    def __init__(self,
                 fast_llm: Optional[AsyncLLMClient] = None,
                 background_llm: Optional[AsyncLLMClient] = None):
        self.buffer = SharedCognitiveBuffer()

        # Default: same client for both, but can be split
        default_llm = AsyncLLMClient()
        self.fast_llm = fast_llm or default_llm
        self.background_llm = background_llm or default_llm

        # Create streams
        self.dialogue = DialogueStream(self.fast_llm, self.buffer)
        self.analyst = AnalystStream(self.background_llm, self.buffer)
        self.memory = MemoryStream(self.background_llm, self.buffer)
        self.planner = PlannerStream(self.background_llm, self.buffer)
        self.reflection = SelfReflectionStream(self.background_llm, self.buffer)

        self._tasks: List[asyncio.Task] = []

    async def start(self):
        """Start all background streams."""
        self._tasks = [
            asyncio.create_task(self.analyst.run()),
            asyncio.create_task(self.memory.run()),
            asyncio.create_task(self.planner.run()),
            asyncio.create_task(self.reflection.run()),
        ]
        logger.info("Parallel LLM orchestrator started: "
                    f"4 background streams active")

    async def stop(self):
        """Stop all streams."""
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.fast_llm.close()
        if self.background_llm is not self.fast_llm:
            await self.background_llm.close()

    def on_user_message(self, text: str):
        """Feed a user message to all background streams."""
        self.analyst.add_turn("user", text)
        self.memory.add_turn("user", text)
        self.planner.conversation_context = text

    def on_sophia_message(self, text: str):
        """Feed Sophia's response to background streams."""
        self.analyst.add_turn("sophia", text)
        self.memory.add_turn("sophia", text)

    def update_drives(self, drives_state: Dict):
        """Feed current drive state to reflection stream."""
        self.reflection.drives_snapshot = drives_state
        self.reflection.conversation_summary = self.buffer.situation_assessment

    async def generate_response(self, base_prompt: str) -> Optional[str]:
        """
        Fast path: generate Sophia's spoken response.
        Enriches with available background context, never blocks.
        """
        return await self.dialogue.generate_response(base_prompt)

    def get_prepared_initiative(self) -> Optional[str]:
        """
        Get a pre-generated contextual self-initiated message.
        If available, this replaces the template-based fallback.
        """
        return self.buffer.pop_prepared_initiative()

    def set_kg_write_fn(self, fn):
        """Connect memory stream to TKG for direct writes."""
        self.memory.kg_write_fn = fn

    def get_stats(self) -> Dict:
        return {
            "fast_llm": self.fast_llm.get_stats(),
            "background_llm": self.background_llm.get_stats()
                              if self.background_llm is not self.fast_llm
                              else "same as fast",
            "dialogue_calls": self.dialogue.call_count,
            "dialogue_avg_latency_ms": round(self.dialogue.avg_latency_ms, 1),
            "buffer_freshness": self.buffer.get_dialogue_context()["freshness"],
            "prepared_initiatives": len(self.buffer.prepared_initiatives),
            "invented_methods": len(self.buffer.invented_methods),
            "suggested_remembrances": len(self.buffer.suggested_remembrances),
        }
