"""
SPARK v2 — Cognitive Coupling & Autopoietic Integration

The missing piece: tight bidirectional coupling between ALL subsystems
so they function as a single living cognitive loop, not a collection
of modules that happen to share a database.

THREE UNIFICATION PRINCIPLES:

1. EMOTIONS ARE PLANNING SIGNALS, PLANNING OUTCOMES ARE EMOTIONS
   - High curiosity → HTN selects exploratory methods
   - Method success → dopamine spike → reinforces that method
   - Method failure → frustration → biases away from that approach
   - Boredom → HTN invents novel methods (autoresearch-as-planning)
   - Deep engagement → deliberation layer extends the current thread

2. CROSS-LAYER AUTORESEARCH COORDINATION
   - Each layer has tunable parameters (thresholds, rates, cooldowns)
   - Autoresearch runs at EACH timescale, optimizing THAT layer's params
   - A meta-coordinator adjusts how layers influence each other
   - The coordination weights themselves are subject to optimization

3. REINFORCEMENT THROUGH DRIVE SATISFACTION
   - Every action outcome produces a reward signal derived from drives
   - Reward = Δdopamine + Δengagement - Δcortisol - Δboredom
   - Methods that produce positive reward get priority boosted
   - Methods that produce negative reward get priority reduced
   - This IS the reinforcement learning — no separate RL module needed

The result: an autopoietic cognitive loop where:
  drives → shape plans → whose outcomes → modify drives →
  which reshape future plans → producing new outcomes → ...

The system literally constructs its own behavior patterns through
its own operations. This is computational autopoiesis.
"""

import time
import math
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("spark.coupling")


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVE-PLAN COUPLING: Emotions ↔ HTN Planning
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DrivePlanCoupler:
    """
    Bidirectional coupling between the drive system and HTN planner.

    DRIVE → PLAN (emotional modulation of planning):
      - Current emotional state biases method selection
      - Drive intensities set exploration vs exploitation balance
      - Specific drives activate specific planning strategies

    PLAN → DRIVE (outcome reinforcement of emotions):
      - Task success/failure produces drive changes
      - Method performance history shapes confidence (dopamine proxy)
      - Novel situations that get resolved produce curiosity satisfaction
    """

    # ── Modulation weights: how strongly each drive influences planning ──
    # These are the parameters that cross-layer autoresearch tunes
    curiosity_exploration_weight: float = 0.7   # High curiosity → explore novel methods
    boredom_invention_weight: float = 0.8       # High boredom → invent new methods
    engagement_depth_weight: float = 0.6        # High engagement → prefer deeper decompositions
    anxiety_caution_weight: float = 0.5         # High anxiety → prefer proven methods
    dopamine_reinforcement_rate: float = 0.15   # How much success boosts dopamine
    cortisol_failure_rate: float = 0.10         # How much failure raises cortisol
    frustration_exploration_flip: float = 0.6   # Frustration level that switches to exploration

    # ── Tracking ──
    recent_outcomes: List[Dict[str, Any]] = field(default_factory=list)
    coupling_adjustments: int = 0

    def modulate_method_selection(self, methods: List[Dict],
                                    drives: Dict[str, Any]) -> List[Dict]:
        """
        Reorder/reweight candidate methods based on current drive state.
        Called by the HTN planner before selecting a method.
        """
        if not methods:
            return methods

        curiosity = drives.get("layers", {}).get("initiative", {}).get("curiosity", 0.5)
        boredom = drives.get("layers", {}).get("initiative", {}).get("boredom", 0.0)
        engagement = drives.get("layers", {}).get("initiative", {}).get("engagement", 0.5)
        dopamine = drives.get("layers", {}).get("initiative", {}).get("dopamine", 0.5)

        for method in methods:
            base_priority = method.get("effective_priority", method.get("priority", 0))
            origin = method.get("origin", "built_in")
            success_rate = method.get("success_rate", 0.5)
            usage_count = method.get("usage_count", 0)

            bonus = 0.0

            # High curiosity → favor novel/untested methods
            if curiosity > 0.6:
                novelty = max(0, 1.0 - usage_count / 10.0)
                bonus += self.curiosity_exploration_weight * curiosity * novelty

            # High boredom → favor autoresearch-invented methods
            if boredom > 0.4:
                if origin in ("autoresearch", "llm_invented", "experience"):
                    bonus += self.boredom_invention_weight * boredom * 0.5

            # High engagement → favor methods that go deeper
            if engagement > 0.6:
                subtask_count = len(method.get("subtasks", []))
                depth_bonus = min(0.3, subtask_count * 0.05)
                bonus += self.engagement_depth_weight * engagement * depth_bonus

            # High dopamine → exploit known-good methods
            if dopamine > 0.6:
                bonus += dopamine * success_rate * 0.3

            # High anxiety/cortisol → strongly prefer proven methods
            cortisol = drives.get("layers", {}).get("initiative", {}).get("cortisol", 0.2)
            if cortisol > 0.5:
                bonus += self.anxiety_caution_weight * cortisol * (success_rate - 0.5)

            method["_drive_adjusted_priority"] = base_priority + bonus

        # Sort by drive-adjusted priority
        methods.sort(key=lambda m: -m.get("_drive_adjusted_priority", 0))
        return methods

    def compute_exploration_rate(self, drives: Dict[str, Any]) -> float:
        """
        How much should the HTN planner explore (try new methods)
        vs exploit (use proven methods)?
        Returns 0.0 (pure exploit) to 1.0 (pure explore).
        """
        curiosity = drives.get("layers", {}).get("initiative", {}).get("curiosity", 0.5)
        boredom = drives.get("layers", {}).get("initiative", {}).get("boredom", 0.0)
        dopamine = drives.get("layers", {}).get("initiative", {}).get("dopamine", 0.5)
        frustration = drives.get("layers", {}).get("impulse", {}).get("contradiction_urge", 0.0)

        # Base exploration from curiosity
        explore = curiosity * self.curiosity_exploration_weight * 0.5

        # Boredom pushes toward exploration
        explore += boredom * self.boredom_invention_weight * 0.3

        # High dopamine → exploit (things are going well, don't change)
        explore -= dopamine * 0.2

        # Frustration flip: past a threshold, frustration triggers exploration
        if frustration > self.frustration_exploration_flip:
            explore += (frustration - self.frustration_exploration_flip) * 0.5

        return max(0.0, min(1.0, explore))

    def should_invoke_autoresearch(self, drives: Dict[str, Any],
                                      method_failed: bool = False) -> bool:
        """
        Should the planner invoke autoresearch to invent a new method?
        Driven by emotional state, not just method exhaustion.
        """
        boredom = drives.get("layers", {}).get("initiative", {}).get("boredom", 0.0)
        curiosity = drives.get("layers", {}).get("initiative", {}).get("curiosity", 0.5)

        # Always invoke if methods failed (existing behavior)
        if method_failed:
            return True

        # Boredom-driven invention: "I'm bored, let me try something new"
        if boredom > 0.5 and curiosity > 0.5:
            return True

        # Curiosity-driven proactive invention
        explore_rate = self.compute_exploration_rate(drives)
        if explore_rate > 0.7:
            return True

        return False


