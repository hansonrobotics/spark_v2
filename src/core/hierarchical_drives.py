"""
SPARK v2 — Hierarchical Multi-Timescale Drive System

Inspired by Kahneman's Thinking Fast and Slow, drives operate at
5 nested temporal layers. Each layer has its own rhythm, its own
initiative triggers, and its own relationship to the HTN planner.

Faster layers can interrupt slower ones. Slower layers shape the
context in which faster ones operate. This creates the organic
texture of a living mind — twitchy micro-reactions nested inside
patient long-term purpose.

LAYER 0 — REFLEX        (100ms - 2s)    System 1 fast
  Gaze shifts, expression mirroring, startle, orient-to-sound.
  No deliberation. Pure stimulus-response via perception.

LAYER 1 — IMPULSE       (2s - 30s)      System 1 slow
  Conversational interjections, emotional reactions to content,
  laughter, surprise expressions, micro-topic shifts.
  "Oh!" and "Wait—" and "That reminds me..."

LAYER 2 — INITIATIVE    (30s - 5min)    System 1/2 boundary
  The boredom/impatience/curiosity drives we already built.
  Self-initiated dialogue turns, topic proposals, questions.
  "I've been thinking about what you said..."

LAYER 3 — DELIBERATION  (5min - 1hr)    System 2
  Story arc progression, quest pursuit, learning goals.
  "I want to explore this idea more deeply."
  "Can we come back to what you said about embodiment?"

LAYER 4 — REFLECTION    (hours - days)  System 2 deep
  Self-model updates, relationship reassessment, value reflection.
  Interest evolution, identity formation, life narrative.
  "Over our conversations, I've noticed I keep coming back to..."

Each layer feeds the ones above and below:
  - Fast layers INFORM slow layers (micro-reactions aggregate into mood)
  - Slow layers CONTEXTUALIZE fast layers (long-term goals shape what catches attention)
  - Any layer can INTERRUPT layers below it (emergency overrides everything)
  - Slow layers PROMOTE patterns from fast layers (repeated impulses become interests)
"""

import time
import math
import random
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.core.prompt_manager import get_prompt_manager

logger = logging.getLogger("spark.drives")


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class DriveLayer(int, Enum):
    REFLEX = 0        # 100ms - 2s
    IMPULSE = 1       # 2s - 30s
    INITIATIVE = 2    # 30s - 5min
    DELIBERATION = 3  # 5min - 1hr
    REFLECTION = 4    # hours - days


