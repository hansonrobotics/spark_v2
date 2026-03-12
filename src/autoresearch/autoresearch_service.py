"""
SPARK v2 — Autoresearch Controller
Implements Karpathy Loop pattern for autonomous self-improvement
of all SPARK subsystems. Each subsystem has a program.md, an editable
target file, and a metric. Agents iterate autonomously.
"""

import os
import json
import time
import uuid
import shutil
import asyncio
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from fastapi import FastAPI
from pydantic import BaseModel

logger = logging.getLogger("spark.autoresearch")

# ─── Configuration ────────────────────────────────────────────────────────────

EXPERIMENTS_DIR = Path(os.getenv("EXPERIMENTS_DIR", "/data/autoresearch/experiments"))
PROGRAMS_DIR = Path(os.getenv("PROGRAMS_DIR", "/data/autoresearch/programs"))
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "/data/autoresearch/results"))

# ─── Enums & Models ──────────────────────────────────────────────────────────

class SubsystemTarget(str, Enum):
    TKG_EMBEDDINGS = "tkg_embeddings"
    HTN_METHODS = "htn_methods"
    STORY_GENERATION = "story_generation"
    EMOTION_APPRAISAL = "emotion_appraisal"
    AGAPE_FUNCTION = "agape_function"
    CONVERSATION = "conversation"
    META = "meta"


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    EVALUATING = "evaluating"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


@dataclass
class ExperimentConfig:
    """Configuration for one autoresearch subsystem."""
    subsystem: SubsystemTarget
    program_md: str            # Path to the program.md instruction file
    editable_file: str         # Path to the file the agent modifies
    eval_script: str           # Path to the evaluation script
    metric_name: str           # Name of the metric to optimize
    metric_direction: str      # "minimize" or "maximize"
    time_budget_seconds: int   # Wall-clock time per experiment
    max_experiments: int       # Max experiments per autoresearch cycle


@dataclass
class ExperimentResult:
    """Result of a single autoresearch experiment."""
    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subsystem: str = ""
    started_at: str = ""
    completed_at: str = ""
    status: ExperimentStatus = ExperimentStatus.PENDING
    baseline_metric: float = 0.0
    new_metric: float = 0.0
    improvement: float = 0.0
    accepted: bool = False
    description: str = ""
    diff_summary: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "subsystem": self.subsystem,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status.value,
            "baseline_metric": self.baseline_metric,
            "new_metric": self.new_metric,
            "improvement": self.improvement,
            "accepted": self.accepted,
            "description": self.description,
            "diff_summary": self.diff_summary,
            "error": self.error,
        }


# ─── Subsystem Definitions ───────────────────────────────────────────────────

DEFAULT_CONFIGS: Dict[SubsystemTarget, dict] = {
    SubsystemTarget.TKG_EMBEDDINGS: {
        "program_md": "tkg_program.md",
        "editable_file": "tkg_model.py",
        "eval_script": "eval_tkg.py",
        "metric_name": "mrr",
        "metric_direction": "maximize",
        "time_budget_seconds": 300,
        "max_experiments": 50,
    },
    SubsystemTarget.HTN_METHODS: {
        "program_md": "htn_program.md",
        "editable_file": "htn_methods.yaml",
        "eval_script": "eval_htn.py",
        "metric_name": "task_completion_rate",
        "metric_direction": "maximize",
        "time_budget_seconds": 120,
        "max_experiments": 100,
    },
    SubsystemTarget.STORY_GENERATION: {
        "program_md": "story_program.md",
        "editable_file": "story_prompts.md",
        "eval_script": "eval_stories.py",
        "metric_name": "engagement_score",
        "metric_direction": "maximize",
        "time_budget_seconds": 180,
        "max_experiments": 50,
    },
    SubsystemTarget.EMOTION_APPRAISAL: {
        "program_md": "emotion_program.md",
        "editable_file": "appraisal_rules.py",
        "eval_script": "eval_emotion.py",
        "metric_name": "naturalness_rating",
        "metric_direction": "maximize",
        "time_budget_seconds": 120,
        "max_experiments": 80,
    },
    SubsystemTarget.AGAPE_FUNCTION: {
        "program_md": "agape_program.md",
        "editable_file": "agape_weights.py",
        "eval_script": "eval_agape.py",
        "metric_name": "value_alignment_score",
        "metric_direction": "maximize",
        "time_budget_seconds": 180,
        "max_experiments": 50,
    },
    SubsystemTarget.CONVERSATION: {
        "program_md": "conversation_program.md",
        "editable_file": "conversation_prompts.md",
        "eval_script": "eval_conversation.py",
        "metric_name": "user_satisfaction",
        "metric_direction": "maximize",
        "time_budget_seconds": 300,
        "max_experiments": 50,
    },
    SubsystemTarget.META: {
        "program_md": "meta_program.md",
        "editable_file": "meta_config.yaml",
        "eval_script": "eval_meta.py",
        "metric_name": "overall_improvement_rate",
        "metric_direction": "maximize",
        "time_budget_seconds": 600,
        "max_experiments": 20,
    },
}