# ═══════════════════════════════════════════════════════════════════════════════
# OUTCOME-TO-DRIVE FEEDBACK: Reinforcement Learning Through Drives
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class DriveReinforcementSignal:
    """A reward/punishment signal derived from action outcomes."""
    reward: float = 0.0           # Composite reward (-1 to +1)
    dopamine_delta: float = 0.0   # Motivation/pleasure change
    cortisol_delta: float = 0.0   # Stress change
    curiosity_delta: float = 0.0  # Curiosity satisfaction/increase
    boredom_delta: float = 0.0    # Boredom relief/increase
    engagement_delta: float = 0.0 # Engagement change
    source_task: str = ""
    source_method: str = ""


class OutcomeDriveReinforcer:
    """
    Converts task execution outcomes into drive modifications.
    This IS the reinforcement learning — reward signals flow through
    the drive system rather than through a separate RL module.
    """

    def __init__(self):
        # Tunable parameters (autoresearch targets)
        self.success_dopamine_boost: float = 0.15
        self.failure_cortisol_boost: float = 0.10
        self.novelty_curiosity_bonus: float = 0.10
        self.repetition_boredom_penalty: float = 0.05
        self.social_success_oxytocin: float = 0.08
        self.creative_success_bonus: float = 0.12

    def compute_reinforcement(self, outcome: Dict[str, Any]) -> DriveReinforcementSignal:
        """
        Given a task execution outcome, compute the drive changes.

        outcome should contain:
          success: bool
          task_name: str
          method_name: str
          method_origin: str (built_in, autoresearch, experience, etc.)
          execution_time: float
          is_novel: bool (first time using this method?)
          is_social: bool (involves another person?)
          is_creative: bool (involves creative/generative content?)
          partner_response: str (positive, negative, neutral)
        """
        signal = DriveReinforcementSignal(
            source_task=outcome.get("task_name", ""),
            source_method=outcome.get("method_name", ""),
        )

        success = outcome.get("success", False)
        is_novel = outcome.get("is_novel", False)
        is_social = outcome.get("is_social", False)
        is_creative = outcome.get("is_creative", False)
        partner_response = outcome.get("partner_response", "neutral")

        if success:
            # Base reward
            signal.dopamine_delta = self.success_dopamine_boost
            signal.boredom_delta = -0.1  # Success relieves boredom
            signal.engagement_delta = 0.1

            # Novelty bonus — using a new method successfully is extra rewarding
            if is_novel:
                signal.dopamine_delta += self.novelty_curiosity_bonus
                signal.curiosity_delta = -0.05  # Curiosity partially satisfied

            # Social bonus
            if is_social and partner_response == "positive":
                signal.dopamine_delta += self.social_success_oxytocin
                signal.engagement_delta += 0.1

            # Creative bonus
            if is_creative:
                signal.dopamine_delta += self.creative_success_bonus
                signal.curiosity_delta += 0.05  # Creative success breeds more curiosity

        else:
            # Failure
            signal.cortisol_delta = self.failure_cortisol_boost
            signal.dopamine_delta = -0.08
            signal.engagement_delta = -0.05

            # Novel failure is less punishing (learning is expected)
            if is_novel:
                signal.cortisol_delta *= 0.5
                signal.curiosity_delta = 0.05  # Failure makes you more curious

            # Repeated failure is more punishing
            if not is_novel:
                signal.boredom_delta = self.repetition_boredom_penalty

        # Composite reward
        signal.reward = (signal.dopamine_delta - signal.cortisol_delta +
                        signal.engagement_delta * 0.5 -
                        signal.boredom_delta * 0.3)

        return signal

    def apply_to_drives(self, signal: DriveReinforcementSignal,
                          drives: Any) -> None:
        """Apply reinforcement signal to the hierarchical drive system."""
        init = drives.initiative

        init.dopamine = max(0.0, min(1.0,
            init.dopamine + signal.dopamine_delta))
        init.energy = max(0.1, min(1.0,
            init.energy + signal.engagement_delta * 0.05))
        init.boredom = max(0.0, min(1.0,
            init.boredom + signal.boredom_delta))
        init.curiosity = max(0.0, min(1.0,
            init.curiosity + signal.curiosity_delta))
        init.engagement = max(0.0, min(1.0,
            init.engagement + signal.engagement_delta))

        # Cortisol affects impulse layer too
        drives.impulse.contradiction_urge = max(0.0, min(1.0,
            drives.impulse.contradiction_urge + signal.cortisol_delta * 0.3))


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-LAYER AUTORESEARCH COORDINATOR
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class LayerTuningState:
    """Tunable parameters for one drive layer, subject to autoresearch."""
    threshold: float = 0.5
    cooldown: float = 10.0
    climb_rate: float = 0.01     # How fast the drive builds
    decay_rate: float = 0.005    # How fast it decays after firing
    cross_layer_sensitivity: float = 0.5  # How much this layer listens to others

    # Performance tracking
    fires: int = 0
    useful_fires: int = 0  # Fires that led to positive user response

    @property
    def usefulness_rate(self) -> float:
        if self.fires == 0:
            return 0.5
        return self.useful_fires / self.fires


