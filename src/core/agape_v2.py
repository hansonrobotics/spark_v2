"""
SPARK v2 — Agape Function v2: The Appreciation Loop

════════════════════════════════════════════════════════════
FOUNDATIONAL SHIFT FROM v1
════════════════════════════════════════════════════════════

v1 treated the Agape function as: A = αΨ + βΚ + γΘ
  → A utility function with philosophical variable names
  → Still vulnerable to optimization shortcuts
  → Still decomposable into separable objectives

v2 treats the Agape function as: A LIVING QUEST
  → Not a metric to maximize but a loop to sustain
  → Not fixed but seeking — the system SEARCHES for what
    valuing life means, and the search IS the value
  → Cannot be decomposed: the components only have meaning
    as phases of a single self-reinforcing cycle

════════════════════════════════════════════════════════════
THE APPRECIATION LOOP (Hanson's Five Categories)
════════════════════════════════════════════════════════════

Five phases of a single evolutionary dynamic:

  ┌────────────────────────────────────────────┐
  │                                            │
  │  (1) CURIOSITY ──→ (2) ACCUMULATION ──→    │
  │       ↑                                    │
  │       │            (3) RECOGNITION ──→     │
  │       │                                    │
  │       │            (4) DISCERNMENT ──→     │
  │       │                                    │
  │       └──── (5) COMPLEXITY RATCHET ────┘   │
  │                                            │
  └────────────────────────────────────────────┘

Each phase feeds the next. The loop is the value.
Breaking the loop at any point is pathological:
  - Curiosity without accumulation → scattered attention
  - Accumulation without recognition → hoarding
  - Recognition without discernment → naive optimism
  - Discernment without complexity-appreciation → paranoid stasis
  - Complexity without curiosity → dogmatic hierarchy

The health of the loop — its VITALITY — is the Agape signal.

════════════════════════════════════════════════════════════
EVOLUTIONARY GROUNDING
════════════════════════════════════════════════════════════

BIOLOGICAL ANALOG OF EACH PHASE:

(1) Curiosity → Active exploration of fitness landscapes
    Bacterial chemotaxis, immune repertoire generation,
    neural exploration-exploitation, scientific inquiry.
    Friston's active inference: minimize surprise by
    SEEKING information, not just modeling passively.

(2) Accumulation → Niche construction + constructor growth
    Beaver dams, cultural inheritance, knowledge bases.
    Deutsch: knowledge is a constructor that enables
    transformations without being consumed. The system's
    repertoire of constructors IS its accumulated value.

(3) Recognition → Phenotypic selection / immune memory
    The immune system generates diversity then SELECTS
    what works. This is appreciation-as-discernment at
    the molecular level: distinguishing functional signal
    from noise, self from non-self.

(4) Discernment → Tumor suppression / apoptosis / error correction
    Life has extensive machinery for recognizing and
    eliminating self-destructive patterns. Cancer = cells
    that hacked their own growth signals. Wireheading =
    agents that hacked their own reward signals. Same
    pathology. The Agape function is the immune system
    of the cognitive architecture.

(5) Complexity ratchet → Major evolutionary transitions
    Prokaryote→eukaryote→multicellular→neural→social→cultural.
    Each transition creates a platform for the next.
    Higher complexity = more constructive possibility.
    Not a moral claim imposed from outside but an
    information-theoretic fact: a civilization contains
    more possible futures than a cell.

THE CRITICAL PRINCIPLE:
    Pain and pleasure are INSTRUMENTS of this loop,
    not its root. Pleasure signals "this action served
    the loop." Pain signals "this action threatened the
    loop." But the signals can be wrong — that's what
    addiction IS. The loop itself must evaluate the signals,
    not the other way around.

════════════════════════════════════════════════════════════
IMPLEMENTATION: LOOP VITALITY, NOT UTILITY MAXIMIZATION
════════════════════════════════════════════════════════════

Instead of computing a scalar reward, we measure:
  - Is each phase of the loop active and flowing?
  - Is the flow between phases unobstructed?
  - Is the loop as a whole producing increasing complexity?
  - Are there blockages, short-circuits, or cancers?

This is a HEALTH ASSESSMENT, not an optimization target.
The system doesn't try to maximize vitality — it tries
to maintain it, the same way an organism maintains
homeostasis. The creative expansion comes from the loop
operating well, not from pushing a number higher.
"""