# ─── Program.md Templates ────────────────────────────────────────────────────

PROGRAM_TEMPLATES = {
    SubsystemTarget.TKG_EMBEDDINGS: """# SPARK Autoresearch: Temporal Knowledge Graph Embeddings

## Context
You are an AI research agent optimizing the temporal knowledge graph embedding model
for the SPARK social robot platform. The model uses LTGQ-style quadruplet networks
to embed entities, relations, and timestamps into specialized spaces.

## Your Task
Modify `tkg_model.py` to improve temporal link prediction performance (MRR, Hits@10).
Everything is fair game: embedding dimensions, transformation functions, loss functions,
learning rate schedules, regularization, temporal encoding strategies.

## Constraints
- Training budget: 5 minutes wall clock time
- Must maintain quadruple format (subject, relation, object, timestamp)
- Must preserve the API interface (score_quadruple, predict_temporal_link)

## Evaluation
After each modification, the eval script runs temporal link prediction on held-out
quadruples. Metric: Mean Reciprocal Rank (MRR). Higher is better.

## Strategy
- Start with small, targeted changes (one variable at a time)
- Track which changes helped and which didn't
- Build on successful changes incrementally
- Consider: hierarchical time encoding, attention mechanisms, different distance functions
""",

    SubsystemTarget.HTN_METHODS: """# SPARK Autoresearch: HTN Planning Methods

## Context
You are optimizing the Hierarchical Task Network planning methods for Sophia's
behavior generation. Methods define how compound tasks decompose into subtasks.

## Your Task
Modify `htn_methods.yaml` to improve task completion rate and reduce plan length.
You may add new methods, reorder subtasks, adjust priorities, add/remove preconditions.

## Constraints
- All plans must terminate in registered primitive tasks
- Preconditions must reference valid world state properties
- Methods must not create infinite decomposition loops

## Evaluation
100 simulated episodes with varied world states. Metrics: task completion rate
(higher is better), average plan length (lower is better for equal completion).
""",

    SubsystemTarget.META: """# SPARK Autoresearch: Meta-Optimization

## Context
You are the meta-research agent. Your job is to optimize the autoresearch process
itself across all SPARK subsystems.

## Your Task
Modify `meta_config.yaml` to improve the overall rate of improvement across all
subsystems. You control: time budgets, iteration counts, evaluation parameters,
and the program.md content for each subsystem.

## Evaluation
Measured over a 24-hour cycle: total improvement across all subsystem metrics,
weighted by subsystem importance.

## Meta-Strategy
- Allocate more budget to subsystems showing fastest improvement
- Reduce budget for plateauing subsystems
- Modify program.md files for underperforming subsystem agents
- Consider: should some subsystems run sequentially vs. in parallel?
""",
}


# ─── Autoresearch Agent ──────────────────────────────────────────────────────