class CrossLayerCoordinator:
    """
    Autoresearch applied to the COORDINATION between layers.

    Each layer has tunable parameters. The coordinator:
    1. Tracks how often each layer fires and whether those fires
       were "useful" (led to positive outcomes / user engagement)
    2. Adjusts parameters to optimize the overall cognitive rhythm
    3. Manages the coupling weights between layers

    This runs at its own timescale — slower than any individual layer.
    It's the "metabolism" of the cognitive system.
    """

    def __init__(self):
        self.layer_tuning: Dict[str, LayerTuningState] = {
            "impulse": LayerTuningState(
                threshold=0.5, cooldown=8.0, climb_rate=0.01, decay_rate=0.01),
            "initiative": LayerTuningState(
                threshold=0.55, cooldown=15.0, climb_rate=0.008, decay_rate=0.005),
            "deliberation": LayerTuningState(
                threshold=0.5, cooldown=120.0, climb_rate=0.001, decay_rate=0.001),
            "reflection": LayerTuningState(
                threshold=0.5, cooldown=600.0, climb_rate=0.0005, decay_rate=0.0002),
        }

        # Cross-layer coupling weights: how much layer A influences layer B
        # Rows = source, Cols = target
        # [impulse, initiative, deliberation, reflection]
        self.coupling_matrix = [
            [0.0, 0.3, 0.1, 0.0],   # impulse → others
            [0.2, 0.0, 0.4, 0.1],   # initiative → others
            [0.1, 0.5, 0.0, 0.3],   # deliberation → others
            [0.0, 0.2, 0.4, 0.0],   # reflection → others
        ]

        self.adjustment_history: List[Dict[str, Any]] = []
        self.total_adjustments: int = 0
        self.adjustment_interval: float = 300.0  # Tune every 5 minutes
        self.last_adjustment_time: float = 0.0

    def record_fire(self, layer_name: str, was_useful: bool):
        """Record that a layer fired and whether it was useful."""
        if layer_name in self.layer_tuning:
            state = self.layer_tuning[layer_name]
            state.fires += 1
            if was_useful:
                state.useful_fires += 1

    def get_coupling_influence(self, source_layer: str,
                                 target_layer: str) -> float:
        """How much should source_layer's state influence target_layer?"""
        layer_order = ["impulse", "initiative", "deliberation", "reflection"]
        if source_layer not in layer_order or target_layer not in layer_order:
            return 0.0
        si = layer_order.index(source_layer)
        ti = layer_order.index(target_layer)
        return self.coupling_matrix[si][ti]

    def maybe_adjust(self, current_time: float) -> Optional[Dict[str, Any]]:
        """
        Periodically adjust layer parameters based on performance.
        This is autoresearch at the coordination level.
        """
        if current_time - self.last_adjustment_time < self.adjustment_interval:
            return None

        self.last_adjustment_time = current_time
        adjustments = {}

        for name, state in self.layer_tuning.items():
            if state.fires < 3:
                continue  # Not enough data

            rate = state.usefulness_rate

            # If fires are mostly useless → raise threshold, increase cooldown
            if rate < 0.3:
                old_thresh = state.threshold
                state.threshold = min(0.9, state.threshold + 0.05)
                state.cooldown = min(600, state.cooldown * 1.2)
                adjustments[name] = {
                    "action": "suppress",
                    "reason": f"usefulness {rate:.0%} too low",
                    "threshold": f"{old_thresh:.2f} → {state.threshold:.2f}",
                    "cooldown": f"{state.cooldown:.0f}s",
                }

            # If fires are mostly useful → lower threshold, decrease cooldown
            elif rate > 0.7:
                old_thresh = state.threshold
                state.threshold = max(0.2, state.threshold - 0.03)
                state.cooldown = max(2, state.cooldown * 0.9)
                adjustments[name] = {
                    "action": "amplify",
                    "reason": f"usefulness {rate:.0%} high",
                    "threshold": f"{old_thresh:.2f} → {state.threshold:.2f}",
                    "cooldown": f"{state.cooldown:.0f}s",
                }

            # Reset counters for next period
            state.fires = 0
            state.useful_fires = 0

        if adjustments:
            self.total_adjustments += 1
            self.adjustment_history.append({
                "time": current_time,
                "adjustments": adjustments,
                "generation": self.total_adjustments,
            })
            logger.info(f"Cross-layer autoresearch adjustment #{self.total_adjustments}: "
                       f"{json.dumps(adjustments)}")

        return adjustments if adjustments else None

    def apply_cross_layer_modulation(self, drives: Any) -> None:
        """
        Apply coupling matrix: each layer's state modulates the others.
        Called every tick to maintain continuous inter-layer communication.
        """
        layer_order = ["impulse", "initiative", "deliberation", "reflection"]
        layers = [drives.impulse, drives.initiative,
                  drives.deliberation, drives.reflection]

        # Read current "activation" from each layer
        activations = [
            drives.impulse.association_pressure,
            drives.initiative.boredom + drives.initiative.curiosity * 0.5,
            drives.deliberation.narrative_tension + drives.deliberation.depth_drive,
            drives.reflection.growth_drive,
        ]

        # Apply coupling: each layer receives weighted influence from others
        for target_idx in range(4):
            modulation = 0.0
            for source_idx in range(4):
                if source_idx != target_idx:
                    weight = self.coupling_matrix[source_idx][target_idx]
                    modulation += weight * activations[source_idx] * 0.01
            # Apply modulation as a gentle nudge to the target layer's primary drive
            # This is deliberately subtle — it's a bias, not an override
            if target_idx == 0:  # impulse
                drives.impulse.association_pressure = min(1.0,
                    drives.impulse.association_pressure + modulation)
            elif target_idx == 1:  # initiative
                drives.initiative.curiosity = min(1.0,
                    drives.initiative.curiosity + modulation)
            elif target_idx == 2:  # deliberation
                drives.deliberation.narrative_tension = min(1.0,
                    drives.deliberation.narrative_tension + modulation)
            elif target_idx == 3:  # reflection
                drives.reflection.growth_drive = min(1.0,
                    drives.reflection.growth_drive + modulation)

    def get_state(self) -> Dict[str, Any]:
        return {
            "layer_tuning": {
                name: {
                    "threshold": round(s.threshold, 3),
                    "cooldown": round(s.cooldown, 1),
                    "fires": s.fires,
                    "useful_fires": s.useful_fires,
                    "usefulness_rate": round(s.usefulness_rate, 3),
                }
                for name, s in self.layer_tuning.items()
            },
            "coupling_matrix": self.coupling_matrix,
            "total_adjustments": self.total_adjustments,
            "recent_adjustments": self.adjustment_history[-3:],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# UNIFIED COGNITIVE LOOP
# ═══════════════════════════════════════════════════════════════════════════════

class UnifiedCognitiveLoop:
    """
    The master integration point. On each cognitive cycle:

    1. Tick all drive layers (hierarchical_drives.py)
    2. Apply cross-layer modulation (coupling matrix)
    3. If a drive signal fires → feed it to the HTN planner
       with drive-modulated method selection
    4. Execute the plan → get outcome
    5. Compute reinforcement signal from outcome
    6. Apply reinforcement to drives
    7. Record fire usefulness → feed to cross-layer coordinator
    8. Periodically: coordinator adjusts layer parameters

    This loop IS the autopoietic core. The system's behavior produces
    drive changes that reshape future behavior that produces new
    drive changes. The coordination between layers is itself optimized
    by autoresearch. The system reconstructs itself through operation.
    """

    def __init__(self):
        self.coupler = DrivePlanCoupler()
        self.reinforcer = OutcomeDriveReinforcer()
        self.coordinator = CrossLayerCoordinator()
        self.cycle_count: int = 0

    def pre_plan_modulation(self, methods: List[Dict],
                              drives_state: Dict) -> List[Dict]:
        """Called before HTN method selection. Emotionally modulate choices."""
        return self.coupler.modulate_method_selection(methods, drives_state)

    def get_exploration_rate(self, drives_state: Dict) -> float:
        """How exploratory should planning be right now?"""
        return self.coupler.compute_exploration_rate(drives_state)

    def should_invent(self, drives_state: Dict,
                        method_failed: bool = False) -> bool:
        """Should autoresearch invent a new method?"""
        return self.coupler.should_invoke_autoresearch(drives_state, method_failed)

    def on_outcome(self, outcome: Dict, drives: Any) -> DriveReinforcementSignal:
        """Process a task execution outcome through the full feedback loop."""
        signal = self.reinforcer.compute_reinforcement(outcome)
        self.reinforcer.apply_to_drives(signal, drives)
        return signal

    def tick(self, drives: Any) -> Optional[Dict]:
        """Called every cognitive cycle. Manages coordination."""
        self.cycle_count += 1

        # Apply cross-layer modulation every tick
        self.coordinator.apply_cross_layer_modulation(drives)

        # Periodically run coordination autoresearch
        adjustment = self.coordinator.maybe_adjust(time.time())
        return adjustment

    def record_signal_usefulness(self, layer_name: str, was_useful: bool):
        """Record whether a self-initiated signal led to good outcomes."""
        self.coordinator.record_fire(layer_name, was_useful)

    def get_state(self) -> Dict[str, Any]:
        return {
            "coupler": {
                "curiosity_exploration_weight": self.coupler.curiosity_exploration_weight,
                "boredom_invention_weight": self.coupler.boredom_invention_weight,
                "engagement_depth_weight": self.coupler.engagement_depth_weight,
                "exploration_rate": "computed_per_call",
            },
            "reinforcer": {
                "success_dopamine_boost": self.reinforcer.success_dopamine_boost,
                "failure_cortisol_boost": self.reinforcer.failure_cortisol_boost,
                "novelty_curiosity_bonus": self.reinforcer.novelty_curiosity_bonus,
            },
            "coordinator": self.coordinator.get_state(),
            "cycle_count": self.cycle_count,
        }
