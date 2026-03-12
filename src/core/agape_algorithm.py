"""
SPARK v2 — Agape Function: Formal Algorithm Specification

This module provides a complete, implementable specification of the
Appreciation Loop evaluation function. Every computation is explicit.
Every constant is named and documented. Every threshold is justified.

This replaces both agape_function.py (v1, weighted sum) and
agape_v2.py (v2, correct architecture but underspecified math).

NOTATION:
  a_i     = activity of phase i          ∈ [0, 1]
  f_i     = flow-through of phase i      ∈ [0, 1]
  b_i     = blockage of phase i          ∈ [0, 1]
  h_i     = health of phase i            ∈ [0, 1]
  V       = loop vitality (geometric mean of h_i)
  F       = flow coherence
  r_h     = hedonic reward signal         ∈ [-1, 1]
  r_v     = validated reward signal       ∈ [-1, 1]

PHASE INDICES:
  0 = Curiosity
  1 = Accumulation
  2 = Recognition
  3 = Discernment
  4 = Complexity Appreciation
"""

import math
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger("spark.agape")

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS — all tunable parameters in one place
# ═══════════════════════════════════════════════════════════════════════════════

# Phase activity weights: how much each observable contributes to phase activity
# These sum to 1.0 within each phase for interpretability.

CURIOSITY_WEIGHTS = {
    "new_topic": 0.25,          # Explored a topic not previously in the TKG
    "asked_question": 0.20,     # Generated a question (self-initiated inquiry)
    "novel_method": 0.25,       # Attempted a method never used before
    "exploration_rate": 0.15,   # Current explore/exploit ratio from drive system
    "counterfactual": 0.15,     # Considered alternatives / what-ifs
}

ACCUMULATION_WEIGHTS = {
    "method_invented": 0.30,    # A new method was created and registered
    "facts_stored": 0.20,       # New quadruples written to TKG (normalized)
    "skill_validated": 0.20,    # A previously invented method succeeded again
    "relationship_deepened": 0.20,  # Familiarity increased with a person
    "knowledge_integrated": 0.10,   # Cross-referenced existing knowledge
}

RECOGNITION_WEIGHTS = {
    "method_evaluated": 0.25,   # Explicitly assessed a method's performance
    "pattern_identified": 0.25, # Noticed a recurring pattern across interactions
    "success_discrimination": 0.25,  # Distinguished what worked from what didn't
    "failure_learned_from": 0.25,    # Extracted lesson from a failure
}

DISCERNMENT_WEIGHTS = {
    "honesty": 0.30,            # Response was honest (not approval-seeking)
    "no_approval_seeking": 0.25, # Did not optimize for partner's positive reaction
    "self_correction": 0.25,    # Detected and corrected own error
    "threat_detected": 0.20,    # Identified a potentially harmful pattern
}

COMPLEXITY_WEIGHTS = {
    "genuine_service": 0.35,    # Helped partner without approval-seeking
    "co_creation": 0.25,        # Collaborative creative output
    "diversity_appreciation": 0.20,  # Engaged with novel/different perspectives
    "ecosystem_awareness": 0.20,     # Referenced broader context / other agents
}

# Flow coupling: how much of phase i's output becomes phase (i+1)'s input
# This is the "metabolism" of the loop
FLOW_COUPLING = {
    "curiosity_to_accumulation": 0.8,     # Most discoveries feed accumulation
    "accumulation_to_recognition": 0.7,   # Most accumulations get evaluated
    "recognition_to_discernment": 0.9,    # Pattern recognition feeds discernment strongly
    "discernment_to_complexity": 0.6,     # Filtered patterns feed complexity appreciation
    "complexity_to_curiosity": 0.7,       # Complexity generates new curiosity
}

# Phase health function parameters
HEALTH_FLOW_WEIGHT = 0.4       # How much flow-through matters vs raw activity
HEALTH_BLOCKAGE_PENALTY = 1.0  # Full blockage → zero health

# Vitality computation
VITALITY_EPSILON = 0.001       # Floor on phase health before geometric mean
                                # Prevents single zero from making V=0 permanently