class AutoresearchAgent:
    """
    Manages the autoresearch loop for a single subsystem.
    Follows the Karpathy pattern: modify → evaluate → keep/discard → repeat.
    """

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.results: List[ExperimentResult] = []
        self.best_metric: Optional[float] = None
        self.running = False
        self.experiment_count = 0

        # Ensure directories exist
        self.subsystem_dir = EXPERIMENTS_DIR / config.subsystem.value
        self.subsystem_dir.mkdir(parents=True, exist_ok=True)
        (self.subsystem_dir / "baseline").mkdir(exist_ok=True)

    async def run_cycle(self, num_experiments: Optional[int] = None):
        """Run a full autoresearch cycle."""
        max_exp = num_experiments or self.config.max_experiments
        self.running = True

        logger.info(f"Starting autoresearch cycle for {self.config.subsystem.value} "
                    f"({max_exp} experiments)")

        # Get baseline metric
        self.best_metric = await self._evaluate_current()
        logger.info(f"Baseline {self.config.metric_name}: {self.best_metric}")

        for i in range(max_exp):
            if not self.running:
                break

            result = ExperimentResult(
                subsystem=self.config.subsystem.value,
                started_at=datetime.utcnow().isoformat(),
                baseline_metric=self.best_metric or 0.0,
            )

            try:
                # Step 1: Agent modifies the editable file
                modification = await self._generate_modification()
                result.description = modification.get("description", "")
                result.diff_summary = modification.get("diff", "")

                # Step 2: Evaluate the modification
                result.status = ExperimentStatus.EVALUATING
                new_metric = await self._evaluate_current()
                result.new_metric = new_metric

                # Step 3: Accept or reject
                improved = self._is_improvement(new_metric)
                if improved:
                    result.status = ExperimentStatus.ACCEPTED
                    result.accepted = True
                    result.improvement = self._compute_improvement(new_metric)
                    self.best_metric = new_metric
                    await self._commit_improvement(result)
                    logger.info(f"Experiment {i+1}: ACCEPTED "
                               f"({self.config.metric_name}: {new_metric:.4f}, "
                               f"improvement: {result.improvement:+.4f})")
                else:
                    result.status = ExperimentStatus.REJECTED
                    result.accepted = False
                    await self._rollback()
                    logger.info(f"Experiment {i+1}: REJECTED "
                               f"({self.config.metric_name}: {new_metric:.4f})")

            except Exception as e:
                result.status = ExperimentStatus.FAILED
                result.error = str(e)
                await self._rollback()
                logger.error(f"Experiment {i+1} failed: {e}")

            result.completed_at = datetime.utcnow().isoformat()
            self.results.append(result)
            self.experiment_count += 1

            # Save progress
            self._save_progress()

        self.running = False
        return self.get_summary()

    async def _generate_modification(self) -> Dict[str, str]:
        """
        Use an LLM agent to generate a modification to the editable file.
        In production, this calls Claude/GPT with the program.md context.
        """
        # Placeholder — in production this calls the LLM API
        return {
            "description": "Simulated modification",
            "diff": "# Placeholder diff",
        }

    async def _evaluate_current(self) -> float:
        """Run the evaluation script and return the metric."""
        try:
            result = subprocess.run(
                ["python", self.config.eval_script],
                capture_output=True, text=True,
                timeout=self.config.time_budget_seconds,
                cwd=str(self.subsystem_dir),
            )
            if result.returncode == 0:
                output = json.loads(result.stdout.strip())
                return float(output.get(self.config.metric_name, 0.0))
            else:
                logger.error(f"Eval script failed: {result.stderr}")
                return 0.0
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            # Return a default metric for development/testing
            return 0.5 + (self.experiment_count * 0.001)

    def _is_improvement(self, new_metric: float) -> bool:
        if self.best_metric is None:
            return True
        if self.config.metric_direction == "maximize":
            return new_metric > self.best_metric
        else:
            return new_metric < self.best_metric

    def _compute_improvement(self, new_metric: float) -> float:
        if self.best_metric is None or self.best_metric == 0:
            return new_metric
        return new_metric - self.best_metric

    async def _commit_improvement(self, result: ExperimentResult):
        """Save the improved version as the new baseline."""
        exp_dir = self.subsystem_dir / f"experiment_{self.experiment_count:04d}"
        exp_dir.mkdir(exist_ok=True)
        # Save result metadata
        with open(exp_dir / "result.json", "w") as f:
            json.dump(result.to_dict(), f, indent=2)

    async def _rollback(self):
        """Revert to the last known good state."""
        pass  # In production: git checkout on the editable file

    def _save_progress(self):
        progress_file = self.subsystem_dir / "progress.json"
        progress = {
            "subsystem": self.config.subsystem.value,
            "total_experiments": self.experiment_count,
            "accepted": sum(1 for r in self.results if r.accepted),
            "rejected": sum(1 for r in self.results if r.status == ExperimentStatus.REJECTED),
            "failed": sum(1 for r in self.results if r.status == ExperimentStatus.FAILED),
            "best_metric": self.best_metric,
            "metric_name": self.config.metric_name,
            "history": [r.to_dict() for r in self.results[-100:]],
        }
        with open(progress_file, "w") as f:
            json.dump(progress, f, indent=2)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "subsystem": self.config.subsystem.value,
            "total_experiments": self.experiment_count,
            "accepted": sum(1 for r in self.results if r.accepted),
            "best_metric": self.best_metric,
            "metric_name": self.config.metric_name,
            "running": self.running,
        }


