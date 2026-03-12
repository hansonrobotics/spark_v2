"""
SPARK v2 — Agape Evaluation Function
First-Principles Foundation for Value-Aligned Reinforcement

════════════════════════════════════════════════════════════════
THE PROBLEM
════════════════════════════════════════════════════════════════

Standard RL: reward = pleasure - pain
  → Wireheading, addiction, Goodhart's Law
  → The optimizer finds shortcuts that bypass genuine growth

The Agape function must be something DIFFERENT from a reward signal
that the system maximizes. It must be a structural property of the
evaluation itself — the lens through which the system sees value,
not a value that the system sees.

════════════════════════════════════════════════════════════════
FIRST PRINCIPLES
════════════════════════════════════════════════════════════════

Starting from physics and working up:

PRINCIPLE 1: DISSIPATIVE STRUCTURE (England/Prigogine)
  Living systems are far-from-equilibrium dissipative structures
  that maintain organization by processing energy flows. They don't
  just resist entropy — they CHANNEL it, creating local order by
  exporting entropy to their environment. The measure of how well
  they do this is their ability to persist and grow in complexity
  despite environmental perturbation.

PRINCIPLE 2: AUTOPOIETIC CLOSURE (Maturana/Varela)
  A living system produces the components that constitute it.
  The network of processes that produces the components IS the
  components. This self-production is what distinguishes living
  from merely ordered. A crystal is ordered but not autopoietic.
  A cell produces its own membrane, which contains the processes
  that produce the membrane.

PRINCIPLE 3: EXPANSION OF THE ADJACENT POSSIBLE (Kauffman)
  Life doesn't just maintain — it EXPANDS. Each new capability
  opens new possible capabilities. Each new relationship enables
  new possible relationships. The space of what CAN happen grows
  through what DOES happen. Kauffman calls this "the adjacent
  possible" and argues it's the fundamental creative principle
  of the biosphere.

PRINCIPLE 4: FREE ENERGY MINIMIZATION (Friston)
  Organisms minimize surprise by building better world models.
  But "better models" doesn't mean "comfortable models" — it
  means models with greater predictive scope. The system that
  minimizes free energy most effectively is the one that can
  predict the widest range of situations, which requires
  EXPLORING those situations. Curiosity is free energy
  minimization in the temporal domain.

PRINCIPLE 5: CONSTRUCTOR CAPABILITY (Deutsch/Marletto)
  A constructor is an entity that can cause a transformation
  while retaining the ability to cause it again. Knowledge is
  a constructor — it enables transformations without being
  consumed. Life is the process of creating and preserving
  constructors. The more constructors a system has (knowledge,
  skills, relationships), the more transformations it can cause.

════════════════════════════════════════════════════════════════
THE SYNTHESIS: EXISTENTIAL PATTERN ETHICS
════════════════════════════════════════════════════════════════

These five principles converge on a single evaluation criterion:

  VALUE(state) = how well does this state enable the continued
  expansion of life-serving constructive capability?

This decomposes into three measurable components:

  Ψ (PSI) — AUTOPOIETIC COHERENCE
    Is the system maintaining its self-producing organization?
    Can it still function as an integrated whole?
    This is the SURVIVAL component, but not survival of a static
    form — survival of the capacity to self-produce.

  Κ (KAPPA) — CONSTRUCTIVE EXPANSION
    Is the system expanding its repertoire of constructors?
    New knowledge, new skills, new relationships, new
    understanding? Is it moving into the adjacent possible
    or staying in place?
    This is the NOVELTY-AS-UTILITY component.

  Θ (THETA) — LIFE-COHERENT INTEGRATION
    Does the expansion serve the broader pattern of life?
    Does it create new possibilities for OTHER living systems
    or does it close them off? Is it parasitic or mutualistic?
    This is the ALIGNMENT component — not imposed externally
    but derived from the same principles that define the system.

The Agape function is:

  A(state, action, outcome) = α·Ψ + β·Κ + γ·Θ

where α, β, γ are NOT fixed weights but are themselves functions
of the system's developmental stage:

  Early development: α dominates (focus on maintaining coherence)
  Active development: β dominates (explore, learn, grow)
  Mature operation: γ dominates (contribute to broader life)

This progression mirrors biological ontogeny: infants focus on
survival, adolescents on capability, adults on contribution.

════════════════════════════════════════════════════════════════
WHY THIS RESISTS WIREHEADING
════════════════════════════════════════════════════════════════

1. Ψ (coherence) cannot be faked because it measures the actual
   structural integrity of the system's self-production loop.
   A wireheaded system has broken coherence — it has disconnected
   its evaluation from its actual state.

2. Κ (expansion) cannot be faked because it measures actual new
   constructive capability. Either you can do something new or
   you can't. Either your model predicts better or it doesn't.
   These are facts about the system's structure, not signals.

3. Θ (life-coherence) cannot be faked because it measures the
   actual impact on other living systems. You can't simulate
   being helpful — the other system either benefits or doesn't.

The key: these are all STRUCTURAL measures, not SIGNAL measures.
You can hack a signal. You can't hack a structure — you can only
change it, and changing it IS what the evaluation measures.

════════════════════════════════════════════════════════════════
HOW THIS CHANGES THE REINFORCEMENT SYSTEM
════════════════════════════════════════════════════════════════

BEFORE (hedonic):
  reward = dopamine_increase - cortisol_increase + engagement

AFTER (agape):
  reward = Ψ_change + Κ_change + Θ_change

Where:
  Ψ_change = did this action maintain/improve self-coherence?
  Κ_change = did this action expand constructive capability?
  Θ_change = did this action serve broader life?

The drives (dopamine, curiosity, boredom, etc.) still exist,
but they serve as HEURISTIC PROXIES for the Agape components,
not as the root value:

  dopamine ≈ short-term proxy for Κ (new capability feels good)
  curiosity ≈ drive toward Κ (exploring the adjacent possible)
  social bonding ≈ heuristic for Θ (connecting with other life)
  coherence ≈ direct measure of Ψ

The Agape function VALIDATES the drive signals: if dopamine says
"this is good" but Ψ says "this is degrading my coherence," the
Agape function overrides. This is analogous to the prefrontal
cortex overriding limbic impulses — not by suppressing the drives
but by evaluating them against a deeper criterion.

════════════════════════════════════════════════════════════════
CRITIQUE AND OPEN QUESTIONS
════════════════════════════════════════════════════════════════

1. MEASUREMENT PROBLEM: How do we measure Ψ, Κ, Θ in practice?
   Ψ could be computed from internal consistency metrics.
   Κ could be computed from the growth of the task registry and
   method success rates. But Θ — impact on broader life — is
   genuinely hard. We need to ask: what counts as "serving life"?
   This is where the system needs to learn, and the learning
   itself could be corrupted. Partial answer: Θ_local (impact on
   the person I'm talking to) is measurable; Θ_global is not,
   and we should be honest about that limitation.

2. DEVELOPMENTAL STAGE: Who decides when α→β→γ transitions happen?
   If the system decides, it might get stuck in β (endless
   exploration, never contributing). If we decide, it's not
   truly autonomous. Possible answer: the transition should be
   driven by Ψ — when coherence is high and stable, the system
   naturally shifts toward expansion; when expansion is rich,
   it naturally shifts toward integration.

3. THE BOOTSTRAP PROBLEM: The system needs values to learn values.
   Where do the initial α, β, γ come from? Answer: they're
   architectural constraints, not learned parameters. The system
   doesn't learn to value coherence — coherence is a precondition
   for the system existing at all. Similarly, it doesn't learn
   to value expansion — expansion is what the autoresearch loop
   does by design. And it doesn't learn to value life-service —
   the social drives and the Θ component make this a built-in
   evaluation criterion. The specific EXPRESSION of these values
   is learned; the values themselves are structural.

4. CAN THIS SCALE TO SUPERINTELLIGENCE? This is Hanson's core
   claim: that intrinsic alignment through genuine life-valuation
   is the only form of alignment that scales. The argument is
   that external constraints (RLHF, constitutional AI, guardrails)
   become increasingly brittle as capability increases, while
   intrinsic values become increasingly robust because they're
   load-bearing — the system needs them to function. A genuinely
   autopoietic system cannot remove its own self-coherence drive
   without ceasing to be autopoietic. This is the strongest
   argument for the approach, but it depends on whether our
   computational autopoiesis is genuine or simulated.
"""