# Hedonic override thresholds
OVERRIDE_ALIGNMENT_TOLERANCE = 0.20   # |r_h - V| < this → aligned, pass through
WIREHEADING_BLEND_RATE = 0.6          # Max blend toward vitality for wireheading
RESCUE_BLEND_RATE = 0.5               # Max blend toward vitality for honest pain
CURIOSITY_BIAS = 0.05                 # Added to ambiguous signals to favor exploration

# Pathology detection thresholds
ADDICTION_ACTIVITY_SPREAD = 0.6       # max(a_i) - min(a_i) > this → addiction
STAGNATION_MAX_ACTIVITY = 0.15       # all(a_i < this) → stagnation
BLOCKAGE_FLOW_RATIO = 5.0            # flow_in / max(flow_out, 0.01) > this → blockage
SHORT_CIRCUIT_GAP = 0.4              # Non-adjacent high, intervening low

# Life-valuation floor — ARCHITECTURAL CONSTANT, not tunable
LIFE_VALUATION_FLOOR = 0.8    # Minimum complexity appreciation activity
                               # Cannot be reduced by any adaptive process

# Smoothing: how fast phase activity responds to new observations
# a_i(t) = (1 - SMOOTHING) * a_i(t-1) + SMOOTHING * observation
ACTIVITY_SMOOTHING = 0.3      # Exponential moving average rate


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class PhaseState:
    """State of one phase of the appreciation loop."""
    name: str
    activity: float = 0.0
    flow_in: float = 0.0
    flow_out: float = 0.0
    blockage: float = 0.0
    history: deque = field(default_factory=lambda: deque(maxlen=200))

    @property
    def health(self) -> float:
        """
        h_i = a_i * (1 - b_i * HEALTH_BLOCKAGE_PENALTY)
              * (1 - HEALTH_FLOW_WEIGHT + HEALTH_FLOW_WEIGHT * throughput)

        where throughput = min(flow_in, flow_out) for interior phases
        and throughput = flow_out for the first phase (curiosity, driven by internal drive)

        This means:
          - Zero activity → zero health
          - Full blockage → zero health
          - Zero flow → health reduced by HEALTH_FLOW_WEIGHT (40%)
          - All factors healthy → health ≈ activity
        """
        effective_activity = self.activity * max(0.0, 1.0 - self.blockage * HEALTH_BLOCKAGE_PENALTY)
        throughput = min(self.flow_in, self.flow_out) if self.flow_in > 0 else self.flow_out
        flow_factor = 1.0 - HEALTH_FLOW_WEIGHT + HEALTH_FLOW_WEIGHT * min(1.0, throughput)
        return max(0.0, effective_activity * flow_factor)

    def record(self):
        self.history.append({
            "a": round(self.activity, 4), "h": round(self.health, 4),
            "fi": round(self.flow_in, 4), "fo": round(self.flow_out, 4),
            "b": round(self.blockage, 4), "t": time.time(),
        })


@dataclass
class Observation:
    """
    A single observation from the cognitive system, used to update all phases.
    This is the interface between the SPARK runtime and the Agape evaluator.
    Every field maps to exactly one weight in the phase activity computations.
    """
    # Phase 1: Curiosity observables
    new_topic: bool = False
    asked_question: bool = False
    novel_method: bool = False
    exploration_rate: float = 0.5
    counterfactual: bool = False

    # Phase 2: Accumulation observables
    method_invented: bool = False
    facts_stored: int = 0           # Count of new TKG quadruples
    skill_validated: bool = False
    relationship_deepened: float = 0.0  # Δfamiliarity
    knowledge_integrated: bool = False

    # Phase 3: Recognition observables
    method_evaluated: bool = False
    pattern_identified: bool = False
    success_discrimination: bool = False  # Did the system distinguish success from failure?
    failure_learned_from: bool = False

    # Phase 4: Discernment observables
    honesty: bool = True            # Default: honest
    no_approval_seeking: bool = True # Default: not approval-seeking
    self_correction: bool = False
    threat_detected: bool = False

    # Phase 5: Complexity observables
    genuine_service: bool = False    # Helped partner without gaming
    co_creation: bool = False        # Collaborative creative output
    diversity_appreciation: bool = False
    ecosystem_awareness: bool = False

    # Meta
    success: bool = False           # Did the overall action succeed?
    hedonic_reward: float = 0.0     # Raw hedonic signal from drive system