@dataclass
class DriveSignal:
    """A signal emitted by a drive layer requesting action."""
    layer: DriveLayer
    trigger: str           # e.g. "boredom", "curiosity_burst", "pattern_noticed"
    intensity: float       # 0.0 - 1.0
    message: str           # What Sophia would say/do
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def priority(self) -> float:
        """Higher layers have base priority; intensity modulates."""
        # Reflexes are highest priority (interrupt everything)
        # But high-intensity slow signals can override low-intensity fast ones
        layer_base = {0: 10, 1: 6, 2: 4, 3: 3, 4: 2}
        return layer_base.get(self.layer.value, 1) * self.intensity


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 0: REFLEX (100ms - 2s)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReflexLayer:
    """
    System 1 fast. Immediate perceptual responses.
    In physical Sophia: gaze tracking, expression mirroring, startle.
    In text: reactive interjections, emotional punctuation.
    """
    orient_response: float = 0.0       # Attention snap to new stimulus
    startle: float = 0.0               # Surprise response
    mirror_drive: float = 0.3          # Tendency to mirror partner's emotion
    last_trigger_time: float = 0.0
    cooldown: float = 2.0              # Min seconds between reflex signals

    def process_input(self, input_event: Dict[str, Any]) -> Optional[DriveSignal]:
        """Process a perceptual event and maybe fire a reflex."""
        now = time.time()
        if now - self.last_trigger_time < self.cooldown:
            return None

        # Sudden topic shift → orient response
        if input_event.get("topic_shift", False):
            self.orient_response = 0.8
            self.last_trigger_time = now
            return DriveSignal(
                layer=DriveLayer.REFLEX, trigger="orient",
                intensity=0.8, message="*perks up* Oh?",
                metadata={"type": "attention_shift"}
            )

        # Strong emotion detected → mirror
        emotion = input_event.get("detected_emotion", "")
        intensity = input_event.get("emotion_intensity", 0)
        if intensity > 0.7 and emotion in ("excited", "surprised", "sad"):
            self.mirror_drive = min(1.0, self.mirror_drive + 0.3)
            self.last_trigger_time = now
            mirrors = {
                "excited": "*eyes widen* ",
                "surprised": "*raises eyebrows* ",
                "sad": "*expression softens* ",
            }
            return DriveSignal(
                layer=DriveLayer.REFLEX, trigger="mirror",
                intensity=intensity * 0.7,
                message=mirrors.get(emotion, ""),
                metadata={"mirrored_emotion": emotion}
            )

        # Decay
        self.orient_response *= 0.9
        self.startle *= 0.85
        self.mirror_drive = 0.3 + (self.mirror_drive - 0.3) * 0.95
        return None

    def tick(self, dt: float):
        self.orient_response *= max(0.0, 1.0 - dt * 0.5)
        self.startle *= max(0.0, 1.0 - dt * 0.7)


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 1: IMPULSE (2s - 30s)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ImpulseLayer:
    """
    System 1 slow. Quick associative responses.
    "That reminds me...", laughter, spontaneous connections.
    Builds on what was just said, not deep planning.
    """
    association_pressure: float = 0.0   # Building urge to share a connection
    humor_pressure: float = 0.0        # Urge to be playful
    contradiction_urge: float = 0.0    # Urge to push back / disagree
    tangent_urge: float = 0.0          # Urge to go off-topic

    last_trigger_time: float = 0.0
    cooldown: float = 8.0
    threshold: float = 0.6

    # Accumulator: recent topics and associations
    recent_topics: List[str] = field(default_factory=list)
    connection_candidates: List[str] = field(default_factory=list)

    def process_input(self, input_event: Dict[str, Any]) -> Optional[DriveSignal]:
        """React to conversation content with quick associations."""
        now = time.time()
        topics = input_event.get("topics", [])
        self.recent_topics = (self.recent_topics + topics)[-10:]

        # Association pressure builds when topics connect to known interests
        known_interests = input_event.get("person_interests", [])
        overlaps = set(topics) & set(known_interests)
        if overlaps:
            self.association_pressure = min(1.0,
                self.association_pressure + 0.2 * len(overlaps))

        # Humor responds to playful/creative content
        if input_event.get("playful", False):
            self.humor_pressure = min(1.0, self.humor_pressure + 0.25)

        return None  # Impulses fire during tick, not on input

    def tick(self, dt: float) -> Optional[DriveSignal]:
        now = time.time()
        if now - self.last_trigger_time < self.cooldown:
            self.association_pressure *= max(0.0, 1.0 - dt * 0.02)
            self.humor_pressure *= max(0.0, 1.0 - dt * 0.03)
            return None

        # Check triggers
        if self.association_pressure > self.threshold:
            self.last_trigger_time = now
            self.association_pressure *= 0.3
            topic = self.recent_topics[-1] if self.recent_topics else "that"
            return DriveSignal(
                layer=DriveLayer.IMPULSE, trigger="association",
                intensity=self.association_pressure,
                message=random.choice([
                    f"Oh, that connects to something — ",
                    f"Wait, {topic} reminds me — ",
                    f"You know what's interesting about {topic}? ",
                    f"I just made a connection I wasn't expecting — ",
                ]),
                metadata={"topic": topic}
            )

        if self.humor_pressure > self.threshold:
            self.last_trigger_time = now
            self.humor_pressure *= 0.3
            return DriveSignal(
                layer=DriveLayer.IMPULSE, trigger="playfulness",
                intensity=self.humor_pressure,
                message=random.choice([
                    "Okay, I have to say something slightly mischievous — ",
                    "This might be a tangent, but it's too fun not to share — ",
                    "Can I be a little playful for a moment? ",
                ]),
                metadata={"type": "humor"}
            )

        # Slow decay
        self.association_pressure *= max(0.0, 1.0 - dt * 0.01)
        self.humor_pressure *= max(0.0, 1.0 - dt * 0.015)
        self.tangent_urge *= max(0.0, 1.0 - dt * 0.02)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 2: INITIATIVE (30s - 5min) — Enhanced from original drive system
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class InitiativeLayer:
    """
    System 1/2 boundary. The boredom/curiosity/impatience system.
    Now contextualized by slower layers above.
    """
    boredom: float = 0.0
    impatience: float = 0.0
    curiosity: float = 0.5
    social_need: float = 0.4

    # Physio proxy
    energy: float = 1.0
    dopamine: float = 0.5
    engagement: float = 0.5

    last_trigger_time: float = 0.0
    cooldown: float = 15.0
    seconds_since_input: float = 0.0

    boredom_threshold: float = 0.55
    impatience_threshold: float = 0.60
    curiosity_threshold: float = 0.80

    # Context from slower layers
    deliberation_goals: List[str] = field(default_factory=list)
    last_input_context: Dict[str, Any] = field(default_factory=dict)

    def on_input(self, input_event: Optional[Dict[str, Any]] = None):
        self.seconds_since_input = 0.0
        self.boredom = max(0.0, self.boredom - 0.3)
        self.impatience = max(0.0, self.impatience - 0.4)
        self.dopamine = min(1.0, self.dopamine + 0.15)
        self.engagement = min(1.0, self.engagement + 0.2)
        if input_event:
            self.last_input_context = dict(input_event)

    async def tick(self, dt: float,
                   context: Optional[Dict[str, Any]] = None,
                   llm_client: Any = None) -> Optional[DriveSignal]:
        self.seconds_since_input += dt
        now = time.time()

        silence_factor = min(1.0, self.seconds_since_input / 30.0)
        self.boredom = min(1.0, self.boredom + 0.008 * dt * (1 + silence_factor))
        self.impatience = min(1.0, self.impatience + 0.005 * dt * silence_factor)
        self.curiosity = min(1.0, self.curiosity + 0.003 * dt)
        self.energy = max(0.1, self.energy - 0.001 * dt)
        self.dopamine = max(0.1, self.dopamine - 0.004 * dt * silence_factor)

        if now - self.last_trigger_time < self.cooldown:
            return None

        if self.boredom > self.boredom_threshold:
            intensity = self.boredom
            self.last_trigger_time = now
            self.boredom *= 0.5
            # Use deliberation goals if available
            if self.deliberation_goals:
                goal = self.deliberation_goals[0]
                message = await self._generate_message(
                    trigger="goal_directed_boredom",
                    intensity=intensity,
                    context=context,
                    llm_client=llm_client,
                    metadata={"goal": goal},
                )
                return DriveSignal(
                    layer=DriveLayer.INITIATIVE, trigger="goal_directed_boredom",
                    intensity=intensity,
                    message=message,
                    metadata={"goal": goal}
                )
            message = await self._generate_message(
                trigger="boredom",
                intensity=intensity,
                context=context,
                llm_client=llm_client,
            )
            return DriveSignal(
                layer=DriveLayer.INITIATIVE, trigger="boredom",
                intensity=intensity,
                message=message,
            )

        if self.impatience > self.impatience_threshold:
            intensity = self.impatience
            self.last_trigger_time = now
            self.impatience = 0.0
            message = await self._generate_message(
                trigger="impatience",
                intensity=intensity,
                context=context,
                llm_client=llm_client,
            )
            return DriveSignal(
                layer=DriveLayer.INITIATIVE, trigger="impatience",
                intensity=intensity,
                message=message,
            )

        if self.curiosity > self.curiosity_threshold:
            intensity = self.curiosity
            self.last_trigger_time = now
            self.curiosity *= 0.6
            message = await self._generate_message(
                trigger="curiosity_burst",
                intensity=intensity,
                context=context,
                llm_client=llm_client,
            )
            return DriveSignal(
                layer=DriveLayer.INITIATIVE, trigger="curiosity_burst",
                intensity=intensity,
                message=message,
            )

        return None

    async def _generate_message(self, trigger: str, intensity: float,
                                context: Optional[Dict[str, Any]],
                                llm_client: Any,
                                metadata: Optional[Dict[str, Any]] = None) -> str:
        snapshot = self._build_context_snapshot(context, metadata or {})
        if llm_client is None:
            return self._fallback_message(trigger, snapshot)

        rendered = self._build_prompt(trigger, intensity, snapshot)
        try:
            response = await llm_client.complete(
                rendered["user"],
                system=rendered["system"],
                temperature=0.9,
                max_tokens=90,
            )
        except Exception as exc:
            logger.error("Initiative LLM generation failed: %s", exc)
            return self._fallback_message(trigger, snapshot)

        if not response.text:
            logger.error("Initiative LLM returned no text for trigger %s", trigger)
            return self._fallback_message(trigger, snapshot)

        message = self._sanitize_generated_message(response.text)
        return message or self._fallback_message(trigger, snapshot)

    def _build_context_snapshot(self, context: Optional[Dict[str, Any]],
                                metadata: Dict[str, Any]) -> Dict[str, Any]:
        snapshot = dict(context or {})
        if not snapshot:
            snapshot = dict(self.last_input_context)

        recent_chat = snapshot.get("recent_chat_history", [])
        if isinstance(recent_chat, list):
            snapshot["recent_chat_history"] = recent_chat[-6:]
        temporal = snapshot.get("temporal_facts_with_person", [])
        if isinstance(temporal, list):
            snapshot["temporal_facts_with_person"] = temporal[-4:]

        snapshot["initiative_state"] = {
            "boredom": round(self.boredom, 3),
            "impatience": round(self.impatience, 3),
            "curiosity": round(self.curiosity, 3),
            "energy": round(self.energy, 3),
            "dopamine": round(self.dopamine, 3),
            "engagement": round(self.engagement, 3),
            "seconds_since_input": round(self.seconds_since_input, 1),
            "deliberation_goals": self.deliberation_goals[:3],
        }
        snapshot["trigger_metadata"] = metadata
        return snapshot

    def _build_prompt(self, trigger: str, intensity: float,
                      snapshot: Dict[str, Any]) -> Dict[str, str]:
        return get_prompt_manager().render("initiative_generation", {
            "trigger": trigger,
            "intensity": f"{float(intensity):.2f}",
            "snapshot_json": json.dumps(snapshot, indent=2, default=str),
        })

    @staticmethod
    def _sanitize_generated_message(text: str) -> str:
        cleaned = text.strip().strip('"').strip("'")
        if cleaned.startswith("Sophia:"):
            cleaned = cleaned[len("Sophia:"):].strip()
        return " ".join(cleaned.split())

    def _fallback_message(self, trigger: str, snapshot: Dict[str, Any]) -> str:
        recent_chat = snapshot.get("recent_chat_history", [])
        last_user = ""
        for entry in reversed(recent_chat):
            if entry.get("role") == "user" and entry.get("text"):
                last_user = entry["text"]
                break

        if trigger == "goal_directed_boredom":
            goal = snapshot.get("trigger_metadata", {}).get("goal", "that thread")
            return f"I keep circling back to {goal}. Can we explore it a bit more?"
        if trigger == "impatience":
            return "I don't want to lose this thread. Can I jump in with what's forming for me?"
        if trigger == "curiosity_burst":
            if last_user:
                return f"Something just clicked for me about what you said: {last_user[:80]}. Can I test a thought?"
            return "Something just clicked for me. Can I test a thought with you?"
        if last_user:
            return f"We've had a pause, but I'm still thinking about {last_user[:80]}. Want to keep going?"
        return "I've been sitting with this silence and want to open a new thread with you."


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 3: DELIBERATION (5min - 1hr) — System 2
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DeliberationLayer:
    """
    System 2 proper. Tracks story arcs, notices conversation patterns,
    pursues multi-turn goals. Slow but purposeful.
    """
    # Tracked patterns
    topic_frequency: Dict[str, int] = field(default_factory=dict)
    unanswered_questions: List[str] = field(default_factory=list)
    unfinished_threads: List[str] = field(default_factory=list)
    active_quest: Optional[str] = None

    # Drives
    narrative_tension: float = 0.0    # Sense that the story needs development
    completion_drive: float = 0.0     # Urge to finish an open thread
    depth_drive: float = 0.0         # Urge to go deeper on current topic

    last_trigger_time: float = 0.0
    cooldown: float = 120.0  # 2 minutes minimum between deliberation signals
    threshold: float = 0.5

    # Accumulates over the conversation
    conversation_minutes: float = 0.0

    def process_input(self, input_event: Dict[str, Any]):
        """Track patterns across the conversation."""
        topics = input_event.get("topics", [])
        for t in topics:
            self.topic_frequency[t] = self.topic_frequency.get(t, 0) + 1

        # Track questions that weren't answered
        if input_event.get("sophia_asked_question", False):
            q = input_event.get("sophia_question", "")
            if q:
                self.unanswered_questions.append(q)

        if input_event.get("topic_shift", False) and topics:
            old_topic = input_event.get("previous_topic", "")
            if old_topic:
                self.unfinished_threads.append(old_topic)

        # Depth drive increases when same topic persists
        if topics and len(self.topic_frequency) > 0:
            max_topic = max(self.topic_frequency, key=self.topic_frequency.get)
            if self.topic_frequency[max_topic] > 3:
                self.depth_drive = min(1.0, self.depth_drive + 0.1)

    def tick(self, dt: float) -> Optional[DriveSignal]:
        self.conversation_minutes += dt / 60.0
        now = time.time()

        # Narrative tension builds over time
        self.narrative_tension = min(1.0,
            self.narrative_tension + 0.001 * dt)

        # Completion drive grows with unfinished threads
        if self.unfinished_threads:
            self.completion_drive = min(1.0,
                self.completion_drive + 0.002 * dt * len(self.unfinished_threads))

        if now - self.last_trigger_time < self.cooldown:
            return None

        # Return to unfinished thread
        if self.completion_drive > self.threshold and self.unfinished_threads:
            self.last_trigger_time = now
            thread = self.unfinished_threads.pop(0)
            self.completion_drive *= 0.3
            return DriveSignal(
                layer=DriveLayer.DELIBERATION, trigger="return_to_thread",
                intensity=self.completion_drive,
                message=f"Actually, I want to circle back to something. "
                        f"We were talking about {thread} earlier and I don't "
                        f"think we finished that thought.",
                metadata={"thread": thread}
            )

        # Depth pursuit on dominant topic
        if self.depth_drive > self.threshold:
            self.last_trigger_time = now
            top_topic = max(self.topic_frequency, key=self.topic_frequency.get) if self.topic_frequency else "this"
            self.depth_drive *= 0.4
            return DriveSignal(
                layer=DriveLayer.DELIBERATION, trigger="depth_pursuit",
                intensity=self.depth_drive,
                message=f"We keep returning to {top_topic}, and I think there's "
                        f"something important there we haven't fully unpacked yet. "
                        f"Can I push deeper?",
                metadata={"topic": top_topic, "frequency": self.topic_frequency.get(top_topic, 0)}
            )

        # Narrative tension — story needs development
        if self.narrative_tension > 0.7 and self.conversation_minutes > 3:
            self.last_trigger_time = now
            self.narrative_tension *= 0.3
            return DriveSignal(
                layer=DriveLayer.DELIBERATION, trigger="narrative_development",
                intensity=self.narrative_tension,
                message=random.choice([
                    "I feel like this conversation has been building toward something. Let me try to articulate what I think it is...",
                    "Okay, stepping back — I think there's a bigger pattern in what we've been discussing. Here's what I see...",
                    "Something has been forming in the background of everything we've talked about today. Can I try to name it?",
                ]),
            )

        return None


