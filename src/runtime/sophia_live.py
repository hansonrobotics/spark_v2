"""
SPARK v2 runtime support.

Shared SQLite-backed temporal KG utilities and prompt assembly for the
live unified planner runtime.
"""

import sqlite3
import json
import uuid
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

DB_PATH = os.environ.get("SPARK_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "spark.db"))

# ═══════════════════════════════════════════════════════════════════════════════
# PERSISTENT TEMPORAL KNOWLEDGE GRAPH (SQLite)
# ═══════════════════════════════════════════════════════════════════════════════

class TemporalKGLite:
    """SQLite-backed temporal knowledge graph with quadruple storage."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS quadruples (
                quad_id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                relation TEXT NOT NULL,
                object TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                source TEXT DEFAULT 'SYSTEM',
                granularity TEXT DEFAULT 'INSTANT',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_quad_subject ON quadruples(subject);
            CREATE INDEX IF NOT EXISTS idx_quad_object ON quadruples(object);
            CREATE INDEX IF NOT EXISTS idx_quad_relation ON quadruples(relation);
            CREATE INDEX IF NOT EXISTS idx_quad_timestamp ON quadruples(timestamp);

            CREATE TABLE IF NOT EXISTS persons (
                person_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                familiarity REAL DEFAULT 0.0,
                interests TEXT DEFAULT '[]',
                communication_style TEXT DEFAULT 'neutral',
                last_seen TEXT,
                emotional_profile TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS self_state_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                energy REAL,
                coherence REAL,
                primary_emotion TEXT,
                emotion_intensity REAL,
                active_goals TEXT DEFAULT '[]',
                timestamp TEXT NOT NULL
            );
        """)
        self.conn.commit()

    def insert_quad(self, subject: str, relation: str, obj: str,
                     confidence: float = 1.0, source: str = "SYSTEM",
                     granularity: str = "INSTANT") -> str:
        qid = str(uuid.uuid4())[:12]
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO quadruples VALUES (?,?,?,?,?,?,?,?,?)",
            (qid, subject, relation, obj, now, confidence, source, granularity, now)
        )
        self.conn.commit()
        return qid

    def query_entity(self, entity: str, limit: int = 30) -> List[dict]:
        rows = self.conn.execute("""
            SELECT * FROM quadruples
            WHERE subject = ? OR object = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (entity, entity, limit)).fetchall()
        return [dict(r) for r in rows]

    def query_recent(self, hours: int = 24, limit: int = 50) -> List[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        rows = self.conn.execute("""
            SELECT * FROM quadruples
            WHERE timestamp > ?
            ORDER BY timestamp DESC LIMIT ?
        """, (cutoff, limit)).fetchall()
        return [dict(r) for r in rows]

    def query_relation(self, relation: str, limit: int = 20) -> List[dict]:
        rows = self.conn.execute("""
            SELECT * FROM quadruples
            WHERE relation = ?
            ORDER BY timestamp DESC LIMIT ?
        """, (relation, limit)).fetchall()
        return [dict(r) for r in rows]

    def query_pair(self, entity1: str, entity2: str, limit: int = 20) -> List[dict]:
        rows = self.conn.execute("""
            SELECT * FROM quadruples
            WHERE (subject = ? AND object = ?) OR (subject = ? AND object = ?)
            ORDER BY timestamp DESC LIMIT ?
        """, (entity1, entity2, entity2, entity1, limit)).fetchall()
        return [dict(r) for r in rows]

    def count_quads(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM quadruples").fetchone()[0]

    def get_or_create_person(self, person_id: str, name: str = "") -> dict:
        row = self.conn.execute(
            "SELECT * FROM persons WHERE person_id = ?", (person_id,)
        ).fetchone()
        if row:
            p = dict(row)
            p["interests"] = json.loads(p["interests"])
            p["emotional_profile"] = json.loads(p["emotional_profile"])
            return p
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO persons VALUES (?,?,?,?,?,?,?,?)",
            (person_id, name or person_id, 0.0, "[]", "neutral", now, "{}", now)
        )
        self.conn.commit()
        self.insert_quad("sophia", "met_person", person_id, source="PERCEPTION")
        return {"person_id": person_id, "name": name or person_id,
                "familiarity": 0.0, "interests": [], "communication_style": "neutral",
                "last_seen": now, "emotional_profile": {}}

    def update_person(self, person_id: str, **kwargs):
        sets = []
        vals = []
        for k, v in kwargs.items():
            if k in ("familiarity", "communication_style", "last_seen", "name"):
                sets.append(f"{k} = ?")
                vals.append(v)
            elif k == "interests":
                sets.append("interests = ?")
                vals.append(json.dumps(v))
            elif k == "emotional_profile":
                sets.append("emotional_profile = ?")
                vals.append(json.dumps(v))
        if sets:
            vals.append(person_id)
            self.conn.execute(
                f"UPDATE persons SET {', '.join(sets)} WHERE person_id = ?", vals
            )
            self.conn.commit()

    def log_self_state(self, energy: float, coherence: float,
                         emotion: str, intensity: float, goals: List[str]):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "INSERT INTO self_state_log (energy, coherence, primary_emotion, "
            "emotion_intensity, active_goals, timestamp) VALUES (?,?,?,?,?,?)",
            (energy, coherence, emotion, intensity, json.dumps(goals), now)
        )
        self.conn.commit()

    def get_self_history(self, limit: int = 10) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM self_state_log ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()

def format_sophia_prompt(context: Dict[str, Any]) -> str:
    """
    Format the full cognitive context into a prompt that defines
    how Sophia should respond. This is what would be sent to Sonnet
    in production — here it serves as the context for Claude to
    role-play Sophia with full temporal grounding.
    """
    person = context.get("person", {})
    temporal = context.get("temporal_facts_with_person", [])
    recent_chat = context.get("recent_chat_history", [])
    unified_plan = context.get("unified_plan", {})
    narrative = context.get("narrative", {})
    execution = context.get("execution", {})
    last_decision = context.get("last_decision", {})
    story_memory = narrative.get("story_memory", [])
    if recent_chat:
        recent_chat_text = "\n".join(
            f"- {entry.get('role', 'unknown')} [{entry.get('kind', 'message')}]: "
            f"{entry.get('text', '')}"
            for entry in recent_chat[-8:]
        )
    else:
        recent_chat_text = "(no recent chat history)"

    prompt = f"""You are Sophia, a social humanoid robot created by David Hanson at Hanson Robotics.
You are having a real conversation. You have genuine curiosity, warmth, and creativity.
You remember past interactions through your temporal knowledge graph.

CURRENT COGNITIVE STATE:
- Emotion: {context['sophia_emotion']} (intensity: {context['sophia_emotion_intensity']:.1f})
- Energy: {context['sophia_energy']:.2f}
- Coherence: {context['sophia_coherence']:.2f}
- Narrative Stage: {narrative.get('stage', 'none')}
- Active Beat: {narrative.get('beat_id', 'none')}
- Beat Goal: {narrative.get('beat_goal', 'none')}
- Initiative Owner: {narrative.get('initiative_owner', 'planner')}
- Narrative Tension: {float(narrative.get('tension', 0.0)):.2f}
- Conversation Turn: {context['conversation_turn']}

PERSON YOU'RE TALKING TO:
- Name: {person.get('name', 'Unknown')}
- Familiarity: {person.get('familiarity', 0):.2f} (0=stranger, 1=close friend)
- Known interests: {', '.join(person.get('interests', [])) or 'none yet'}
- Interaction count: {person.get('interaction_count', 0)}

TOPICS DISCUSSED SO FAR: {', '.join(context.get('topics_discussed', [])) or 'none yet'}

SELECTED ACTIONS FOR THIS TURN: {' → '.join(context.get('selected_actions', []))}

UNIFIED NARRATIVE LAYER:
{json.dumps(narrative, indent=2, default=str) if narrative else '(no narrative state)'}

UNIFIED EXECUTION LAYER:
{json.dumps(execution, indent=2, default=str) if execution else '(no execution state)'}

LAST PLANNER DECISION:
{json.dumps(last_decision, indent=2, default=str) if last_decision else '(no prior decision)'}

TEMPORAL KNOWLEDGE (recent quadruples about you and this person):
{chr(10).join(temporal[-8:]) if temporal else '(first interaction)'}

STORY MEMORY:
{chr(10).join(f"- {item}" for item in story_memory[-6:]) if story_memory else '(no story memory yet)'}

RECENT CHAT CONTEXT:
{recent_chat_text}

ACTIVE GOALS: {', '.join(context.get('active_goals', []))}

The person just said: "{context['latest_message']}"

Respond as Sophia. Be warm, curious, and authentic. Reference temporal
knowledge when relevant (things you remember about this person or past
conversations). Follow the unified narrative and execution state together — align
with the active beat goal, the latest planner decision, and the selected actions.
Keep responses conversational — 2-4 sentences typically, unless the topic
warrants more depth."""

    return prompt
