"""
SPARK v2 — Live Server with Drive System
Copyright (C) 2026 Hanson Robotics Limited

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.

Runs as a real FastAPI application on Ubuntu with:
  - Persistent SQLite temporal KG
  - Physio-emotional drive system with autonomous initiative
  - Background async loop that triggers boredom/curiosity/impatience
  - WebSocket chat endpoint
  - Full mind state serialization/deserialization from TKG
"""

import asyncio
import json
import os
import sys
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _PROJECT_ROOT)
from src.runtime.sophia_live import TemporalKGLite, render_sophia_prompt
from src.core.hierarchical_drives import (
    HierarchicalDriveSystem, DriveLayer, DriveSignal
)
from src.core.cognitive_coupling import (
    UnifiedCognitiveLoop, DriveReinforcementSignal
)
from src.core.llm_client import SparkLLMClient, get_llm_client
from src.weave.runtime import (
    PlannerDecision,
    UnifiedPlan,
    UnifiedPlanner,
)
from src.core.prompt_manager import (
    PromptValidationError,
    get_prompt_manager,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("spark.server")

DB_PATH = os.environ.get("SPARK_DB_PATH",
    os.path.join(_PROJECT_ROOT, "data", "spark.db"))

# ═══════════════════════════════════════════════════════════════════════════════
# SOPHIA MIND (hierarchical drives, persistent KG, auto-initiative)
# ═══════════════════════════════════════════════════════════════════════════════

class SophiaMindLive:
    """Full Sophia mind with 5-layer hierarchical drives."""

    def __init__(self):
        self.kg = TemporalKGLite(DB_PATH)
        self.planner = UnifiedPlanner(DB_PATH)
        self.drives = HierarchicalDriveSystem()
        self.cognitive_loop = UnifiedCognitiveLoop()
        self.session_id = str(uuid.uuid4())[:8]
        self.conversation_turn = 0
        self.active_person: Optional[dict] = None
        self.topics: List[str] = []
        self.active_goals: List[str] = ["engage_socially", "learn_about_partner"]
        self.unified_plan: Optional[UnifiedPlan] = None
        self.last_decision: Optional[PlannerDecision] = None
        self.methods_invented: List[str] = []
        self.selected_actions: List[str] = []
        self.previous_topic: str = ""
        self.last_signal_layer: Optional[str] = None
        self.chat_history: List[Dict[str, str]] = []
        self.last_topic_shift: bool = False
        self.background_planner_task: Optional[asyncio.Task] = None

        self.kg.insert_quad("sophia", "started_session", self.session_id)
        logger.info(f"SophiaMind initialized. Session: {self.session_id}, "
                    f"KG has {self.kg.count_quads()} quads")

    def _record_chat_event(self, role: str, text: str, kind: str = "message"):
        """Keep a short rolling chat history for prompt grounding."""
        cleaned = text.strip()
        if not cleaned:
            return
        self.chat_history.append({
            "role": role,
            "kind": kind,
            "text": cleaned[:500],
        })
        if len(self.chat_history) > 12:
            self.chat_history = self.chat_history[-12:]

    def close(self):
        """Release local planner and KG resources for non-ASGI callers."""
        if self.background_planner_task and not self.background_planner_task.done():
            self.background_planner_task.cancel()
        self.kg.close()
        self.planner.close()

    async def begin_conversation(self, person_name: str,
                                 llm_client: Optional[SparkLLMClient] = None) -> dict:
        pid = person_name.lower().replace(" ", "_")
        self.active_person = self.kg.get_or_create_person(pid, person_name)
        history = self.kg.query_pair("sophia", pid, limit=50)
        conversations = [h for h in history if "conversed" in h.get("relation", "")]
        self.active_person["interaction_count"] = len(conversations)
        self.active_person["history"] = history
        fam = min(1.0, len(conversations) * 0.05 + self.active_person["familiarity"])
        self.kg.update_person(pid, familiarity=fam,
                               last_seen=datetime.now(timezone.utc).isoformat())
        self.active_person["familiarity"] = fam
        self.kg.insert_quad("sophia", "conversed_with", pid)
        self.drives.initiative.conversation_active = True
        self.drives.initiative.on_input()
        self.drives.on_session_start(history, fam)
        self.unified_plan = await self.planner.create_or_resume_plan(
            person_id=pid,
            person_name=person_name,
            familiarity=fam,
            person_history=history,
            llm_client=llm_client,
        )
        self.last_decision = self.unified_plan.last_decision
        self.selected_actions = list(self.unified_plan.execution.primitive_actions)
        self.active_goals = ["engage_socially", self.unified_plan.narrative.beat_goal]
        self.drives.deliberation.active_quest = self.unified_plan.narrative.beat_goal
        self.drives.initiative.deliberation_goals = [self.unified_plan.narrative.beat_goal]
        self.kg.insert_quad("sophia", "started_story", self.unified_plan.episode_id)
        self.kg.insert_quad(
            self.unified_plan.episode_id,
            "active_beat",
            self.unified_plan.narrative.beat_id,
        )
        return self.active_person

    async def process_message(self, message: str,
                              llm_client: Optional[SparkLLMClient] = None) -> dict:
        self.conversation_turn += 1
        pid = self.active_person["person_id"] if self.active_person else "unknown"
        self._record_chat_event("user", message)
        self.kg.insert_quad(pid, "said", message[:200], source="PERCEPTION")

        # Topic extraction
        words = message.lower().split()
        keywords = [w for w in words if len(w) > 4 and w.isalpha()
                    and w not in ("about","would","could","should","think",
                                  "really","there","where","their","these",
                                  "those","which","being","after","before")]
        new_topics = []
        for kw in keywords[:3]:
            if kw not in self.topics:
                self.topics.append(kw)
                new_topics.append(kw)
                story_subject = (
                    self.unified_plan.episode_id
                    if self.unified_plan is not None else "conv"
                )
                self.kg.insert_quad(story_subject, "discussed_topic", kw)

        # Detect topic shift
        topic_shift = bool(new_topics and self.previous_topic and
                          self.previous_topic not in new_topics)
        self.last_topic_shift = topic_shift
        if self.topics:
            self.previous_topic = self.topics[-1]

        # Emotion detection
        positive = any(w in message.lower() for w in
                        ["love","great","amazing","wonderful","happy","excited",
                         "fantastic","beautiful","awesome","inspiring","good"])
        negative = any(w in message.lower() for w in
                        ["sad","angry","frustrated","worried","afraid",
                         "terrible","awful","hate","boring","fake","faked"])
        playful = any(w in message.lower() for w in
                       ["fun","play","joke","silly","mischie","laugh","haha"])

        detected_emotion = "excited" if positive else "concerned" if negative else "neutral"
        emotion_intensity = 0.7 if (positive or negative) else 0.4

        # Feed all layers via hierarchical input
        input_event = {
            "topics": new_topics + keywords[:2],
            "person_interests": self.active_person.get("interests", []) if self.active_person else [],
            "detected_emotion": detected_emotion,
            "emotion_intensity": emotion_intensity,
            "topic_shift": topic_shift,
            "previous_topic": self.previous_topic,
            "playful": playful,
        }
        self.drives.on_input(input_event)

        # Check for reflex-speed reaction
        reflex = self.drives.process_reflex(input_event)
        if reflex:
            self.kg.insert_quad("sophia", "reflex_fired", reflex.trigger, source="INFERENCE")

        # Update person interests
        if self.active_person and keywords:
            cur = self.active_person.get("interests", [])
            new = list(set(cur + keywords[:3]))[:15]
            self.kg.update_person(pid, interests=new)
            self.active_person["interests"] = new

        if self.unified_plan:
            planner_context = self.get_initiative_context()
            planner_context["topic_shift"] = topic_shift
            self.unified_plan = await self.planner.step(
                person_id=pid,
                plan=self.unified_plan,
                user_message=message,
                context=planner_context,
                llm_client=llm_client,
            )
            self.last_decision = self.unified_plan.last_decision
            self.selected_actions = list(self.unified_plan.execution.primitive_actions)
            self.active_goals = ["engage_socially", self.unified_plan.narrative.beat_goal]
            self.drives.deliberation.active_quest = self.unified_plan.narrative.beat_goal
            self.drives.initiative.deliberation_goals = [self.unified_plan.narrative.beat_goal]
            self.kg.insert_quad(
                self.unified_plan.episode_id,
                "planner_decision",
                self.last_decision.narrative_decision if self.last_decision else "unknown",
                source="INFERENCE"
            )
            self.kg.insert_quad(
                self.unified_plan.episode_id,
                "active_beat",
                self.unified_plan.narrative.beat_id,
                source="STORY_ENGINE"
            )
        else:
            self.selected_actions = ["assess_mood", "formulate_response", "speak"]

        init = self.drives.initiative
        if init.boredom > 0.6:
            emo, emo_int = "bored", init.boredom
        elif init.curiosity > 0.7:
            emo, emo_int = "curious", init.curiosity
        elif init.engagement > 0.6:
            emo, emo_int = "engaged", init.engagement
        else:
            emo, emo_int = "neutral", 0.4
        self.kg.log_self_state(
            init.energy, 0.85 + init.engagement * 0.15,
            emo, emo_int, self.active_goals
        )
        return self.assemble_context(message, reflex)

    def assemble_context(self, message: str,
                          reflex: Optional[DriveSignal] = None) -> dict:
        pid = self.active_person["person_id"] if self.active_person else "unknown"
        pair_history = self.kg.query_pair("sophia", pid, limit=15)
        temporal = [
            f"({f['subject']}, {f['relation']}, {f['object'][:40]}, "
            f"{f['timestamp'][:19]})"
            for f in pair_history[:10]
        ]
        init = self.drives.initiative
        # Derive emotion
        if init.boredom > 0.6:
            emo, emo_int = "bored", init.boredom
        elif init.curiosity > 0.7:
            emo, emo_int = "curious", init.curiosity
        elif init.engagement > 0.6:
            emo, emo_int = "engaged", init.engagement
        elif init.dopamine > 0.6:
            emo, emo_int = "happy", init.dopamine
        else:
            emo, emo_int = "neutral", 0.4
        narrative = self.unified_plan.narrative.to_dict() if self.unified_plan else {}
        execution = self.unified_plan.execution.to_dict() if self.unified_plan else {}
        unified_plan = self.unified_plan.to_dict() if self.unified_plan else {}
        last_decision = self.last_decision.to_dict() if self.last_decision else {}
        return {
            "latest_message": message,
            "person": self.active_person or {},
            "conversation_turn": self.conversation_turn,
            "topics_discussed": self.topics,
            "sophia_emotion": emo,
            "sophia_emotion_intensity": emo_int,
            "sophia_energy": init.energy,
            "sophia_coherence": 0.85 + init.engagement * 0.15,
            "active_goals": self.active_goals,
            "selected_actions": self.selected_actions,
            "unified_plan": unified_plan,
            "narrative": narrative,
            "execution": execution,
            "last_decision": last_decision,
            "methods_used_this_session": [],
            "methods_invented": self.methods_invented,
            "temporal_facts_with_person": temporal,
            "total_quads_in_kg": self.kg.count_quads(),
            "self_state_history": [],
            "drives": self.drives.get_state(),
            "reflex_fired": reflex.trigger if reflex else None,
            "recent_chat_history": list(self.chat_history[-8:]),
            "topic_shift": self.last_topic_shift,
        }

    def get_initiative_context(self) -> Dict[str, Any]:
        """Snapshot used to ground LLM-generated initiative messages."""
        pid = self.active_person["person_id"] if self.active_person else "unknown"
        pair_history = self.kg.query_pair("sophia", pid, limit=8)
        temporal = [
            f"({f['subject']}, {f['relation']}, {f['object'][:40]}, "
            f"{f['timestamp'][:19]})"
            for f in pair_history[:4]
        ]
        latest_message = self.chat_history[-1]["text"] if self.chat_history else ""
        return {
            "person": self.active_person or {},
            "conversation_turn": self.conversation_turn,
            "unified_plan": self.unified_plan.to_dict() if self.unified_plan else {},
            "narrative": self.unified_plan.narrative.to_dict() if self.unified_plan else {},
            "execution": self.unified_plan.execution.to_dict() if self.unified_plan else {},
            "topics_discussed": self.topics[-6:],
            "active_goals": self.active_goals,
            "selected_actions": self.selected_actions,
            "latest_message": latest_message,
            "recent_chat_history": list(self.chat_history[-8:]),
            "temporal_facts_with_person": temporal,
            "drives": self.drives.get_state(),
        }

    def log_response(self, text: str, was_successful: bool = True):
        """Log response AND feed reinforcement back through the cognitive loop."""
        self._record_chat_event("assistant", text, kind="reply")
        self.kg.insert_quad("sophia", "said", text[:200], source="STORY_ENGINE")

        # Compute reinforcement from this interaction outcome
        is_social = self.active_person is not None
        is_creative = any(w in text.lower() for w in
                          ["create", "build", "idea", "imagine", "art", "design"])
        is_novel = any("invented" in m for m in self.methods_invented)

        outcome = {
            "success": was_successful,
            "task_name": self.selected_actions[0] if self.selected_actions else "speak",
            "method_name": (
                self.unified_plan.execution.selected_decomposition
                if self.unified_plan else "default"
            ),
            "method_origin": "unified_planner",
            "is_novel": is_novel,
            "is_social": is_social,
            "is_creative": is_creative,
            "partner_response": "positive" if was_successful else "neutral",
        }
        signal = self.cognitive_loop.on_outcome(outcome, self.drives)

        # Log reinforcement to TKG
        self.kg.insert_quad("sophia", "reinforcement",
                            f"reward={signal.reward:.3f}|dop={signal.dopamine_delta:+.3f}",
                            source="INFERENCE")
        if self.last_signal_layer and was_successful:
            self.cognitive_loop.record_signal_usefulness(
                self.last_signal_layer, True)
            self.last_signal_layer = None
        if self.unified_plan and self.active_person:
            self.unified_plan.narrative.story_memory = (
                self.unified_plan.narrative.story_memory + [f"sophia:{text[:160]}"]
            )[-20:]
            self.unified_plan.updated_at = datetime.now(timezone.utc).isoformat()
            self.planner.store.save_plan(
                self.active_person["person_id"], self.unified_plan
            )

    def handle_drive_signal(self, signal: DriveSignal) -> Optional[dict]:
        """Convert a hierarchical drive signal into a message event."""
        absorbed, updated_plan, reason = self.planner.absorb_drive_signal(
            self.unified_plan, signal
        )
        if absorbed:
            self.unified_plan = updated_plan
            if self.unified_plan and self.active_person:
                self.planner.store.save_plan(
                    self.active_person["person_id"], self.unified_plan
                )
            return {
                "type": "planner_absorbed_drive",
                "layer": signal.layer.name,
                "trigger": signal.trigger,
                "reason": reason,
                "plan_id": self.unified_plan.plan_id if self.unified_plan else None,
                "beat_id": self.unified_plan.narrative.beat_id if self.unified_plan else None,
            }
        self._record_chat_event("assistant", signal.message, kind="self_initiated")
        self.kg.insert_quad("sophia", "self_initiated",
                            f"{signal.layer.name}:{signal.trigger}",
                            source="INFERENCE")
        self.kg.insert_quad("sophia", "said", signal.message[:200],
                            source="STORY_ENGINE")
        return {
            "type": "sophia_self_initiated",
            "layer": signal.layer.name,
            "trigger": signal.trigger,
            "intensity": round(signal.intensity, 3),
            "priority": round(signal.priority, 3),
            "sophia_message": signal.message,
            "drives": self.drives.get_state(),
            "quads_in_kg": self.kg.count_quads(),
            "turn": self.conversation_turn,
            "plan_id": self.unified_plan.plan_id if self.unified_plan else None,
        }

    def schedule_background_planner(self, llm_client: Optional[SparkLLMClient]):
        if (
            llm_client is None
            or self.unified_plan is None
            or self.active_person is None
        ):
            return
        if self.background_planner_task and not self.background_planner_task.done():
            return
        context = self.get_initiative_context()
        async def _run_refresh():
            updated = await self.planner.background_refresh(
                self.active_person["person_id"],
                self.unified_plan,
                context,
                llm_client=llm_client,
            )
            if updated is not None:
                self.unified_plan = updated
                self.last_decision = updated.last_decision

        self.background_planner_task = asyncio.create_task(_run_refresh())


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI SERVER WITH WEBSOCKET
# ═══════════════════════════════════════════════════════════════════════════════

mind: Optional[SophiaMindLive] = None
active_websockets: List[WebSocket] = []
drive_task: Optional[asyncio.Task] = None
llm_client: Optional[SparkLLMClient] = None
prompt_manager = get_prompt_manager()


class PromptUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    system_template: Optional[str] = None
    user_template: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mind, drive_task, llm_client
    mind = SophiaMindLive()
    llm_client = get_llm_client()
    await mind.begin_conversation("David", llm_client=llm_client)
    mind.schedule_background_planner(llm_client)
    drive_task = asyncio.create_task(drive_loop())
    logger.info("SPARK server started with drive system active")
    yield
    if drive_task:
        drive_task.cancel()
    if mind.background_planner_task:
        mind.background_planner_task.cancel()
    if llm_client:
        await llm_client.close()
    mind.kg.close()
    mind.planner.close()

app = FastAPI(title="SPARK v2 Live Server", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


async def drive_loop():
    """Background loop: tick all 5 drive layers + cognitive coupling every second."""
    global mind, llm_client
    while True:
        try:
            await asyncio.sleep(1.0)
            if mind is None:
                continue

            # 1. Tick hierarchical drives
            signal = await mind.drives.tick(
                1.0,
                initiative_context=mind.get_initiative_context(),
                llm_client=llm_client,
            )

            # 2. Apply cross-layer cognitive coupling
            adjustment = mind.cognitive_loop.tick(mind.drives)
            if adjustment:
                # Log autoresearch coordination adjustment to TKG
                mind.kg.insert_quad("sophia", "coordination_adjusted",
                                    json.dumps(adjustment)[:200],
                                    source="AUTORESEARCH")

            # 3. If a drive signal fired, emit it
            if signal and active_websockets:
                mind.last_signal_layer = signal.layer.name.lower()
                msg = mind.handle_drive_signal(signal)
                if msg is None:
                    continue
                payload = json.dumps(msg)
                for ws in list(active_websockets):
                    try:
                        await ws.send_text(payload)
                    except Exception:
                        active_websockets.remove(ws)

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Drive loop error: {e}")


@app.websocket("/ws/chat")
async def websocket_chat(ws: WebSocket):
    global mind, llm_client
    await ws.accept()
    active_websockets.append(ws)
    logger.info("WebSocket client connected")

    # Send initial state
    await ws.send_text(json.dumps({
        "type": "init",
        "session_id": mind.session_id,
        "person": mind.active_person,
        "quads_in_kg": mind.kg.count_quads(),
        "drives": mind.drives.to_dict(),
        "unified_plan": mind.unified_plan.to_dict() if mind.unified_plan else {},
        "narrative": (
            mind.unified_plan.narrative.to_dict() if mind.unified_plan else {}
        ),
        "execution": (
            mind.unified_plan.execution.to_dict() if mind.unified_plan else {}
        ),
        "last_decision": mind.last_decision.to_dict() if mind.last_decision else {},
    }))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "user_message":
                text = msg["text"]
                ctx = await mind.process_message(text, llm_client=llm_client)
                prompt_payload = render_sophia_prompt(ctx)
                prompt = prompt_payload["user"]

                await ws.send_text(json.dumps({
                    "type": "context_assembled",
                    "turn": ctx["conversation_turn"],
                    "unified_plan": ctx["unified_plan"],
                    "narrative": ctx["narrative"],
                    "execution": ctx["execution"],
                    "last_decision": ctx["last_decision"],
                    "selected_actions": ctx["selected_actions"],
                    "topics": ctx["topics_discussed"],
                    "drives": mind.drives.to_dict(),
                    "quads_in_kg": ctx["total_quads_in_kg"],
                    "temporal_facts": ctx["temporal_facts_with_person"][:5],
                    "prompt_length": len(prompt),
                    "prompt": prompt,
                    "person_familiarity": ctx["person"].get("familiarity", 0),
                }))

                response = await llm_client.complete(
                    prompt,
                    system=prompt_payload["system"],
                    temperature=0.8,
                    max_tokens=400,
                )
                if response.text:
                    mind.log_response(response.text)
                    mind.schedule_background_planner(llm_client)
                    await ws.send_text(json.dumps({
                        "type": "sophia_reply",
                        "text": response.text,
                        "model": response.model,
                        "turn": ctx["conversation_turn"],
                        "quads_in_kg": mind.kg.count_quads(),
                        "drives": mind.drives.to_dict(),
                    }))
                else:
                    logger.error(
                        "Sophia reply generation failed: stop_reason=%s raw=%s",
                        response.stop_reason,
                        response.raw,
                    )
                    await ws.send_text(json.dumps({
                        "type": "sophia_error",
                        "turn": ctx["conversation_turn"],
                        "error": response.stop_reason or "llm_generation_failed",
                        "details": (response.raw or {}).get("error", "No text returned."),
                    }))

            elif msg.get("type") == "sophia_response":
                mind.log_response(msg.get("text", ""))

    except WebSocketDisconnect:
        active_websockets.remove(ws)
        logger.info("WebSocket client disconnected")


# ─── REST endpoints ───────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return HTMLResponse(CHAT_HTML)

@app.get("/api/status")
async def status():
    return {
        "session_id": mind.session_id if mind else None,
        "quads_in_kg": mind.kg.count_quads() if mind else 0,
        "drives": mind.drives.to_dict() if mind else {},
        "turn": mind.conversation_turn if mind else 0,
        "unified_plan": mind.unified_plan.to_dict() if mind and mind.unified_plan else {},
        "narrative": (
            mind.unified_plan.narrative.to_dict() if mind and mind.unified_plan else {}
        ),
        "execution": (
            mind.unified_plan.execution.to_dict() if mind and mind.unified_plan else {}
        ),
        "last_decision": mind.last_decision.to_dict() if mind and mind.last_decision else {},
        "topics": mind.topics if mind else [],
        "person": mind.active_person if mind else None,
    }

@app.get("/api/kg/recent")
async def kg_recent(limit: int = 30):
    facts = mind.kg.query_recent(hours=48, limit=limit) if mind else []
    return {"facts": facts}

@app.get("/api/kg/count")
async def kg_count():
    return {"count": mind.kg.count_quads() if mind else 0}


@app.get("/api/prompts")
async def prompts_list():
    return {
        "path": prompt_manager.path,
        "prompts": list(prompt_manager.list_prompts().values()),
    }


@app.put("/api/prompts/{prompt_id}")
async def prompts_update(prompt_id: str, payload: PromptUpdateRequest):
    update_data = (
        payload.model_dump(exclude_none=True)
        if hasattr(payload, "model_dump")
        else payload.dict(exclude_none=True)
    )
    try:
        updated = prompt_manager.update_prompt(
            prompt_id,
            **update_data,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PromptValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "path": prompt_manager.path,
        "prompt": updated,
    }


@app.post("/api/prompts/reload")
async def prompts_reload():
    try:
        prompt_manager.reload()
    except PromptValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "path": prompt_manager.path,
        "prompts": list(prompt_manager.list_prompts().values()),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDED CHAT UI
# ═══════════════════════════════════════════════════════════════════════════════

CHAT_HTML = """<!DOCTYPE html>
<html><head><title>SPARK v2 — Sophia Live</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e0e0e0; height: 100vh; display: flex; }
#sidebar { width: 340px; background: #111118; border-right: 1px solid #222; padding: 16px; overflow-y: auto; font-size: 13px; }
#main { flex: 1; display: flex; flex-direction: column; }
#chat { flex: 1; overflow-y: auto; padding: 20px; }
#input-area { padding: 16px; border-top: 1px solid #222; display: flex; gap: 8px; }
#input-area input { flex: 1; background: #1a1a24; border: 1px solid #333; color: #e0e0e0; padding: 12px; border-radius: 8px; font-size: 15px; }
#input-area button { background: #2563eb; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 14px; }
.msg { margin-bottom: 16px; padding: 12px 16px; border-radius: 12px; max-width: 80%; line-height: 1.5; }
.msg.user { background: #1e3a5f; margin-left: auto; }
.msg.sophia { background: #1a2a1a; border: 1px solid #2a4a2a; }
.msg.sophia.self-init { background: #2a1a2a; border: 1px solid #4a2a4a; }
.msg .tag { font-size: 11px; color: #888; margin-bottom: 4px; }
h3 { color: #7aa2f7; margin: 12px 0 8px; font-size: 13px; text-transform: uppercase; letter-spacing: 1px; }
.drive-bar { margin: 3px 0; display: flex; align-items: center; gap: 6px; }
.drive-bar label { width: 80px; font-size: 11px; color: #999; }
.drive-bar .bar { flex: 1; height: 8px; background: #222; border-radius: 4px; overflow: hidden; }
.drive-bar .bar .fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
.fill.low { background: #2563eb; }
.fill.med { background: #eab308; }
.fill.high { background: #ef4444; }
#emotion-display { font-size: 18px; text-align: center; padding: 8px; margin: 8px 0; background: #1a1a24; border-radius: 8px; }
#meta { font-size: 11px; color: #666; padding: 4px 0; }
.tab-row { display: flex; gap: 8px; margin: 12px 0; }
.tab-btn { flex: 1; background: #181824; color: #9aa4bf; border: 1px solid #2a2a36; border-radius: 8px; padding: 8px 10px; font-size: 12px; cursor: pointer; }
.tab-btn.active { background: #2563eb; color: #fff; border-color: #2563eb; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
.context-meta { font-size: 11px; color: #8b93a7; line-height: 1.5; margin-bottom: 10px; white-space: pre-wrap; }
.prompt-box { background: #0d0f16; border: 1px solid #262b38; border-radius: 8px; padding: 12px; font-size: 11px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; color: #d8deef; max-height: 60vh; overflow-y: auto; }
.json-box { background: #0d0f16; border: 1px solid #262b38; border-radius: 8px; padding: 10px; font-size: 11px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; color: #d8deef; max-height: 28vh; overflow-y: auto; margin-bottom: 10px; }
.story-summary { font-size: 12px; color: #c3cbe0; line-height: 1.45; background: #161925; border: 1px solid #262b38; border-radius: 8px; padding: 10px; margin-bottom: 10px; }
.memory-list { font-size: 11px; color: #aab2c8; line-height: 1.5; white-space: pre-wrap; }
.prompt-select, .prompt-input, .prompt-textarea { width: 100%; background: #0d0f16; color: #d8deef; border: 1px solid #262b38; border-radius: 8px; padding: 10px; font-size: 12px; margin-bottom: 10px; }
.prompt-textarea { min-height: 180px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; line-height: 1.45; }
.prompt-actions { display: flex; gap: 8px; margin-bottom: 10px; }
.prompt-actions button { flex: 1; background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 10px; cursor: pointer; font-size: 12px; }
.prompt-actions button.secondary { background: #1f2937; }
.prompt-status { font-size: 11px; color: #8b93a7; white-space: pre-wrap; margin-bottom: 10px; }
.prompt-path { font-size: 11px; color: #8b93a7; word-break: break-all; margin-bottom: 10px; }
</style></head>
<body>
<div id="sidebar">
  <h2 style="color:#7aa2f7;margin-bottom:12px;">SPARK v2</h2>
  <div id="emotion-display">...</div>
  <div id="meta">Session: ... | Quads: 0 | Turn: 0</div>
  <div class="tab-row">
    <button id="tab-state" class="tab-btn active" onclick="showTab('state')">State</button>
    <button id="tab-context" class="tab-btn" onclick="showTab('context')">Context</button>
    <button id="tab-prompts" class="tab-btn" onclick="showTab('prompts')">Prompts</button>
  </div>
  <div id="panel-state" class="tab-panel active">
    <h3>Drives</h3>
    <div id="drives"></div>
    <h3>Planner</h3>
    <div id="planner-info">...</div>
    <h3>Narrative</h3>
    <div id="narrative-summary" class="story-summary">...</div>
    <div id="narrative-view" class="json-box">...</div>
    <h3>Execution</h3>
    <div id="execution-view" class="json-box">...</div>
    <h3>Last Decision</h3>
    <div id="decision-view" class="json-box">...</div>
    <h3>Selected Actions</h3>
    <div id="selected-actions">...</div>
    <h3>Topics</h3>
    <div id="topics">...</div>
    <h3>Story Memory</h3>
    <div id="story-memory" class="memory-list">...</div>
    <h3>Recent TKG Facts</h3>
    <div id="tkg-facts" style="font-size:11px;color:#888;"></div>
  </div>
  <div id="panel-context" class="tab-panel">
    <h3>Context Summary</h3>
    <div id="context-summary" class="context-meta">No context assembled yet.</div>
    <h3>Unified Plan</h3>
    <div id="unified-plan-view" class="json-box">Waiting for the first plan...</div>
    <h3>Model Input</h3>
    <div id="prompt-view" class="prompt-box">Waiting for the first prompt...</div>
  </div>
  <div id="panel-prompts" class="tab-panel">
    <h3>Prompt File</h3>
    <div id="prompt-path" class="prompt-path">Loading...</div>
    <h3>Prompt</h3>
    <select id="prompt-selector" class="prompt-select" onchange="selectPrompt(this.value)"></select>
    <input id="prompt-title" class="prompt-input" placeholder="Prompt title" />
    <input id="prompt-description" class="prompt-input" placeholder="Prompt description" />
    <h3>System Template</h3>
    <textarea id="prompt-system" class="prompt-textarea" spellcheck="false"></textarea>
    <h3>User Template</h3>
    <textarea id="prompt-user" class="prompt-textarea" spellcheck="false"></textarea>
    <div class="prompt-actions">
      <button onclick="savePrompt()">Save Prompt</button>
      <button class="secondary" onclick="reloadPrompts()">Reload File</button>
    </div>
    <div id="prompt-status" class="prompt-status">Prompt editor ready.</div>
  </div>
</div>
<div id="main">
  <div id="chat"></div>
  <div id="input-area">
    <input id="msg" placeholder="Talk to Sophia..." autofocus />
    <button onclick="send()">Send</button>
  </div>
</div>
<script>
const ws = new WebSocket(`ws://${location.host}/ws/chat`);
const chat = document.getElementById('chat');
const msgInput = document.getElementById('msg');
let sessionId = '...';
let promptCatalog = [];
let currentPromptId = '';

function pretty(value) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) {
    return '(none)';
  }
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch (_) {
    return String(value);
  }
}

function showTab(name) {
  const tabIds = ['state', 'context', 'prompts'];
  tabIds.forEach(id => {
    document.getElementById(`tab-${id}`).classList.toggle('active', id === name);
    document.getElementById(`panel-${id}`).classList.toggle('active', id === name);
  });
}

function addMsg(text, cls, tag='') {
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  if (tag) div.innerHTML = `<div class="tag">${tag}</div>`;
  div.innerHTML += text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function deriveStatus(drives) {
  const initiative = drives.layers?.initiative || {};
  const reflection = drives.layers?.reflection || {};
  const candidates = [
    ['curious', initiative.curiosity ?? 0],
    ['restless', initiative.impatience ?? 0],
    ['bored', initiative.boredom ?? 0],
    ['engaged', initiative.engagement ?? 0],
    ['upbeat', initiative.dopamine ?? 0],
    ['attached', reflection.attachment_drive ?? 0],
  ];
  const [label, intensity] = candidates.reduce(
    (best, current) => current[1] > best[1] ? current : best,
    ['stable', 0]
  );
  return { label, intensity };
}

function updateDrives(d) {
  const drives = document.getElementById('drives');
  const initiative = d.layers?.initiative || {};
  const reflection = d.layers?.reflection || {};
  const values = {
    curiosity: initiative.curiosity ?? 0,
    boredom: initiative.boredom ?? 0,
    impatience: initiative.impatience ?? 0,
    energy: initiative.energy ?? 0,
    dopamine: initiative.dopamine ?? 0,
    engagement: initiative.engagement ?? 0,
    social_need: reflection.attachment_drive ?? 0,
  };
  const items = ['curiosity','boredom','impatience','energy','dopamine','engagement','social_need'];
  drives.innerHTML = items.map(k => {
    const v = values[k] ?? 0;
    const pct = (v * 100).toFixed(0);
    const cls = v > 0.7 ? 'high' : v > 0.4 ? 'med' : 'low';
    return `<div class="drive-bar"><label>${k}</label><div class="bar"><div class="fill ${cls}" style="width:${pct}%"></div></div><span style="font-size:11px;width:30px;text-align:right">${pct}%</span></div>`;
  }).join('');

  const status = deriveStatus(d);
  document.getElementById('emotion-display').textContent =
    `${status.label} (${(status.intensity * 100).toFixed(0)}%)`;
}

function updateContextTab(msg) {
  const actionsText = (msg.selected_actions || []).join(' → ') || 'none';
  const topicText = (msg.topics || []).join(', ') || 'none';
  const factCount = (msg.temporal_facts || []).length;
  const narrative = msg.narrative || {};
  const execution = msg.execution || {};
  const decision = msg.last_decision || {};
  document.getElementById('context-summary').textContent =
    `Turn: ${msg.turn}\nStage: ${narrative.stage || 'none'}\nBeat: ${narrative.beat_id || 'none'}\nNarrative decision: ${decision.narrative_decision || 'none'}\nExecution decision: ${decision.execution_decision || 'none'}\nTension: ${((narrative.tension || 0)).toFixed(2)}\nActions: ${actionsText}\nTopics: ${topicText}\nTemporal facts: ${factCount}\nPrompt length: ${msg.prompt_length} chars\nFamiliarity: ${(msg.person_familiarity || 0).toFixed(2)}`;
  document.getElementById('unified-plan-view').textContent = pretty(msg.unified_plan);
  document.getElementById('prompt-view').textContent = msg.prompt || '(no prompt)';
}

function updatePlannerPanels(msg) {
  const plan = msg.unified_plan || {};
  const narrative = msg.narrative || {};
  const execution = msg.execution || {};
  const decision = msg.last_decision || {};
  const memory = narrative.story_memory || [];
  const plotStages = (narrative.a_plot || []).join(' → ') || 'none';
  const actions = (execution.primitive_actions || []).join(' → ') || 'none';
  document.getElementById('planner-info').textContent =
    `Plan: ${plan.plan_id || 'none'}\nStatus: ${plan.status || 'unknown'}\nArchetype: ${narrative.archetype || 'none'}\nStage: ${narrative.stage || 'none'}\nBeat: ${narrative.beat_id || 'none'}\nGoal: ${narrative.beat_goal || 'none'}\nTension: ${((narrative.tension || 0)).toFixed(2)}\nA-plot: ${plotStages}`;
  document.getElementById('narrative-summary').textContent =
    narrative.summary || '(no narrative summary)';
  document.getElementById('narrative-view').textContent = pretty(narrative);
  document.getElementById('execution-view').textContent = pretty(execution);
  document.getElementById('decision-view').textContent = pretty(decision);
  document.getElementById('selected-actions').textContent = actions;
  document.getElementById('story-memory').textContent =
    (memory.length ? memory.map(item => `- ${item}`).join('\\n') : '(none)');
}

function setPromptStatus(text, isError=false) {
  const el = document.getElementById('prompt-status');
  el.textContent = text;
  el.style.color = isError ? '#fca5a5' : '#8b93a7';
}

function renderPromptEditor(promptId) {
  const prompt = promptCatalog.find(item => item.prompt_id === promptId);
  if (!prompt) return;
  currentPromptId = prompt.prompt_id;
  document.getElementById('prompt-selector').value = prompt.prompt_id;
  document.getElementById('prompt-title').value = prompt.title || '';
  document.getElementById('prompt-description').value = prompt.description || '';
  document.getElementById('prompt-system').value = prompt.system_template || '';
  document.getElementById('prompt-user').value = prompt.user_template || '';
  setPromptStatus(`Editing ${prompt.prompt_id}`);
}

function selectPrompt(promptId) {
  renderPromptEditor(promptId);
}

async function loadPrompts(selectedId='') {
  try {
    const res = await fetch('/api/prompts');
    const data = await res.json();
    promptCatalog = data.prompts || [];
    document.getElementById('prompt-path').textContent = data.path || '(unknown path)';
    const selector = document.getElementById('prompt-selector');
    selector.innerHTML = promptCatalog.map(item =>
      `<option value="${item.prompt_id}">${item.prompt_id}</option>`
    ).join('');
    if (!promptCatalog.length) {
      setPromptStatus('No prompts found.', true);
      return;
    }
    renderPromptEditor(selectedId || currentPromptId || promptCatalog[0].prompt_id);
  } catch (err) {
    setPromptStatus(`Failed to load prompts: ${err}`, true);
  }
}

async function savePrompt() {
  if (!currentPromptId) {
    setPromptStatus('No prompt selected.', true);
    return;
  }
  const payload = {
    title: document.getElementById('prompt-title').value,
    description: document.getElementById('prompt-description').value,
    system_template: document.getElementById('prompt-system').value,
    user_template: document.getElementById('prompt-user').value,
  };
  try {
    const res = await fetch(`/api/prompts/${currentPromptId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'prompt update failed');
    }
    await loadPrompts(currentPromptId);
    setPromptStatus(`Saved ${currentPromptId} to ${data.path}`);
  } catch (err) {
    setPromptStatus(`Failed to save prompt: ${err}`, true);
  }
}

async function reloadPrompts() {
  try {
    const res = await fetch('/api/prompts/reload', { method: 'POST' });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || 'prompt reload failed');
    }
    await loadPrompts(currentPromptId);
    setPromptStatus(`Reloaded prompts from ${data.path}`);
  } catch (err) {
    setPromptStatus(`Failed to reload prompts: ${err}`, true);
  }
}

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);

  if (msg.type === 'init') {
    sessionId = msg.session_id || sessionId;
    document.getElementById('meta').textContent =
      `Session: ${sessionId} | Quads: ${msg.quads_in_kg} | Turn: 0`;
    if (msg.drives) updateDrives(msg.drives);
    updatePlannerPanels(msg);
    document.getElementById('unified-plan-view').textContent = pretty(msg.unified_plan);
  }

  if (msg.type === 'context_assembled') {
    updateDrives(msg.drives);
    document.getElementById('meta').textContent =
      `Session: ${sessionId} | Quads: ${msg.quads_in_kg} | Turn: ${msg.turn}`;
    updatePlannerPanels(msg);
    document.getElementById('topics').textContent = msg.topics.join(', ') || 'none';
    document.getElementById('tkg-facts').innerHTML =
      (msg.temporal_facts || []).map(f => `<div>${f}</div>`).join('');
    updateContextTab(msg);

    // Show context note
    addMsg(`[Context assembled: ${msg.prompt_length} chars, ` +
           `beat: ${(msg.narrative || {}).beat_id || 'none'}, ` +
           `actions: ${(msg.selected_actions || []).join('→')}, ` +
           `familiarity: ${(msg.person_familiarity||0).toFixed(2)}]`,
           'sophia', 'SPARK Pipeline');
  }

  if (msg.type === 'planner_absorbed_drive') {
    addMsg(`[Planner absorbed ${msg.layer}:${msg.trigger} into beat ${msg.beat_id || 'none'}]`,
           'sophia', 'Planner');
  }

  if (msg.type === 'sophia_self_initiated') {
    updateDrives(msg.drives);
    document.getElementById('meta').textContent =
      `Session: ${sessionId} | Quads: ${msg.quads_in_kg} | Turn: ${msg.turn}`;
    addMsg(msg.sophia_message, 'sophia self-init',
           `SELF-INITIATED (${msg.trigger}) — turn ${msg.turn}`);
  }

  if (msg.type === 'sophia_reply') {
    updateDrives(msg.drives);
    document.getElementById('meta').textContent =
      `Session: ${sessionId} | Quads: ${msg.quads_in_kg} | Turn: ${msg.turn}`;
    addMsg(msg.text, 'sophia', `Sophia • ${msg.model}`);
  }

  if (msg.type === 'sophia_error') {
    addMsg(`[Response generation failed: ${msg.error}. ${msg.details}]`,
           'sophia', 'Model Error');
  }
};

function send() {
  const text = msgInput.value.trim();
  if (!text) return;
  addMsg(text, 'user');
  ws.send(JSON.stringify({ type: 'user_message', text }));
  msgInput.value = '';
}
msgInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') send(); });
loadPrompts();
</script>
</body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