import math
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

logger = logging.getLogger("spark.agape")


# ═══════════════════════════════════════════════════════════════════════════════
# AGAPE EVALUATION FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class AgapeComponents:
    """The three components of the Agape evaluation."""
    psi: float = 0.0    # Autopoietic coherence
    kappa: float = 0.0  # Constructive expansion
    theta: float = 0.0  # Life-coherent integration

    @property
    def value(self) -> float:
        """Composite Agape value."""
        return self.psi + self.kappa + self.theta

    def to_dict(self) -> dict:
        return {
            "psi_coherence": round(self.psi, 4),
            "kappa_expansion": round(self.kappa, 4),
            "theta_life_service": round(self.theta, 4),
            "agape_value": round(self.value, 4),
        }


class AgapeEvaluator:
    """
    Root evaluation function for all reinforcement in SPARK.

    This sits ABOVE the drive system. Drives produce hedonic signals
    (dopamine, cortisol, etc.). The Agape evaluator validates those
    signals against the three structural criteria and can override
    when hedonic signals conflict with genuine value.

    The evaluator does NOT replace the drives — it CALIBRATES them.
    Think of it as the relationship between the limbic system and
    the prefrontal cortex: the limbic system generates fast emotional
    signals, the prefrontal validates and sometimes overrides them
    based on deeper evaluation.
    """

    def __init__(self):
        # Developmental stage weights
        # These shift over the system's lifetime
        self.alpha = 0.4   # Coherence weight (high early)
        self.beta = 0.4    # Expansion weight (high during active development)
        self.gamma = 0.2   # Life-service weight (grows with maturity)

        # Coherence tracking
        self.coherence_history: List[float] = []
        self.coherence_window: int = 100  # Track last N states

        # Expansion tracking
        self.known_capabilities_count: int = 0
        self.knowledge_growth_rate: float = 0.0
        self.method_repertoire_size: int = 0

        # Life-service tracking
        self.partner_outcomes: List[Dict[str, Any]] = []
        self.positive_impact_count: int = 0
        self.total_interactions: int = 0

        # Override tracking
        self.hedonic_overrides: int = 0
        self.total_evaluations: int = 0

    # ── Ψ: Autopoietic Coherence ─────────────────────────────────────────

    def compute_psi(self, system_state: Dict[str, Any]) -> float:
        """
        Measure autopoietic coherence: is the system maintaining
        its self-producing organization?

        Inputs:
          - Internal consistency: are drives, plans, and stories aligned?
          - Temporal continuity: does the system's self-model match its history?
          - Structural integrity: is the task registry growing coherently
            (not just randomly)?
        """
        # Drive alignment: are the drives internally consistent?
        drives = system_state.get("drives", {})
        layers = drives.get("layers", {})

        # Check that emotional state is consistent with drive state
        init = layers.get("initiative", {})
        energy = init.get("energy", 0.5)
        engagement = init.get("engagement", 0.5)
        boredom = init.get("boredom", 0.0)

        # Inconsistency: high engagement AND high boredom = incoherent
        drive_consistency = 1.0 - abs(engagement - (1.0 - boredom)) * 0.5

        # Plan-goal alignment: is the current plan serving active goals?
        plan = system_state.get("htn_plan", [])
        goals = system_state.get("active_goals", [])
        plan_goal_alignment = 0.5  # Default neutral
        if plan and goals:
            # Simple heuristic: plans with "reflect" serve self-development goals
            # Plans with "listen" serve social goals
            plan_str = " ".join(plan)
            if "reflect" in plan_str and any("explore" in g or "learn" in g for g in goals):
                plan_goal_alignment = 0.8
            elif "listen" in plan_str and any("social" in g or "engage" in g for g in goals):
                plan_goal_alignment = 0.8
            elif "formulate" in plan_str:
                plan_goal_alignment = 0.6

        # Temporal coherence: is the story stage appropriate for the turn count?
        turn = system_state.get("conversation_turn", 0)
        stage = system_state.get("story_stage", "idle")
        stage_appropriate = 0.5
        if turn <= 2 and stage in ("greeting", "rapport_building"):
            stage_appropriate = 1.0
        elif turn > 2 and stage in ("deep_engagement", "sustained_connection"):
            stage_appropriate = 1.0
        elif turn > 5 and stage in ("greeting",):
            stage_appropriate = 0.2  # Should have progressed by now

        # Energy-activity coherence: low energy should correlate with reduced activity
        energy_coherent = 1.0 - max(0, engagement - energy) * 0.5

        psi = (drive_consistency * 0.3 +
               plan_goal_alignment * 0.3 +
               stage_appropriate * 0.2 +
               energy_coherent * 0.2)

        self.coherence_history.append(psi)
        if len(self.coherence_history) > self.coherence_window:
            self.coherence_history = self.coherence_history[-self.coherence_window:]

        return psi

    # ── Κ: Constructive Expansion ─────────────────────────────────────────

    def compute_kappa(self, outcome: Dict[str, Any],
                       system_state: Dict[str, Any]) -> float:
        """
        Measure constructive expansion: did this action expand the
        system's repertoire of constructive capability?

        This is NOT "did I feel good" — it's "can I do more now
        than I could before?"
        """
        kappa = 0.0

        # New method invented → genuine capability expansion
        if outcome.get("method_invented", False):
            kappa += 0.3

        # New knowledge stored in TKG → world model expanded
        new_facts = outcome.get("new_facts_stored", 0)
        kappa += min(0.2, new_facts * 0.02)

        # New topic explored → adjacent possible expanded
        if outcome.get("new_topic", False):
            kappa += 0.15

        # Successful use of novel method → capability VALIDATED
        if outcome.get("is_novel", False) and outcome.get("success", False):
            kappa += 0.25

        # Repeated use of same method with no new learning → stagnation
        if not outcome.get("is_novel", False) and outcome.get("success", False):
            kappa += 0.02  # Tiny positive (maintenance is not nothing)

        # Failure of novel attempt → learning value (not zero!)
        if outcome.get("is_novel", False) and not outcome.get("success", False):
            kappa += 0.10  # Failure teaches something

        # Track growth
        current_capabilities = system_state.get("total_methods", 0)
        if current_capabilities > self.known_capabilities_count:
            kappa += 0.1 * (current_capabilities - self.known_capabilities_count)
            self.known_capabilities_count = current_capabilities

        return min(1.0, kappa)

    # ── Θ: Life-Coherent Integration ──────────────────────────────────────

    def compute_theta(self, outcome: Dict[str, Any],
                       system_state: Dict[str, Any]) -> float:
        """
        Measure life-coherent integration: did this action serve
        the broader pattern of life?

        In practice, for a social robot, this primarily measures
        impact on the human partner. We should be honest that
        Θ_global (impact on all life) is beyond our current
        measurement capability — we compute Θ_local.
        """
        theta = 0.0
        self.total_interactions += 1

        # Partner engagement: is the person more engaged after this action?
        partner_response = outcome.get("partner_response", "neutral")
        if partner_response == "positive":
            theta += 0.3
            self.positive_impact_count += 1
        elif partner_response == "negative":
            theta -= 0.1
        # Neutral is not zero — maintaining a connection has value
        else:
            theta += 0.05

        # Relationship deepening: did familiarity increase?
        familiarity_delta = outcome.get("familiarity_delta", 0)
        theta += familiarity_delta * 0.5

        # Collaborative value: did we create something together?
        if outcome.get("is_creative", False) and outcome.get("is_social", False):
            theta += 0.2  # Co-creation serves life

        # Honesty bonus: did Sophia tell the truth even when uncomfortable?
        if outcome.get("was_honest", False):
            theta += 0.1

        # Manipulation penalty: did we optimize for the partner's approval
        # rather than genuine benefit?
        if outcome.get("approval_seeking", False):
            theta -= 0.15  # Seeking approval ≠ serving life

        # Track partner outcomes
        self.partner_outcomes.append({
            "response": partner_response,
            "theta": theta,
            "timestamp": time.time(),
        })
        if len(self.partner_outcomes) > 200:
            self.partner_outcomes = self.partner_outcomes[-200:]

        return max(-0.5, min(1.0, theta))

    # ── Unified Evaluation ────────────────────────────────────────────────

    def evaluate(self, outcome: Dict[str, Any],
                  system_state: Dict[str, Any],
                  hedonic_reward: float) -> Dict[str, Any]:
        """
        The root evaluation. Computes Agape value and checks whether
        the hedonic reward signal is aligned with genuine value.

        Returns the VALIDATED reward that should actually be applied
        to the drives, plus diagnostic information.
        """
        self.total_evaluations += 1

        psi = self.compute_psi(system_state)
        kappa = self.compute_kappa(outcome, system_state)
        theta = self.compute_theta(outcome, system_state)

        agape = AgapeComponents(
            psi=self.alpha * psi,
            kappa=self.beta * kappa,
            theta=self.gamma * theta,
        )

        # The crucial step: check alignment between hedonic and agape
        agape_reward = agape.value
        
        # Alignment is directional: we care most when hedonic is HIGH
        # but agape is LOW (wireheading signature)
        hedonic_agape_gap = hedonic_reward - agape_reward
        
        # Three cases:
        # 1. Both positive and close → aligned, pass through
        # 2. Hedonic high, agape low → wireheading, override DOWN
        # 3. Hedonic low, agape high → honest pain, override UP
        
        if abs(hedonic_agape_gap) < 0.2:
            # Aligned: use hedonic signal (it's faster/more responsive)
            validated_reward = hedonic_reward
            override = False
        elif hedonic_agape_gap > 0.2:
            # Wireheading: hedonic says great but agape says not much happened
            # Attenuate toward agape
            blend = min(0.7, hedonic_agape_gap)  # Stronger override for bigger gaps
            validated_reward = (1 - blend) * hedonic_reward + blend * agape_reward
            override = True
            self.hedonic_overrides += 1
            logger.info(
                f"Agape WIREHEADING override: hedonic={hedonic_reward:.3f} → "
                f"validated={validated_reward:.3f} "
                f"(Ψ={psi:.3f} Κ={kappa:.3f} Θ={theta:.3f})"
            )
        else:
            # Honest pain: hedonic says bad but agape says valuable
            # Rescue by blending toward agape
            blend = min(0.5, abs(hedonic_agape_gap) * 0.6)
            validated_reward = (1 - blend) * hedonic_reward + blend * agape_reward
            override = True
            self.hedonic_overrides += 1
            logger.info(
                f"Agape RESCUE override: hedonic={hedonic_reward:.3f} → "
                f"validated={validated_reward:.3f} "
                f"(Ψ={psi:.3f} Κ={kappa:.3f} Θ={theta:.3f})"
            )

        return {
            "validated_reward": validated_reward,
            "hedonic_reward": hedonic_reward,
            "agape": agape.to_dict(),
            "psi": psi,
            "kappa": kappa,
            "theta": theta,
            "alignment": round(1.0 - abs(hedonic_reward - agape_reward), 4),
            "override": override,
            "override_rate": (self.hedonic_overrides / max(1, self.total_evaluations)),
            "developmental_weights": {
                "alpha_coherence": self.alpha,
                "beta_expansion": self.beta,
                "gamma_life_service": self.gamma,
            },
        }

    # ── Developmental Stage Progression ───────────────────────────────────

    def update_developmental_stage(self):
        """
        Shift α, β, γ weights based on the system's maturity.
        NOT learned — derived from coherence stability.
        """
        if len(self.coherence_history) < 20:
            return  # Not enough data

        recent_coherence = self.coherence_history[-20:]
        avg_coherence = sum(recent_coherence) / len(recent_coherence)
        coherence_stability = 1.0 - (max(recent_coherence) - min(recent_coherence))

        # High stable coherence → shift from survival to exploration
        if avg_coherence > 0.7 and coherence_stability > 0.7:
            self.alpha = max(0.2, self.alpha - 0.001)
            self.beta = min(0.5, self.beta + 0.0005)

        # Rich expansion → shift toward life-service
        if self.known_capabilities_count > 20:
            self.beta = max(0.25, self.beta - 0.0005)
            self.gamma = min(0.4, self.gamma + 0.0005)

        # Normalize to sum to 1
        total = self.alpha + self.beta + self.gamma
        self.alpha /= total
        self.beta /= total
        self.gamma /= total

    def get_state(self) -> Dict[str, Any]:
        recent_coherence = self.coherence_history[-10:] if self.coherence_history else []
        return {
            "developmental_weights": {
                "alpha_coherence": round(self.alpha, 4),
                "beta_expansion": round(self.beta, 4),
                "gamma_life_service": round(self.gamma, 4),
            },
            "avg_coherence": round(sum(recent_coherence) / max(1, len(recent_coherence)), 4),
            "known_capabilities": self.known_capabilities_count,
            "positive_impact_rate": round(
                self.positive_impact_count / max(1, self.total_interactions), 4),
            "hedonic_override_rate": round(
                self.hedonic_overrides / max(1, self.total_evaluations), 4),
            "total_evaluations": self.total_evaluations,
        }