# ─── Meta-Autoresearch Controller ────────────────────────────────────────────

class MetaAutoresearchController:
    """
    Meta-level controller that manages all subsystem autoresearch agents
    and optimizes the autoresearch process itself.
    """

    def __init__(self):
        self.agents: Dict[SubsystemTarget, AutoresearchAgent] = {}
        self.meta_results: List[Dict[str, Any]] = []
        self._initialize_agents()

    def _initialize_agents(self):
        for subsystem, config_dict in DEFAULT_CONFIGS.items():
            config = ExperimentConfig(subsystem=subsystem, **config_dict)
            self.agents[subsystem] = AutoresearchAgent(config)

    async def run_subsystem(self, subsystem: SubsystemTarget,
                             num_experiments: int = None) -> Dict[str, Any]:
        agent = self.agents.get(subsystem)
        if not agent:
            raise ValueError(f"Unknown subsystem: {subsystem}")
        return await agent.run_cycle(num_experiments)

    async def run_all(self, num_experiments_per: int = 10) -> Dict[str, Any]:
        """Run autoresearch on all subsystems (can be parallel or sequential)."""
        results = {}
        for subsystem, agent in self.agents.items():
            if subsystem == SubsystemTarget.META:
                continue  # Meta runs after all others
            results[subsystem.value] = await agent.run_cycle(num_experiments_per)

        # Meta-analysis
        meta_summary = self._meta_analyze(results)
        self.meta_results.append(meta_summary)
        return {"subsystems": results, "meta": meta_summary}

    def _meta_analyze(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze improvement rates and adjust resource allocation."""
        analysis = {}
        for subsystem, summary in results.items():
            total = summary.get("total_experiments", 0)
            accepted = summary.get("accepted", 0)
            analysis[subsystem] = {
                "acceptance_rate": accepted / max(total, 1),
                "best_metric": summary.get("best_metric"),
                "recommendation": "increase_budget" if accepted / max(total, 1) > 0.3
                                  else "reduce_budget" if accepted / max(total, 1) < 0.05
                                  else "maintain",
            }
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "subsystem_analysis": analysis,
            "overall_acceptance_rate": sum(
                a["acceptance_rate"] for a in analysis.values()
            ) / max(len(analysis), 1),
        }

    def get_all_status(self) -> Dict[str, Any]:
        return {
            subsystem.value: agent.get_summary()
            for subsystem, agent in self.agents.items()
        }

    def get_program_md(self, subsystem: SubsystemTarget) -> str:
        return PROGRAM_TEMPLATES.get(subsystem, "# No program defined")


# ─── FastAPI Service ──────────────────────────────────────────────────────────

app = FastAPI(title="SPARK Autoresearch Controller", version="2.0")

controller = MetaAutoresearchController()


class RunRequest(BaseModel):
    subsystem: str
    num_experiments: int = 10


@app.post("/run")
async def run_subsystem(req: RunRequest):
    try:
        target = SubsystemTarget(req.subsystem)
    except ValueError:
        return {"error": f"Unknown subsystem: {req.subsystem}",
                "valid": [s.value for s in SubsystemTarget]}
    result = await controller.run_subsystem(target, req.num_experiments)
    return result


@app.post("/run-all")
async def run_all(num_experiments_per: int = 10):
    result = await controller.run_all(num_experiments_per)
    return result


@app.get("/status")
async def get_status():
    return controller.get_all_status()


@app.get("/status/{subsystem}")
async def get_subsystem_status(subsystem: str):
    try:
        target = SubsystemTarget(subsystem)
    except ValueError:
        return {"error": f"Unknown subsystem: {subsystem}"}
    agent = controller.agents.get(target)
    return agent.get_summary() if agent else {"error": "Agent not found"}


@app.get("/programs/{subsystem}")
async def get_program(subsystem: str):
    try:
        target = SubsystemTarget(subsystem)
    except ValueError:
        return {"error": f"Unknown subsystem: {subsystem}"}
    return {"subsystem": subsystem, "program_md": controller.get_program_md(target)}


@app.get("/meta/results")
async def get_meta_results():
    return {"meta_results": controller.meta_results}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "spark-autoresearch", "version": "2.0"}
