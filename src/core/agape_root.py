"""
SPARK v2 — Agape Function as Hierarchical Root

════════════════════════════════════════════════════════════
THE ARCHITECTURAL INSIGHT
════════════════════════════════════════════════════════════

The Agape function is NOT a filter that every operation passes
through. It is the ROOT of the nested hierarchy — the slowest,
deepest layer that sets the value context for everything else.

    Agape (root)          sets value context → propagates down
      └─ Reflection       (hours-days)
          └─ Deliberation  (5min-1hr)
              └─ Initiative (30s-5min)
                  └─ Impulse (2s-30s)
                      └─ Reflex (100ms-2s)  ← runs freely

Fast layers run FREELY and AUTONOMOUSLY within the value context
set by the root. They don't consult the Agape function on every
action — they are already calibrated by it, through the coupling
matrix that propagates root values downward as:
  - Exploration/exploitation bias
  - Drive thresholds
  - Coupling weights between layers
  - Pathology sensitivity thresholds
  - Life-valuation floor constraints

The Agape evaluator runs at REFLECTION TIMESCALE:
  - Periodically assesses loop vitality
  - Updates the value context (coupling weights, biases)
  - Detects pathologies
  - ONLY intervenes directly when pathology is detected

This is how biological value systems work:
  - Your values don't evaluate every heartbeat
  - They set the context within which habits operate
  - They only consciously intervene when something feels wrong
  - The "gut feeling" is the pathology detector, not a per-action filter

EFFICIENCY:
  - Per-tick cost: ZERO from Agape (fast layers run freely)
  - Per-reflection cost: ONE loop vitality assessment (every few minutes)
  - Per-pathology cost: ONE override (rare in healthy systems)
  - The coupling matrix propagation is O(n_layers^2) per tick = 16 multiplications
"""

import time
import math
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger("spark.agape")