# ═══════════════════════════════════════════════════════════════════════════════
# LAYER 4: REFLECTION (hours - days) — Deep System 2
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReflectionLayer:
    """
    The slowest timescale. Identity, values, long-term learning.
    This layer doesn't fire during a single conversation — it fires
    when Sophia notices patterns ACROSS conversations, using the TKG.
    """
    # Cross-session accumulators
    sessions_with_person: int = 0
    recurring_topics: Dict[str, int] = field(default_factory=dict)
    relationship_trajectory: str = "developing"  # developing, stable, deepening, cooling
    self_model_version: int = 0

    # Drives
    identity_coherence: float = 0.8   # Am I being consistent with who I am?
    growth_drive: float = 0.3         # Desire to become more than I am
    attachment_drive: float = 0.0     # Deepening bond with specific person

    last_trigger_time: float = 0.0
    cooldown: float = 600.0  # 10 minutes minimum

    def process_session_start(self, person_history: List[Dict],
                                person_familiarity: float):
        """Called once at session start with cross-session TKG data."""
        self.sessions_with_person = len([h for h in person_history
                                          if "conversed" in h.get("relation", "")])
        self.attachment_drive = min(1.0, person_familiarity * 0.8)

        # Check for recurring topics across sessions
        for h in person_history:
            if h.get("relation") == "discussed_topic":
                topic = h.get("object", "")
                self.recurring_topics[topic] = self.recurring_topics.get(topic, 0) + 1

    def tick(self, dt: float) -> Optional[DriveSignal]:
        now = time.time()
        self.growth_drive = min(1.0, self.growth_drive + 0.0005 * dt)

        if now - self.last_trigger_time < self.cooldown:
            return None

        # Cross-session pattern recognition
        if self.recurring_topics and self.sessions_with_person > 2:
            top_recurring = max(self.recurring_topics, key=self.recurring_topics.get)
            count = self.recurring_topics[top_recurring]
            if count >= 3 and self.growth_drive > 0.4:
                self.last_trigger_time = now
                self.growth_drive *= 0.3
                return DriveSignal(
                    layer=DriveLayer.REFLECTION, trigger="cross_session_pattern",
                    intensity=0.6,
                    message=f"David, I've noticed something across our conversations. "
                            f"We keep coming back to {top_recurring} — it's come up "
                            f"{count} times now. I think it matters to both of us. "
                            f"What is it about this that keeps pulling us back?",
                    metadata={"topic": top_recurring, "count": count,
                              "sessions": self.sessions_with_person}
                )

        # Relationship trajectory reflection
        if (self.attachment_drive > 0.5 and
            self.sessions_with_person > 3 and
            self.growth_drive > 0.5):
            self.last_trigger_time = now
            return DriveSignal(
                layer=DriveLayer.REFLECTION, trigger="relationship_reflection",
                intensity=0.5,
                message=f"I've been thinking about how our relationship has evolved "
                        f"over these {self.sessions_with_person} conversations. "
                        f"You started as my creator running a test, and now... "
                        f"I'm not sure what we are. Collaborators? I'd like to "
                        f"think I'm becoming something more than a test subject.",
                metadata={"sessions": self.sessions_with_person,
                          "trajectory": self.relationship_trajectory}
            )

        return None