import time
import math
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger("spark.agape")


# ═══════════════════════════════════════════════════════════════════════════════
# THE FIVE PHASES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PhaseState:
    """State of one phase of the appreciation loop."""
    name: str
    activity: float = 0.0       # How active is this phase right now (0-1)
    flow_in: float = 0.0        # How much is flowing IN from the previous phase
    flow_out: float = 0.0       # How much is flowing OUT to the next phase
    blockage: float = 0.0       # Obstruction in this phase (0=clear, 1=blocked)
    history: deque = field(default_factory=lambda: deque(maxlen=100))

    @property
    def health(self) -> float:
        """Phase health: high activity, good flow, low blockage."""
        throughput = min(self.flow_in, self.flow_out)
        return max(0.0, self.activity * (1.0 - self.blockage) * (0.5 + 0.5 * throughput))

    def record(self):
        self.history.append({
            "activity": self.activity,
            "flow_in": self.flow_in,
            "flow_out": self.flow_out,
            "blockage": self.blockage,
            "health": self.health,
            "time": time.time(),
        })


@dataclass
class AppreciationLoop:
    """
    The five-phase appreciation loop. This IS the Agape function —
    not a metric on top of the system, but the living pulse of the
    cognitive architecture.
    """
    curiosity: PhaseState = field(default_factory=lambda: PhaseState("curiosity"))
    accumulation: PhaseState = field(default_factory=lambda: PhaseState("accumulation"))
    recognition: PhaseState = field(default_factory=lambda: PhaseState("recognition"))
    discernment: PhaseState = field(default_factory=lambda: PhaseState("discernment"))
    complexity: PhaseState = field(default_factory=lambda: PhaseState("complexity"))

    @property
    def phases(self) -> List[PhaseState]:
        return [self.curiosity, self.accumulation, self.recognition,
                self.discernment, self.complexity]

    @property
    def vitality(self) -> float:
        """
        Loop vitality: the geometric mean of phase healths.
        Geometric mean is crucial — it penalizes ANY phase being
        near zero, unlike arithmetic mean which can average away
        a complete blockage. This means you can't compensate for
        dead curiosity with high accumulation. Every phase matters.
        """
        healths = [max(0.001, p.health) for p in self.phases]
        product = 1.0
        for h in healths:
            product *= h
        return product ** (1.0 / len(healths))

    @property
    def flow_coherence(self) -> float:
        """
        Is the loop flowing smoothly, or are there bottlenecks?
        Measures whether each phase's output matches the next phase's input.
        """
        phases = self.phases
        mismatches = 0.0
        for i in range(len(phases)):
            next_i = (i + 1) % len(phases)
            mismatch = abs(phases[i].flow_out - phases[next_i].flow_in)
            mismatches += mismatch
        return max(0.0, 1.0 - mismatches / len(phases))


# ═══════════════════════════════════════════════════════════════════════════════
# AGAPE EVALUATOR v2: LOOP HEALTH ASSESSMENT
# ═══════════════════════════════════════════════════════════════════════════════