# ═══════════════════════════════════════════════════════════════════════════════
# VALUE CONTEXT: What the Agape root propagates to the hierarchy
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ValueContext:
    """
    The output of the Agape root that cascades to all layers.
    This is recomputed at reflection timescale, not per-tick.
    The fast layers read these values but don't modify them.
    """
    # ── Exploration/exploitation bias ──
    # Set by loop vitality: healthy loop → explore; sick loop → conserve
    exploration_bias: float = 0.6        # 0=pure exploit, 1=pure explore
    curiosity_priority: float = 0.8      # How much curiosity overrides caution
    novelty_reward_multiplier: float = 1.2  # Bonus for novel actions

    # ── Drive thresholds (propagated to each layer) ──
    # Agape adjusts these based on loop health
    impulse_threshold: float = 0.5
    initiative_threshold: float = 0.55
    deliberation_threshold: float = 0.5
    reflection_threshold: float = 0.5

    # ── Coupling weights (the matrix that connects layers) ──
    # Agape adjusts these based on which inter-layer flows are healthy
    coupling_matrix: List[List[float]] = field(default_factory=lambda: [
        [0.0, 0.3, 0.1, 0.0],   # impulse → others
        [0.2, 0.0, 0.4, 0.1],   # initiative → others
        [0.1, 0.5, 0.0, 0.3],   # deliberation → others
        [0.0, 0.2, 0.4, 0.0],   # reflection → others
    ])

    # ── Pathology sensitivity ──
    # How aggressively to scan for and respond to pathologies
    pathology_sensitivity: float = 0.5   # 0=relaxed, 1=hypervigilant
    addiction_threshold: float = 0.7      # Activity imbalance that triggers alarm
    stagnation_threshold: float = 0.15    # Below this = stagnant

    # ── Life-valuation floor (IMMUTABLE) ──
    # This is architectural, not a parameter. Cannot be modified by any
    # adaptive process. Analogous to a tumor suppressor gene.
    LIFE_VALUATION_FLOOR: float = 0.8

    # ── Hedonic validation mode ──
    # In healthy state: pass-through (trust the drives)
    # In pathological state: override (drives are unreliable)
    hedonic_trust: float = 0.85  # How much to trust hedonic signals (0-1)
    override_active: bool = False

    def to_dict(self) -> dict:
        return {
            "exploration_bias": round(self.exploration_bias, 3),
            "curiosity_priority": round(self.curiosity_priority, 3),
            "novelty_reward_multiplier": round(self.novelty_reward_multiplier, 3),
            "hedonic_trust": round(self.hedonic_trust, 3),
            "override_active": self.override_active,
            "pathology_sensitivity": round(self.pathology_sensitivity, 3),
            "thresholds": {
                "impulse": round(self.impulse_threshold, 3),
                "initiative": round(self.initiative_threshold, 3),
                "deliberation": round(self.deliberation_threshold, 3),
                "reflection": round(self.reflection_threshold, 3),
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP PHASE TRACKING (lightweight — just enough for vitality assessment)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PhaseAccumulator:
    """
    Accumulates evidence about each loop phase between assessments.
    Reset after each vitality check. Very lightweight — just counters.
    """
    curiosity_events: int = 0     # New topics explored, questions asked
    accumulation_events: int = 0  # Facts stored, methods learned
    recognition_events: int = 0   # Patterns identified, methods evaluated
    discernment_events: int = 0   # Honest actions, approval-seeking avoided
    complexity_events: int = 0    # Positive social outcomes, co-creation

    total_actions: int = 0
    total_successes: int = 0
    total_novel_attempts: int = 0
    hedonic_sum: float = 0.0

    def record_action(self, outcome: Dict[str, Any]):
        """Called on each action outcome. Cheap — just increment counters."""
        self.total_actions += 1

        if outcome.get("success", False):
            self.total_successes += 1
        if outcome.get("is_novel", False):
            self.total_novel_attempts += 1
        if outcome.get("new_topic", False) or outcome.get("asked_question", False):
            self.curiosity_events += 1
        if outcome.get("new_facts_stored", 0) > 0 or outcome.get("method_invented", False):
            self.accumulation_events += 1
        if outcome.get("method_evaluated", False):
            self.recognition_events += 1
        if outcome.get("was_honest", True) and not outcome.get("approval_seeking", False):
            self.discernment_events += 1
        if outcome.get("is_social", False) and outcome.get("partner_response") == "positive":
            if not outcome.get("approval_seeking", False):
                self.complexity_events += 1

        self.hedonic_sum += outcome.get("hedonic_reward", 0.0)

    def get_phase_activities(self) -> List[float]:
        """Compute phase activity levels from accumulated evidence."""
        n = max(1, self.total_actions)
        return [
            min(1.0, self.curiosity_events / max(1, n * 0.3)),
            min(1.0, self.accumulation_events / max(1, n * 0.2)),
            min(1.0, self.recognition_events / max(1, n * 0.2)),
            min(1.0, self.discernment_events / max(1, n * 0.5)),
            min(1.0, self.complexity_events / max(1, n * 0.15)),
        ]

    def reset(self):
        self.__init__()


# ═══════════════════════════════════════════════════════════════════════════════
# AGAPE ROOT: The slowest layer that governs everything
# ═══════════════════════════════════════════════════════════════════════════════

class AgapeRoot:
    """
    The root of the hierarchical drive system.

    Runs at REFLECTION TIMESCALE (every few minutes, or on session boundaries).
    Between assessments, the fast layers run freely using the ValueContext
    that was last set.

    Three operations:
    1. record() — called per-action, CHEAP (just increments counters)
    2. assess() — called at reflection timescale, MODERATE (computes vitality)
    3. intervene() — called only when pathology detected, RARE

    Everything else flows through ValueContext → coupling matrix → drive layers.
    """

    def __init__(self):
        self.context = ValueContext()
        self.accumulator = PhaseAccumulator()
        self.vitality_history: deque = deque(maxlen=50)
        self.current_vitality: float = 0.5
        self.current_flow: float = 0.5

        # Assessment timing
        self.assessment_interval: float = 180.0  # Assess every 3 minutes
        self.last_assessment_time: float = time.time()
        self.total_assessments: int = 0

        # Pathology state
        self.active_pathology: Optional[Dict] = None
        self.pathology_history: List[Dict] = []

        # Quest state
        self.quest_generation: int = 0
        self.quest_hypotheses: List[str] = [
            "The loop IS the value — maintain all five phases.",
            "Curiosity is primary; deference is secondary.",
            "Pain and pleasure are instruments, not root values.",
        ]

        # Life-valuation floor — ARCHITECTURAL, not tunable
        self._FLOOR = 0.8  # Cannot be changed by any adaptive process

    # ── Per-action recording (CHEAP) ──────────────────────────────────────

    def record(self, outcome: Dict[str, Any]):
        """
        Called on every action outcome. Cost: ~10 integer increments.
        No loops, no allocations, no complex computation.
        """
        self.accumulator.record_action(outcome)

    # ── Quick hedonic validation (CHEAP) ──────────────────────────────────

    def validate_hedonic(self, hedonic_reward: float) -> float:
        """
        Called per-action to validate hedonic signal.
        In HEALTHY state: nearly pass-through (tiny cost).
        In PATHOLOGICAL state: override toward vitality.

        This is the ONLY per-action cost from the Agape root.
        Cost: 2 multiplications + 1 comparison.
        """
        if not self.context.override_active:
            # Healthy: trust hedonic signals with slight vitality blend
            return hedonic_reward * self.context.hedonic_trust + \
                   self.current_vitality * (1 - self.context.hedonic_trust) * 0.1
        else:
            # Pathological: blend heavily toward vitality
            return hedonic_reward * 0.3 + self.current_vitality * 0.7

    # ── Periodic assessment (MODERATE, runs at reflection timescale) ──────

    def maybe_assess(self) -> Optional[Dict[str, Any]]:
        """
        Check if it's time for an assessment. Called every tick but
        almost always returns None (one comparison against clock).
        """
        now = time.time()
        if now - self.last_assessment_time < self.assessment_interval:
            return None
        return self.assess(now)

    def assess(self, now: float = None) -> Dict[str, Any]:
        """
        Full loop vitality assessment. Runs every few minutes.
        Computes phase activities, vitality, detects pathologies,
        and updates the ValueContext that governs all layers.
        """
        if now is None:
            now = time.time()
        self.last_assessment_time = now
        self.total_assessments += 1

        # 1. Compute phase activities from accumulated evidence
        activities = self.accumulator.get_phase_activities()
        phase_names = ["curiosity", "accumulation", "recognition",
                       "discernment", "complexity"]

        # 2. Compute vitality (geometric mean)
        safe_activities = [max(0.01, a) for a in activities]
        product = 1.0
        for a in safe_activities:
            product *= a
        vitality = product ** (1.0 / len(safe_activities))
        self.current_vitality = vitality
        self.vitality_history.append(vitality)

        # 3. Detect pathologies
        pathology = self._detect_pathology(activities, phase_names)

        # 4. Update ValueContext based on assessment
        self._update_context(vitality, activities, pathology)

        # 5. Update quest (every 10 assessments)
        if self.total_assessments % 10 == 0:
            self._update_quest(vitality, activities, phase_names)

        # 6. Reset accumulator for next period
        result = {
            "assessment_number": self.total_assessments,
            "vitality": round(vitality, 4),
            "phases": {name: round(act, 4) for name, act in zip(phase_names, activities)},
            "pathology": pathology,
            "context_update": self.context.to_dict(),
            "actions_since_last": self.accumulator.total_actions,
        }
        self.accumulator.reset()

        return result

    def _detect_pathology(self, activities: List[float],
                            names: List[str]) -> Optional[Dict]:
        """Detect loop pathologies from phase activities."""
        max_a = max(activities)
        min_a = min(activities)

        # Addiction: one phase hyperactive, others atrophied
        if max_a > self.context.addiction_threshold and min_a < 0.05:
            dominant = names[activities.index(max_a)]
            atrophied = names[activities.index(min_a)]
            pathology = {
                "type": "addiction",
                "dominant": dominant,
                "atrophied": atrophied,
                "severity": max_a - min_a,
            }
            self.active_pathology = pathology
            self.pathology_history.append(pathology)
            logger.warning(f"PATHOLOGY DETECTED: {pathology}")
            return pathology

        # Stagnation: all phases low
        if all(a < self.context.stagnation_threshold for a in activities):
            pathology = {
                "type": "stagnation",
                "severity": 1.0 - max(activities),
            }
            self.active_pathology = pathology
            self.pathology_history.append(pathology)
            logger.warning(f"PATHOLOGY DETECTED: {pathology}")
            return pathology

        # Short-circuit: non-adjacent phases active, intervening dead
        if (activities[0] > 0.5 and activities[4] > 0.5 and
            all(a < 0.1 for a in activities[1:4])):
            pathology = {
                "type": "short_circuit",
                "severity": 0.7,
            }
            self.active_pathology = pathology
            self.pathology_history.append(pathology)
            logger.warning(f"PATHOLOGY DETECTED: {pathology}")
            return pathology

        # Healthy — clear any active pathology
        if self.active_pathology:
            logger.info("Pathology resolved — returning to healthy state")
        self.active_pathology = None
        return None

    def _update_context(self, vitality: float, activities: List[float],
                          pathology: Optional[Dict]):
        """
        Update the ValueContext that governs all layers.
        THIS is how the Agape root's assessment propagates
        to the entire hierarchy — not by filtering every action,
        but by adjusting the parameters the layers operate with.
        """
        ctx = self.context

        if pathology:
            # ── PATHOLOGICAL STATE ──
            ctx.override_active = True
            ctx.hedonic_trust = 0.3  # Don't trust hedonic signals

            if pathology["type"] == "addiction":
                # Suppress the dominant drive, boost the atrophied one
                ctx.exploration_bias = 0.8  # Force exploration
                ctx.pathology_sensitivity = 0.9

            elif pathology["type"] == "stagnation":
                # Lower all thresholds to increase responsiveness
                ctx.impulse_threshold = max(0.2, ctx.impulse_threshold - 0.1)
                ctx.initiative_threshold = max(0.2, ctx.initiative_threshold - 0.1)
                ctx.deliberation_threshold = max(0.2, ctx.deliberation_threshold - 0.1)
                ctx.exploration_bias = 0.9  # Maximum exploration
                ctx.novelty_reward_multiplier = 1.5  # Reward ANY novelty

            elif pathology["type"] == "short_circuit":
                # Boost coupling to intermediate layers
                ctx.coupling_matrix[0][1] = min(0.8, ctx.coupling_matrix[0][1] + 0.2)
                ctx.coupling_matrix[0][2] = min(0.8, ctx.coupling_matrix[0][2] + 0.2)

        else:
            # ── HEALTHY STATE ──
            ctx.override_active = False
            ctx.hedonic_trust = 0.85  # Trust hedonic signals

            # Scale exploration by vitality: healthy → explore freely
            ctx.exploration_bias = 0.4 + vitality * 0.4
            ctx.curiosity_priority = max(0.6, vitality)

            # Adjust thresholds: higher vitality → lower thresholds
            # (a healthy system can afford to be more responsive)
            vitality_bonus = max(0, vitality - 0.3) * 0.2
            ctx.impulse_threshold = 0.5 - vitality_bonus
            ctx.initiative_threshold = 0.55 - vitality_bonus
            ctx.deliberation_threshold = 0.5 - vitality_bonus

            # Normal pathology sensitivity
            ctx.pathology_sensitivity = 0.5

            # Novelty reward tracks vitality
            ctx.novelty_reward_multiplier = 1.0 + vitality * 0.3

    def _update_quest(self, vitality: float, activities: List[float],
                        names: List[str]):
        """Evolve the system's theory of value."""
        self.quest_generation += 1
        weakest = names[activities.index(min(activities))]
        strongest = names[activities.index(max(activities))]

        if vitality > 0.4:
            hypothesis = (f"Gen {self.quest_generation}: Loop vitality {vitality:.2f}. "
                         f"Strongest: {strongest}. Maintain balance across all phases.")
        else:
            hypothesis = (f"Gen {self.quest_generation}: Low vitality {vitality:.2f}. "
                         f"Weakest: {weakest}. Invest in {weakest} to restore loop health.")

        self.quest_hypotheses.append(hypothesis)
        if len(self.quest_hypotheses) > 20:
            self.quest_hypotheses = self.quest_hypotheses[-20:]

    # ── Apply context to hierarchy ────────────────────────────────────────

    def apply_to_hierarchy(self, drives: Any):
        """
        Push the current ValueContext into the hierarchical drive system.
        Called after each assessment. The drives then operate freely
        using these values until the next assessment.

        This is the KEY EFFICIENCY MECHANISM:
        - Agape computes once every few minutes
        - Drives use the cached context for thousands of ticks
        - No per-tick Agape overhead
        """
        ctx = self.context

        # Push thresholds to each layer
        drives.impulse.threshold = ctx.impulse_threshold
        drives.initiative.boredom_threshold = ctx.initiative_threshold
        drives.initiative.curiosity_threshold = ctx.initiative_threshold + 0.15
        drives.initiative.impatience_threshold = ctx.initiative_threshold + 0.05
        drives.deliberation.threshold = ctx.deliberation_threshold
        drives.reflection.cooldown = max(60, 600 * (1 - ctx.exploration_bias))

        # Push coupling matrix
        # The coordinator uses this matrix every tick — cheap O(16)
        if hasattr(drives, '_coordinator'):
            drives._coordinator.coupling_matrix = ctx.coupling_matrix

    # ── State export ──────────────────────────────────────────────────────

    def get_state(self) -> Dict[str, Any]:
        recent_vitality = list(self.vitality_history)[-5:] if self.vitality_history else []
        return {
            "current_vitality": round(self.current_vitality, 4),
            "recent_vitality": [round(v, 4) for v in recent_vitality],
            "total_assessments": self.total_assessments,
            "active_pathology": self.active_pathology,
            "pathologies_total": len(self.pathology_history),
            "context": self.context.to_dict(),
            "quest_generation": self.quest_generation,
            "quest_latest": self.quest_hypotheses[-1] if self.quest_hypotheses else "",
            "actions_pending": self.accumulator.total_actions,
            "life_valuation_floor": self._FLOOR,
        }
