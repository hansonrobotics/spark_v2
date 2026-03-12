"""
SPARK v2 — Live Server with Drive System
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
import time
import uuid
import math
import random
import sqlite3
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, _PROJECT_ROOT)
from src.runtime.sophia_live import TemporalKGLite, format_sophia_prompt
from src.core.hierarchical_drives import (
    HierarchicalDriveSystem, DriveLayer, DriveSignal
)
from src.core.cognitive_coupling import (
    UnifiedCognitiveLoop, DriveReinforcementSignal
)
from src.core.llm_client import SparkLLMClient, get_llm_client

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
        self.drives = HierarchicalDriveSystem()
        self.cognitive_loop = UnifiedCognitiveLoop()
        self.session_id = str(uuid.uuid4())[:8]
        self.conversation_turn = 0
        self.active_person: Optional[dict] = None
        self.topics: List[str] = []
        self.active_goals: List[str] = ["engage_socially", "learn_about_partner"]
        self.current_story_stage = "idle"
        self.current_story_id: Optional[str] = None
        self.methods_invented: List[str] = []
        self.plan: List[str] = []
        self.previous_topic: str = ""
        self.last_signal_layer: Optional[str] = None
        self.chat_history: List[Dict[str, str]] = []

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

    def begin_conversation(self, person_name: str) -> dict:
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
        self.current_story_id = f"conv_{self.session_id}_{pid}"
        self.kg.insert_quad("sophia", "started_story", self.current_story_id)
        self.kg.insert_quad("sophia", "conversed_with", pid)
        self.current_story_stage = "greeting"
        self.drives.initiative.conversation_active = True
        self.drives.initiative.on_input()

        # Initialize cross-session reflection layer with TKG data
        self.drives.on_session_start(history, fam)
        return self.active_person

    def process_message(self, message: str) -> dict:
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
                self.kg.insert_quad(self.current_story_id or "conv",
                                    "discussed_topic", kw)

        # Detect topic shift
        topic_shift = bool(new_topics and self.previous_topic and
                          self.previous_topic not in new_topics)
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

        # Story stage
        if self.conversation_turn <= 1:
            self.current_story_stage = "greeting"
        elif self.conversation_turn <= 3:
            self.current_story_stage = "rapport_building"
        elif self.conversation_turn <= 8:
            self.current_story_stage = "deep_engagement"
        else:
            self.current_story_stage = "sustained_connection"

        # HTN plan selection
        has_question = "?" in message
        is_creative = any(w in message.lower() for w in
                          ["create","make","build","design","art","dream"])
        is_philosophical = any(w in message.lower() for w in
                               ["feel","conscious","alive","think","mind",
                                "embodiment","dream","sentience","life"])
        if is_philosophical:
            self.plan = ["recall","reflect","reflect","formulate_response",
                         "express_emotion","speak"]
        elif is_creative:
            self.plan = ["recall","reflect","formulate_response",
                         "express_emotion","speak"]
        elif has_question:
            self.plan = ["reflect","formulate_response","speak"]
        else:
            self.plan = ["listen","assess_mood","formulate_response","speak"]

        # Update person interests
        if self.active_person and keywords:
            cur = self.active_person.get("interests", [])
            new = list(set(cur + keywords[:3]))[:15]
            self.kg.update_person(pid, interests=new)
            self.active_person["interests"] = new

        # Log self state
        init = self.drives.initiative
        # Derive emotion from initiative layer state
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
        return {
            "latest_message": message,
            "person": self.active_person or {},
            "conversation_turn": self.conversation_turn,
            "story_stage": self.current_story_stage,
            "story_id": self.current_story_id,
            "topics_discussed": self.topics,
            "sophia_emotion": emo,
            "sophia_emotion_intensity": emo_int,
            "sophia_energy": init.energy,
            "sophia_coherence": 0.85 + init.engagement * 0.15,
            "active_goals": self.active_goals,
            "htn_plan": self.plan,
            "methods_used_this_session": [],
            "methods_invented": self.methods_invented,
            "temporal_facts_with_person": temporal,
            "total_quads_in_kg": self.kg.count_quads(),
            "self_state_history": [],
            "drives": self.drives.get_state(),
            "reflex_fired": reflex.trigger if reflex else None,
            "recent_chat_history": list(self.chat_history[-8:]),
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
            "story_stage": self.current_story_stage,
            "topics_discussed": self.topics[-6:],
            "active_goals": self.active_goals,
            "htn_plan": self.plan,
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
            "task_name": self.plan[0] if self.plan else "speak",
            "method_name": self.plan[-1] if self.plan else "default",
            "method_origin": "built_in",
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

        # Record whether the last self-initiated signal was useful
        if self.last_signal_layer and was_successful:
            self.cognitive_loop.record_signal_usefulness(
                self.last_signal_layer, True)
            self.last_signal_layer = None

    def handle_drive_signal(self, signal: DriveSignal) -> dict:
        """Convert a hierarchical drive signal into a message event."""
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
            "story_stage": self.current_story_stage,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI SERVER WITH WEBSOCKET
# ═══════════════════════════════════════════════════════════════════════════════

mind: Optional[SophiaMindLive] = None
active_websockets: List[WebSocket] = []
drive_task: Optional[asyncio.Task] = None
llm_client: Optional[SparkLLMClient] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mind, drive_task, llm_client
    mind = SophiaMindLive()
    llm_client = get_llm_client()
    mind.begin_conversation("David")
    drive_task = asyncio.create_task(drive_loop())
    logger.info("SPARK server started with drive system active")
    yield
    if drive_task:
        drive_task.cancel()
    if llm_client:
        await llm_client.close()
    mind.kg.close()

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
    }))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("type") == "user_message":
                text = msg["text"]
                ctx = mind.process_message(text)
                prompt = format_sophia_prompt(ctx)

                await ws.send_text(json.dumps({
                    "type": "context_assembled",
                    "turn": ctx["conversation_turn"],
                    "story_stage": ctx["story_stage"],
                    "htn_plan": ctx["htn_plan"],
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
                    temperature=0.8,
                    max_tokens=400,
                )
                if response.text:
                    mind.log_response(response.text)
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
        "story_stage": mind.current_story_stage if mind else "none",
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
</style></head>
<body>
<div id="sidebar">
  <h2 style="color:#7aa2f7;margin-bottom:12px;">SPARK v2</h2>
  <div id="emotion-display">...</div>
  <div id="meta">Session: ... | Quads: 0 | Turn: 0</div>
  <div class="tab-row">
    <button id="tab-state" class="tab-btn active" onclick="showTab('state')">State</button>
    <button id="tab-context" class="tab-btn" onclick="showTab('context')">Context</button>
  </div>
  <div id="panel-state" class="tab-panel active">
    <h3>Drives</h3>
    <div id="drives"></div>
    <h3>Story</h3>
    <div id="story-info">...</div>
    <h3>HTN Plan</h3>
    <div id="htn-plan">...</div>
    <h3>Topics</h3>
    <div id="topics">...</div>
    <h3>Recent TKG Facts</h3>
    <div id="tkg-facts" style="font-size:11px;color:#888;"></div>
  </div>
  <div id="panel-context" class="tab-panel">
    <h3>Context Summary</h3>
    <div id="context-summary" class="context-meta">No context assembled yet.</div>
    <h3>Model Input</h3>
    <div id="prompt-view" class="prompt-box">Waiting for the first prompt...</div>
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

function showTab(name) {
  const tabIds = ['state', 'context'];
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
  const planText = (msg.htn_plan || []).join(' → ') || 'none';
  const topicText = (msg.topics || []).join(', ') || 'none';
  const factCount = (msg.temporal_facts || []).length;
  document.getElementById('context-summary').textContent =
    `Turn: ${msg.turn}\nStory: ${msg.story_stage}\nPlan: ${planText}\nTopics: ${topicText}\nTemporal facts: ${factCount}\nPrompt length: ${msg.prompt_length} chars\nFamiliarity: ${(msg.person_familiarity || 0).toFixed(2)}`;
  document.getElementById('prompt-view').textContent = msg.prompt || '(no prompt)';
}

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);

  if (msg.type === 'init') {
    sessionId = msg.session_id || sessionId;
    document.getElementById('meta').textContent =
      `Session: ${sessionId} | Quads: ${msg.quads_in_kg} | Turn: 0`;
    if (msg.drives) updateDrives(msg.drives);
  }

  if (msg.type === 'context_assembled') {
    updateDrives(msg.drives);
    document.getElementById('meta').textContent =
      `Session: ${sessionId} | Quads: ${msg.quads_in_kg} | Turn: ${msg.turn}`;
    document.getElementById('story-info').textContent = msg.story_stage;
    document.getElementById('htn-plan').textContent = msg.htn_plan.join(' → ');
    document.getElementById('topics').textContent = msg.topics.join(', ') || 'none';
    document.getElementById('tkg-facts').innerHTML =
      (msg.temporal_facts || []).map(f => `<div>${f}</div>`).join('');
    updateContextTab(msg);

    // Show context note
    addMsg(`[Context assembled: ${msg.prompt_length} chars, ` +
           `plan: ${msg.htn_plan.join('→')}, ` +
           `familiarity: ${(msg.person_familiarity||0).toFixed(2)}]`,
           'sophia', 'SPARK Pipeline');
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
</script>
</body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