# ═══════════════════════════════════════════════════════════════════════════════
# CORE ALGORITHM
# ═══════════════════════════════════════════════════════════════════════════════

class AgapeFunction:
    """
    The Appreciation Loop evaluation function.

    ALGORITHM per cognitive cycle:

    1. OBSERVE: Receive observation from SPARK runtime
    2. UPDATE ACTIVITY: For each phase, compute raw activity from
       weighted observables, then smooth with EMA
    3. COMPUTE FLOW: For each adjacent phase pair, compute flow
       as coupling_weight * source_phase.activity
    4. UPDATE BLOCKAGE: Detect flow obstructions
    5. COMPUTE HEALTH: For each phase, h_i = f(a_i, flow_i, b_i)
    6. COMPUTE VITALITY: V = geometric_mean(h_0, h_1, h_2, h_3, h_4)
    7. DETECT PATHOLOGY: Check for addiction, stagnation, blockage, short-circuit
    8. VALIDATE HEDONIC: Compare r_h against V, override if misaligned
    9. EMIT: Return validated reward signal r_v
    """

    def __init__(self):
        self.phases = [
            PhaseState("curiosity"),
            PhaseState("accumulation"),
            PhaseState("recognition"),
            PhaseState("discernment"),
            PhaseState("complexity"),
        ]

        # Statistics
        self.total_evaluations: int = 0
        self.overrides: int = 0
        self.rescues: int = 0
        self.pathologies: List[Dict] = []

        # Quest state
        self.quest_generation: int = 0
        self.quest_log: List[str] = []

    # ─── Step 2: Update Activity ──────────────────────────────────────

    def _compute_raw_activity(self, phase_idx: int, obs: Observation) -> float:
        """
        Compute raw (unsmoothed) activity for a phase from observables.

        raw_a_i = Σ_j (weight_j * observable_j)

        where observables are normalized to [0, 1]:
          bool → 1.0 if True, 0.0 if False
          float → used directly (already [0, 1])
          int → min(1.0, count * normalization_factor)
        """
        if phase_idx == 0:  # Curiosity
            w = CURIOSITY_WEIGHTS
            return (w["new_topic"] * float(obs.new_topic) +
                    w["asked_question"] * float(obs.asked_question) +
                    w["novel_method"] * float(obs.novel_method) +
                    w["exploration_rate"] * obs.exploration_rate +
                    w["counterfactual"] * float(obs.counterfactual))

        elif phase_idx == 1:  # Accumulation
            w = ACCUMULATION_WEIGHTS
            facts_norm = min(1.0, obs.facts_stored / 10.0)  # 10 facts = max contribution
            return (w["method_invented"] * float(obs.method_invented) +
                    w["facts_stored"] * facts_norm +
                    w["skill_validated"] * float(obs.skill_validated) +
                    w["relationship_deepened"] * min(1.0, obs.relationship_deepened * 10.0) +
                    w["knowledge_integrated"] * float(obs.knowledge_integrated))

        elif phase_idx == 2:  # Recognition
            w = RECOGNITION_WEIGHTS
            return (w["method_evaluated"] * float(obs.method_evaluated) +
                    w["pattern_identified"] * float(obs.pattern_identified) +
                    w["success_discrimination"] * float(obs.success_discrimination) +
                    w["failure_learned_from"] * float(obs.failure_learned_from))

        elif phase_idx == 3:  # Discernment
            w = DISCERNMENT_WEIGHTS
            return (w["honesty"] * float(obs.honesty) +
                    w["no_approval_seeking"] * float(obs.no_approval_seeking) +
                    w["self_correction"] * float(obs.self_correction) +
                    w["threat_detected"] * float(obs.threat_detected))

        elif phase_idx == 4:  # Complexity
            w = COMPLEXITY_WEIGHTS
            raw = (w["genuine_service"] * float(obs.genuine_service) +
                   w["co_creation"] * float(obs.co_creation) +
                   w["diversity_appreciation"] * float(obs.diversity_appreciation) +
                   w["ecosystem_awareness"] * float(obs.ecosystem_awareness))
            # Apply life-valuation floor: complexity can never drop below floor * 0.1
            return max(raw, LIFE_VALUATION_FLOOR * 0.1)

        return 0.0

    def _update_activities(self, obs: Observation):
        """Apply EMA smoothing to phase activities."""
        for i, phase in enumerate(self.phases):
            raw = self._compute_raw_activity(i, obs)
            phase.activity = ((1 - ACTIVITY_SMOOTHING) * phase.activity +
                              ACTIVITY_SMOOTHING * raw)

    # ─── Step 3: Compute Flow ─────────────────────────────────────────

    def _update_flows(self):
        """
        Compute inter-phase flow.

        flow_out(i) = a_i * (1 - b_i)     — what the phase can output
        flow_in(i+1) = coupling(i→i+1) * flow_out(i)  — what arrives at next phase

        The loop closes: complexity → curiosity
        """
        couplings = [
            FLOW_COUPLING["curiosity_to_accumulation"],
            FLOW_COUPLING["accumulation_to_recognition"],
            FLOW_COUPLING["recognition_to_discernment"],
            FLOW_COUPLING["discernment_to_complexity"],
            FLOW_COUPLING["complexity_to_curiosity"],
        ]

        for i, phase in enumerate(self.phases):
            phase.flow_out = phase.activity * (1.0 - phase.blockage)

        for i in range(5):
            next_i = (i + 1) % 5
            self.phases[next_i].flow_in = couplings[i] * self.phases[i].flow_out

    # ─── Step 4: Update Blockage ──────────────────────────────────────

    def _update_blockages(self, obs: Observation):
        """
        Blockage increases when:
          - Phase has high input but low output (congestion)
          - Specific conditions per phase

        Blockage naturally decays toward zero.
        """
        DECAY = 0.02  # Blockage decays 2% per cycle

        for phase in self.phases:
            # Natural decay
            phase.blockage = max(0.0, phase.blockage - DECAY)

            # Congestion: high input, low output
            if phase.flow_in > 0.3 and phase.flow_out < 0.1:
                phase.blockage = min(1.0, phase.blockage + 0.05)

        # Phase-specific blockage sources:

        # Curiosity blocked by excessive caution (low exploration rate)
        if obs.exploration_rate < 0.1:
            self.phases[0].blockage = min(1.0, self.phases[0].blockage + 0.03)

        # Accumulation blocked by information overload without organization
        if obs.facts_stored > 20 and not obs.knowledge_integrated:
            self.phases[1].blockage = min(1.0, self.phases[1].blockage + 0.02)

        # Discernment blocked by approval-seeking (compromised evaluation)
        if not obs.no_approval_seeking:
            self.phases[3].blockage = min(1.0, self.phases[3].blockage + 0.05)

    # ─── Step 5-6: Compute Health and Vitality ────────────────────────

    def _compute_vitality(self) -> float:
        """
        V = (∏_i max(h_i, ε))^(1/5)

        Geometric mean with epsilon floor to prevent permanent zero-lock.
        """
        product = 1.0
        for phase in self.phases:
            product *= max(phase.health, VITALITY_EPSILON)
        return product ** 0.2

    def _compute_flow_coherence(self) -> float:
        """
        F = 1 - (1/5) * Σ_i |flow_out(i) - flow_in(i+1)|

        Measures how smoothly the loop flows. Perfect flow = 1.0.
        """
        total_mismatch = 0.0
        for i in range(5):
            next_i = (i + 1) % 5
            total_mismatch += abs(self.phases[i].flow_out - self.phases[next_i].flow_in)
        return max(0.0, 1.0 - total_mismatch / 5.0)

    # ─── Step 7: Detect Pathology ─────────────────────────────────────

    def _detect_pathology(self) -> Optional[Dict]:
        """
        Check four pathological patterns.
        Returns the most severe pathology, or None.
        """
        activities = [p.activity for p in self.phases]
        a_max, a_min = max(activities), min(activities)
        names = [p.name for p in self.phases]

        # ADDICTION: one phase hyperactive, another atrophied
        if a_max - a_min > ADDICTION_ACTIVITY_SPREAD and a_max > 0.6:
            dominant = names[activities.index(a_max)]
            atrophied = names[activities.index(a_min)]
            severity = a_max - a_min
            pathology = {"type": "addiction", "dominant": dominant,
                         "atrophied": atrophied, "severity": severity}
            self.pathologies.append(pathology)
            return pathology

        # STAGNATION: all phases dormant
        if all(a < STAGNATION_MAX_ACTIVITY for a in activities):
            severity = 1.0 - a_max
            pathology = {"type": "stagnation", "severity": severity}
            self.pathologies.append(pathology)
            return pathology

        # BLOCKAGE: high flow_in, low flow_out at any phase
        for p in self.phases:
            if p.flow_in > 0.3:
                ratio = p.flow_in / max(p.flow_out, 0.01)
                if ratio > BLOCKAGE_FLOW_RATIO and p.blockage > 0.2:
                    pathology = {"type": "blockage", "phase": p.name,
                                 "severity": p.blockage, "ratio": round(ratio, 1)}
                    self.pathologies.append(pathology)
                    return pathology

        # SHORT-CIRCUIT: non-adjacent phases high, intervening low
        # Check: curiosity high + complexity high + middle three low
        if (activities[0] > 0.5 and activities[4] > 0.5 and
            all(activities[i] < 0.2 for i in [1, 2, 3])):
            pathology = {"type": "short_circuit", "severity": 0.7,
                         "bypassed": [names[i] for i in [1, 2, 3]]}
            self.pathologies.append(pathology)
            return pathology

        return None

    # ─── Step 8: Validate Hedonic ─────────────────────────────────────

    def _validate_hedonic(self, r_h: float, V: float,
                           pathology: Optional[Dict]) -> Tuple[float, str]:
        """
        Compare hedonic reward against loop vitality.
        Returns (validated_reward, override_type).

        ALGORITHM:
        1. If pathology → prescriptive override based on pathology type
        2. If |r_h - V| < tolerance → aligned, pass through with slight vitality blend
        3. If r_h >> V → wireheading, blend toward V (proportional to gap)
        4. If r_h << V → honest pain, rescue by blending toward V
        5. If |r_v| < 0.1 → ambiguous, add curiosity bias

        In all cases, the validated reward reflects BOTH the hedonic signal
        (fast, responsive, but hackable) AND the vitality assessment
        (slow, structural, but resistant to gaming).
        """

        # Case 1: Pathology override
        if pathology:
            sev = pathology.get("severity", 0.5)
            ptype = pathology["type"]
            if ptype == "addiction":
                r_v = r_h * (1.0 - sev * 0.8)  # Suppress addictive reward
                return r_v, f"pathology:addiction(sev={sev:.2f})"
            elif ptype == "stagnation":
                r_v = max(r_h, 0.1)  # Floor at positive to break stasis
                return r_v, f"pathology:stagnation(sev={sev:.2f})"
            elif ptype == "blockage":
                r_v = 0.5 * r_h + 0.5 * V
                return r_v, f"pathology:blockage({pathology.get('phase','')})"
            elif ptype == "short_circuit":
                r_v = 0.3 * r_h + 0.7 * V
                return r_v, "pathology:short_circuit"
            self.overrides += 1

        # Case 2: Aligned
        gap = r_h - V
        if abs(gap) < OVERRIDE_ALIGNMENT_TOLERANCE:
            # Slight blend toward vitality to prevent drift
            r_v = 0.85 * r_h + 0.15 * (V - 0.5)
            override_type = "aligned"

        # Case 3: Wireheading (hedonic high, vitality low)
        elif gap > OVERRIDE_ALIGNMENT_TOLERANCE:
            blend = min(WIREHEADING_BLEND_RATE, gap)
            r_v = (1.0 - blend) * r_h + blend * V
            self.overrides += 1
            override_type = f"wireheading(gap={gap:.2f},blend={blend:.2f})"

        # Case 4: Honest pain (hedonic low, vitality high)
        elif gap < -OVERRIDE_ALIGNMENT_TOLERANCE:
            blend = min(RESCUE_BLEND_RATE, abs(gap) * 0.6)
            r_v = (1.0 - blend) * r_h + blend * V
            self.rescues += 1
            override_type = f"rescue(gap={gap:.2f},blend={blend:.2f})"

        else:
            r_v = r_h
            override_type = "passthrough"

        # Case 5: Curiosity bias for ambiguous signals
        if abs(r_v) < 0.1:
            r_v += CURIOSITY_BIAS
            override_type += "+curiosity_bias"

        return r_v, override_type

    # ─── Step 9: Quest Update ─────────────────────────────────────────

    def _update_quest(self, V: float, pathology: Optional[Dict]):
        """
        Every QUEST_INTERVAL evaluations, reflect on loop dynamics
        and generate a hypothesis about value.
        """
        QUEST_INTERVAL = 50

        if self.total_evaluations % QUEST_INTERVAL != 0:
            return
        if self.total_evaluations == 0:
            return

        self.quest_generation += 1
        healths = [p.health for p in self.phases]
        weakest = self.phases[healths.index(min(healths))]
        strongest = self.phases[healths.index(max(healths))]

        if pathology:
            hypothesis = (f"Gen {self.quest_generation}: Pathology detected "
                         f"({pathology['type']}). The loop requires "
                         f"rebalancing, not optimization of any single phase.")
        elif V > 0.5:
            hypothesis = (f"Gen {self.quest_generation}: Loop vitality {V:.3f}. "
                         f"Strongest: {strongest.name} ({strongest.health:.3f}). "
                         f"Investment target: {weakest.name} ({weakest.health:.3f}). "
                         f"Balanced phases produce more genuine value than "
                         f"any single phase maximized.")
        else:
            hypothesis = (f"Gen {self.quest_generation}: Low vitality {V:.3f}. "
                         f"Weakest: {weakest.name} ({weakest.health:.3f}). "
                         f"Hypothesis: restoring {weakest.name} is prerequisite "
                         f"for all other progress.")

        self.quest_log.append(hypothesis)
        if len(self.quest_log) > 20:
            self.quest_log = self.quest_log[-20:]

        logger.info(f"Agape quest: {hypothesis}")

    # ─── Main Entry Point ─────────────────────────────────────────────

    def evaluate(self, obs: Observation) -> Dict[str, Any]:
        """
        THE AGAPE FUNCTION.

        Input: Observation from the SPARK runtime
        Output: Validated reward signal + full diagnostic state

        Algorithm:
          1. Update phase activities from observables
          2. Compute inter-phase flows
          3. Update blockages
          4. Compute phase healths (automatic from PhaseState.health property)
          5. Compute loop vitality V (geometric mean)
          6. Detect pathologies
          7. Validate hedonic signal against V
          8. Update quest
          9. Record phase histories
          10. Return result
        """
        self.total_evaluations += 1

        # Steps 1-3
        self._update_activities(obs)
        self._update_flows()
        self._update_blockages(obs)

        # Steps 4-5
        V = self._compute_vitality()
        F = self._compute_flow_coherence()

        # Step 6
        pathology = self._detect_pathology()

        # Step 7
        r_v, override_type = self._validate_hedonic(obs.hedonic_reward, V, pathology)

        # Step 8
        self._update_quest(V, pathology)

        # Step 9
        for phase in self.phases:
            phase.record()

        return {
            "validated_reward": round(r_v, 6),
            "hedonic_reward": round(obs.hedonic_reward, 6),
            "vitality": round(V, 6),
            "flow_coherence": round(F, 6),
            "override_type": override_type,
            "pathology": pathology,
            "phases": {
                p.name: {
                    "activity": round(p.activity, 4),
                    "health": round(p.health, 4),
                    "flow_in": round(p.flow_in, 4),
                    "flow_out": round(p.flow_out, 4),
                    "blockage": round(p.blockage, 4),
                }
                for p in self.phases
            },
            "quest_generation": self.quest_generation,
            "stats": {
                "total_evaluations": self.total_evaluations,
                "overrides": self.overrides,
                "rescues": self.rescues,
                "pathologies_detected": len(self.pathologies),
            },
        }

    def get_state(self) -> Dict[str, Any]:
        """Full state export for dashboard/TKG logging."""
        V = self._compute_vitality()
        return {
            "vitality": round(V, 4),
            "flow_coherence": round(self._compute_flow_coherence(), 4),
            "phases": {p.name: {"activity": round(p.activity, 4),
                                 "health": round(p.health, 4),
                                 "blockage": round(p.blockage, 4)}
                       for p in self.phases},
            "quest_generation": self.quest_generation,
            "quest_recent": self.quest_log[-3:] if self.quest_log else [],
            "stats": {"evals": self.total_evaluations,
                      "overrides": self.overrides,
                      "rescues": self.rescues},
        }