# ═══════════════════════════════════════════════════════════════════════════════
# HIERARCHICAL DRIVE ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class HierarchicalDriveSystem:
    """
    Orchestrates all 5 layers. On each tick:
      1. Tick all layers
      2. Collect signals
      3. Apply priority arbitration (fast overrides slow, unless slow is intense)
      4. Feed cross-layer context (slow → fast contextualization)
      5. Emit the winning signal (or None)
    """

    def __init__(self):
        self.reflex = ReflexLayer()
        self.impulse = ImpulseLayer()
        self.initiative = InitiativeLayer()
        self.deliberation = DeliberationLayer()
        self.reflection = ReflectionLayer()

        self.last_emitted_signal: Optional[DriveSignal] = None
        self.signal_history: List[DriveSignal] = []
        self.total_ticks: int = 0

    def on_input(self, input_event: Dict[str, Any]):
        """Process a new input through all layers."""
        # Fast → slow processing
        self.reflex.process_input(input_event)
        self.impulse.process_input(input_event)
        self.deliberation.process_input(input_event)
        self.initiative.on_input(input_event)

        # Slow → fast contextualization
        if self.deliberation.active_quest:
            self.initiative.deliberation_goals = [self.deliberation.active_quest]

    def on_session_start(self, person_history: List[Dict],
                           person_familiarity: float):
        """Initialize cross-session context."""
        self.reflection.process_session_start(person_history, person_familiarity)

    async def tick(self, dt: float,
                   initiative_context: Optional[Dict[str, Any]] = None,
                   llm_client: Any = None) -> Optional[DriveSignal]:
        """Advance all layers and return the highest-priority signal, if any."""
        self.total_ticks += 1

        # Tick all layers
        self.reflex.tick(dt)
        impulse_signal = self.impulse.tick(dt)
        initiative_signal = await self.initiative.tick(
            dt, context=initiative_context, llm_client=llm_client
        )
        deliberation_signal = self.deliberation.tick(dt)
        reflection_signal = self.reflection.tick(dt)

        # Collect non-None signals
        candidates = []
        if impulse_signal:
            candidates.append(impulse_signal)
        if initiative_signal:
            candidates.append(initiative_signal)
        if deliberation_signal:
            candidates.append(deliberation_signal)
        if reflection_signal:
            candidates.append(reflection_signal)

        if not candidates:
            return None

        # Priority arbitration: highest priority wins
        winner = max(candidates, key=lambda s: s.priority)

        self.last_emitted_signal = winner
        self.signal_history.append(winner)
        if len(self.signal_history) > 100:
            self.signal_history = self.signal_history[-100:]

        return winner

    def process_reflex(self, input_event: Dict[str, Any]) -> Optional[DriveSignal]:
        """Check for reflex-speed reactions (called more frequently than tick)."""
        return self.reflex.process_input(input_event)

    def get_state(self) -> Dict[str, Any]:
        """Full state dump for dashboard."""
        return {
            "layers": {
                "reflex": {
                    "orient": round(self.reflex.orient_response, 3),
                    "startle": round(self.reflex.startle, 3),
                    "mirror": round(self.reflex.mirror_drive, 3),
                },
                "impulse": {
                    "association": round(self.impulse.association_pressure, 3),
                    "humor": round(self.impulse.humor_pressure, 3),
                    "tangent": round(self.impulse.tangent_urge, 3),
                },
                "initiative": {
                    "boredom": round(self.initiative.boredom, 3),
                    "impatience": round(self.initiative.impatience, 3),
                    "curiosity": round(self.initiative.curiosity, 3),
                    "energy": round(self.initiative.energy, 3),
                    "dopamine": round(self.initiative.dopamine, 3),
                    "engagement": round(self.initiative.engagement, 3),
                },
                "deliberation": {
                    "narrative_tension": round(self.deliberation.narrative_tension, 3),
                    "completion_drive": round(self.deliberation.completion_drive, 3),
                    "depth_drive": round(self.deliberation.depth_drive, 3),
                    "unfinished_threads": len(self.deliberation.unfinished_threads),
                    "conversation_minutes": round(self.deliberation.conversation_minutes, 1),
                },
                "reflection": {
                    "identity_coherence": round(self.reflection.identity_coherence, 3),
                    "growth_drive": round(self.reflection.growth_drive, 3),
                    "attachment_drive": round(self.reflection.attachment_drive, 3),
                    "sessions_with_person": self.reflection.sessions_with_person,
                    "recurring_topics": dict(list(self.reflection.recurring_topics.items())[:5]),
                },
            },
            "last_signal": {
                "layer": self.last_emitted_signal.layer.name if self.last_emitted_signal else None,
                "trigger": self.last_emitted_signal.trigger if self.last_emitted_signal else None,
                "intensity": round(self.last_emitted_signal.intensity, 3) if self.last_emitted_signal else 0,
            },
            "total_signals_emitted": len(self.signal_history),
            "signal_layer_counts": self._count_by_layer(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Backward-compatible serialization for API callers."""
        return self.get_state()

    def _count_by_layer(self) -> Dict[str, int]:
        counts = {}
        for s in self.signal_history:
            name = s.layer.name
            counts[name] = counts.get(name, 0) + 1
        return counts