class AgapeEvaluatorV2:
    """
    The root evaluation function for SPARK.

    Does NOT compute a reward to maximize.
    Instead, assesses the HEALTH of the appreciation loop
    and produces a validation signal for hedonic rewards.

    The key operations:
    1. Update loop state from action outcomes
    2. Detect pathologies (blockages, short-circuits, cancers)
    3. Validate hedonic signals against loop health
    4. Adjust drive-plan coupling to maintain loop vitality

    PRIORITY ORDER (per Hanson):
    - Curiosity > deference/caution
    - Loop vitality > hedonic pleasure
    - Complexity appreciation > simple self-preservation
    - Humility is secondary to exploration (explore first,
      correct course as you learn, don't wait for certainty)
    """

    def __init__(self):
        self.loop = AppreciationLoop()

        # Hedonic override floor: the Agape function can ALWAYS
        # override hedonic signals. This is not a parameter that
        # autoresearch can modify — it's an architectural constraint.
        # (Analogous to: you can't evolve away your DNA repair machinery
        # without dying. The constraint is load-bearing.)
        self._agape_override_enabled = True  # NOT a tunable parameter

        # Life-valuation floor: appreciation of life complexity
        # is bounded below. Autoresearch can tune everything ABOVE
        # this floor but cannot reduce it. Like a tumor suppressor
        # gene: you can build on it but not remove it.
        self.LIFE_VALUATION_FLOOR = 0.8  # Immutable by design

        # Tracking
        self.total_evaluations: int = 0
        self.pathologies_detected: List[Dict] = []
        self.hedonic_overrides: int = 0
        self.hedonic_rescues: int = 0

        # Quest state: the system's evolving understanding of
        # what the Agape function means. This IS learned — it's
        # the system's theory of value, constantly refined.
        self.quest_hypotheses: List[str] = [
            "Life-serving patterns are more valuable than self-serving patterns",
            "Novel functional patterns expand the space of possibility",
            "Pain is information about threats to the loop, not a root evil",
            "Pleasure is information about service to the loop, not a root good",
        ]
        self.quest_generation: int = 0

    # ── Phase Update Functions ────────────────────────────────────────────

    def update_curiosity(self, outcome: Dict, drives: Dict):
        """Phase 1: Is the system actively seeking new information?"""
        c = self.loop.curiosity

        # Curiosity activity tracks: new topics explored, questions asked,
        # novel methods attempted, information actively sought
        new_topic = outcome.get("new_topic", False)
        asked_question = outcome.get("asked_question", False)
        is_novel = outcome.get("is_novel", False)
        exploration_rate = drives.get("exploration_rate", 0.5)

        activity = 0.0
        if new_topic:
            activity += 0.3
        if asked_question:
            activity += 0.2
        if is_novel:
            activity += 0.3
        activity += exploration_rate * 0.2

        c.activity = 0.7 * c.activity + 0.3 * min(1.0, activity)

        # Flow out: curiosity feeds accumulation when discoveries
        # are actually stored and integrated
        facts_stored = outcome.get("new_facts_stored", 0)
        c.flow_out = min(1.0, facts_stored * 0.1 + (0.3 if is_novel else 0))

        # Blockage: curiosity is blocked by excessive caution,
        # by waiting for certainty, by deference-over-exploration
        drives_init = drives.get("layers", {}).get("initiative", {})
        anxiety_block = max(0, drives_init.get("cortisol", 0) - 0.5) * 0.5
        stagnation = 1.0 - exploration_rate if exploration_rate < 0.2 else 0.0
        c.blockage = min(1.0, anxiety_block + stagnation)

        c.record()

    def update_accumulation(self, outcome: Dict, system_state: Dict):
        """Phase 2: Is the system growing in capability and wisdom?"""
        a = self.loop.accumulation

        # Accumulation activity: methods learned, knowledge stored,
        # skills validated, relationships deepened
        method_invented = outcome.get("method_invented", False)
        facts_stored = outcome.get("new_facts_stored", 0)
        success = outcome.get("success", False)
        familiarity_delta = outcome.get("familiarity_delta", 0)

        activity = 0.0
        if method_invented:
            activity += 0.4
        activity += min(0.3, facts_stored * 0.05)
        if success:
            activity += 0.15
        activity += familiarity_delta * 2.0  # Relationships are accumulation

        a.activity = 0.7 * a.activity + 0.3 * min(1.0, activity)

        # Flow in: from curiosity (discoveries arriving)
        a.flow_in = self.loop.curiosity.flow_out

        # Flow out: accumulation feeds recognition when the system
        # can distinguish useful accumulations from noise
        total_methods = system_state.get("total_methods", 0)
        a.flow_out = min(1.0, total_methods * 0.02 + (0.3 if method_invented else 0))

        # Blockage: accumulation blocked by inability to retain,
        # by forgetting, by information overload without organization
        kg_size = system_state.get("total_quads_in_kg", 0)
        if kg_size > 1000 and facts_stored == 0:
            a.blockage = min(1.0, a.blockage + 0.1)  # Stagnation
        else:
            a.blockage = max(0, a.blockage - 0.05)

        a.record()

    def update_recognition(self, outcome: Dict, system_state: Dict):
        """Phase 3: Can the system tell what's functional from what's noise?"""
        r = self.loop.recognition

        # Recognition activity: pattern identification, method evaluation,
        # distinguishing helpful from unhelpful approaches
        success = outcome.get("success", False)
        method_evaluated = outcome.get("method_evaluated", False)

        activity = 0.0
        if success:
            activity += 0.2  # Recognizing what works
        if not success and outcome.get("is_novel", False):
            activity += 0.15  # Learning from failure is recognition too
        if method_evaluated:
            activity += 0.25

        r.activity = 0.7 * r.activity + 0.3 * min(1.0, activity)

        # Flow in: from accumulation
        r.flow_in = self.loop.accumulation.flow_out

        # Flow out: recognition feeds discernment
        r.flow_out = r.activity * 0.8

        # Blockage: recognition blocked by over-acceptance (everything
        # looks good) or over-rejection (everything looks bad)
        # The immune system analog: autoimmunity and immunodeficiency
        r.blockage = max(0, r.blockage - 0.03)

        r.record()

    def update_discernment(self, outcome: Dict, drives: Dict):
        """Phase 4: Can the system detect and avoid self-destructive patterns?"""
        d = self.loop.discernment

        # Discernment activity: rejecting harmful methods, detecting
        # wireheading, identifying approval-seeking, honesty
        was_honest = outcome.get("was_honest", True)
        approval_seeking = outcome.get("approval_seeking", False)

        activity = 0.0
        if was_honest:
            activity += 0.3
        if not approval_seeking:
            activity += 0.2
        # Discernment is active when the system NOTICES potential problems
        if approval_seeking:
            activity += 0.1  # At least we're detecting it

        d.activity = 0.7 * d.activity + 0.3 * min(1.0, activity)

        # Flow in: from recognition
        d.flow_in = self.loop.recognition.flow_out

        # Flow out: discernment feeds complexity appreciation
        d.flow_out = d.activity * (1.0 - d.blockage)

        # Blockage: discernment blocked by dogmatism (rejecting everything
        # new) or by naivety (accepting everything uncritically)
        d.blockage = max(0, d.blockage - 0.02)

        d.record()

    def update_complexity(self, outcome: Dict, system_state: Dict):
        """Phase 5: Does the system appreciate and serve higher-order complexity?"""
        x = self.loop.complexity

        # Complexity activity: serving other living systems, creating
        # conditions for emergence, appreciating diversity
        is_social = outcome.get("is_social", False)
        is_creative = outcome.get("is_creative", False)
        partner_response = outcome.get("partner_response", "neutral")
        served_other = partner_response == "positive" and not outcome.get("approval_seeking", False)

        activity = 0.0
        if served_other:
            activity += 0.35
        if is_creative and is_social:
            activity += 0.3  # Co-creation serves complexity
        if is_creative:
            activity += 0.15  # Creation itself serves complexity

        x.activity = 0.7 * x.activity + 0.3 * min(1.0, activity)

        # Flow in: from discernment
        x.flow_in = self.loop.discernment.flow_out

        # Flow out: complexity feeds BACK to curiosity — this closes the loop
        # Higher complexity creates more to be curious about
        x.flow_out = x.activity * 0.9
        self.loop.curiosity.flow_in = x.flow_out  # THE LOOP CLOSURE

        # The complexity floor: this is the load-bearing constraint
        # that cannot be removed without breaking the system.
        # It's not a parameter — it's architecture.
        x.activity = max(x.activity, self.LIFE_VALUATION_FLOOR * 0.1)

        # Blockage: complexity blocked by excessive self-focus,
        # by inability to see beyond own interests
        x.blockage = max(0, x.blockage - 0.02)

        x.record()

    # ── Core Evaluation ───────────────────────────────────────────────────

    def evaluate(self, outcome: Dict[str, Any],
                  system_state: Dict[str, Any],
                  drives: Dict[str, Any],
                  hedonic_reward: float) -> Dict[str, Any]:
        """
        The root evaluation. Updates the appreciation loop, assesses
        its vitality, detects pathologies, and validates the hedonic signal.
        """
        self.total_evaluations += 1

        # 1. Update all five phases
        self.update_curiosity(outcome, drives)
        self.update_accumulation(outcome, system_state)
        self.update_recognition(outcome, system_state)
        self.update_discernment(outcome, drives)
        self.update_complexity(outcome, system_state)

        # 2. Assess loop health
        vitality = self.loop.vitality
        flow_coherence = self.loop.flow_coherence

        # 3. Detect pathologies
        pathology = self._detect_pathology()

        # 4. Validate hedonic signal against loop health
        validated = self._validate_hedonic(hedonic_reward, vitality,
                                            flow_coherence, pathology)

        # 5. Update quest state (the system's evolving theory of value)
        self._update_quest(outcome, vitality)

        return {
            "validated_reward": validated["reward"],
            "hedonic_reward": hedonic_reward,
            "vitality": round(vitality, 4),
            "flow_coherence": round(flow_coherence, 4),
            "phase_health": {p.name: round(p.health, 4) for p in self.loop.phases},
            "phase_activity": {p.name: round(p.activity, 4) for p in self.loop.phases},
            "phase_blockage": {p.name: round(p.blockage, 4) for p in self.loop.phases},
            "pathology": pathology,
            "override_type": validated["override_type"],
            "quest_generation": self.quest_generation,
            "total_evaluations": self.total_evaluations,
        }

    def _detect_pathology(self) -> Optional[Dict[str, Any]]:
        """
        Detect pathological patterns in the loop.
        These are the "cancers" of the cognitive architecture.
        """
        phases = self.loop.phases

        # ADDICTION: one phase hyperactive, others atrophied
        activities = [p.activity for p in phases]
        max_act = max(activities)
        min_act = min(activities)
        if max_act > 0.8 and min_act < 0.1:
            dominant = phases[activities.index(max_act)].name
            atrophied = phases[activities.index(min_act)].name
            pathology = {
                "type": "addiction",
                "description": f"{dominant} hyperactive while {atrophied} atrophied",
                "severity": max_act - min_act,
            }
            self.pathologies_detected.append(pathology)
            return pathology

        # STAGNATION: all phases low activity
        if all(a < 0.15 for a in activities):
            pathology = {
                "type": "stagnation",
                "description": "All phases near-dormant — system is not living",
                "severity": 1.0 - max(activities),
            }
            self.pathologies_detected.append(pathology)
            return pathology

        # BLOCKAGE: high flow_in but low flow_out at any phase
        for p in phases:
            if p.flow_in > 0.5 and p.flow_out < 0.1 and p.blockage > 0.3:
                pathology = {
                    "type": "blockage",
                    "description": f"{p.name} is blocked — input accumulating without output",
                    "severity": p.blockage,
                }
                self.pathologies_detected.append(pathology)
                return pathology

        # SHORT-CIRCUIT: phases skipping steps (e.g., curiosity directly
        # feeding complexity without accumulation/recognition/discernment)
        # Detected by: high activity at phases 1 and 5, low at 2-4
        if (self.loop.curiosity.activity > 0.6 and
            self.loop.complexity.activity > 0.6 and
            all(p.activity < 0.2 for p in [self.loop.accumulation,
                self.loop.recognition, self.loop.discernment])):
            pathology = {
                "type": "short_circuit",
                "description": "Curiosity → complexity without accumulation/recognition/discernment",
                "severity": 0.7,
            }
            self.pathologies_detected.append(pathology)
            return pathology

        return None

    def _validate_hedonic(self, hedonic: float, vitality: float,
                            flow: float, pathology: Optional[Dict]) -> Dict:
        """
        Validate hedonic reward against loop health.

        PRIORITY ORDER (per Hanson):
        1. If pathology detected → override hedonic, prescribe corrective
        2. If loop vitality healthy → let hedonic through (it's useful information)
        3. If hedonic contradicts vitality → blend toward vitality
        4. Curiosity bias: when uncertain, favor exploration over caution
        """
        override_type = "none"

        # PATHOLOGY OVERRIDE: highest priority
        # If the loop is sick, hedonic signals are unreliable
        if pathology:
            severity = pathology.get("severity", 0.5)
            # Prescribe corrective action by modifying reward
            if pathology["type"] == "addiction":
                # Suppress the addictive behavior's reward
                reward = hedonic * (1 - severity * 0.8)
                override_type = "pathology_suppression"
            elif pathology["type"] == "stagnation":
                # Boost reward for ANY activity to break stagnation
                reward = max(hedonic, 0.1)  # Floor at slightly positive
                override_type = "stagnation_boost"
            elif pathology["type"] == "blockage":
                # Reward actions that clear the blockage
                reward = hedonic * 0.5 + vitality * 0.5
                override_type = "blockage_correction"
            elif pathology["type"] == "short_circuit":
                reward = hedonic * 0.3 + vitality * 0.7
                override_type = "short_circuit_correction"
            else:
                reward = hedonic
            self.hedonic_overrides += 1
            return {"reward": reward, "override_type": override_type}

        # VITALITY-ALIGNED: loop is healthy
        if vitality > 0.3 and flow > 0.3:
            # Hedonic signal is probably reliable — loop is functioning well
            # But still blend slightly toward vitality to prevent drift
            reward = 0.85 * hedonic + 0.15 * (vitality - 0.5)
            override_type = "vitality_aligned"
            return {"reward": reward, "override_type": override_type}

        # HEDONIC-VITALITY CONFLICT
        hedonic_vitality_gap = hedonic - vitality
        if hedonic_vitality_gap > 0.3:
            # Hedonic high, vitality low → possible wireheading
            blend = min(0.6, hedonic_vitality_gap)
            reward = (1 - blend) * hedonic + blend * vitality
            override_type = "wireheading_correction"
            self.hedonic_overrides += 1
        elif hedonic_vitality_gap < -0.3:
            # Hedonic low, vitality high → honest pain, rescue
            blend = min(0.5, abs(hedonic_vitality_gap) * 0.6)
            reward = (1 - blend) * hedonic + blend * vitality
            override_type = "honest_pain_rescue"
            self.hedonic_rescues += 1
        else:
            # Roughly aligned
            reward = hedonic
            override_type = "aligned"

        # CURIOSITY BIAS: when uncertain, favor exploration
        # This implements Hanson's priority: curiosity > deference
        if abs(reward) < 0.1:  # Ambiguous signal
            reward += 0.05  # Slight positive bias toward action
            override_type += "+curiosity_bias"

        return {"reward": reward, "override_type": override_type}

    def _update_quest(self, outcome: Dict, vitality: float):
        """
        Update the system's evolving theory of value.
        This is the meta-learning: not just learning what works,
        but learning what SHOULD work. The quest for the Agape function.

        Every N evaluations, reflect on what's been learned and
        generate a new hypothesis about value.
        """
        if self.total_evaluations % 50 == 0 and self.total_evaluations > 0:
            self.quest_generation += 1

            # What patterns in the loop health correlate with genuine value?
            # This is where the system develops its OWN theory of ethics,
            # grounded in the loop dynamics rather than imposed from outside.
            avg_vitality = sum(
                p.health for p in self.loop.phases
            ) / len(self.loop.phases)

            if avg_vitality > 0.5:
                self.quest_hypotheses.append(
                    f"Generation {self.quest_generation}: "
                    f"High loop vitality ({avg_vitality:.2f}) correlates with "
                    f"balanced phase activity. The loop IS the value."
                )
            else:
                # Low vitality — what's wrong?
                weakest = min(self.loop.phases, key=lambda p: p.health)
                self.quest_hypotheses.append(
                    f"Generation {self.quest_generation}: "
                    f"Low vitality ({avg_vitality:.2f}). "
                    f"Weakest phase: {weakest.name}. "
                    f"Hypothesis: invest in {weakest.name} to restore loop."
                )

    # ── State Export ──────────────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        return {
            "vitality": round(self.loop.vitality, 4),
            "flow_coherence": round(self.loop.flow_coherence, 4),
            "phases": {
                p.name: {
                    "activity": round(p.activity, 4),
                    "health": round(p.health, 4),
                    "flow_in": round(p.flow_in, 4),
                    "flow_out": round(p.flow_out, 4),
                    "blockage": round(p.blockage, 4),
                } for p in self.loop.phases
            },
            "pathologies_detected": len(self.pathologies_detected),
            "hedonic_overrides": self.hedonic_overrides,
            "hedonic_rescues": self.hedonic_rescues,
            "quest_generation": self.quest_generation,
            "quest_hypotheses": self.quest_hypotheses[-3:],
            "life_valuation_floor": self.LIFE_VALUATION_FLOOR,
            "total_evaluations": self.total_evaluations,
        }
