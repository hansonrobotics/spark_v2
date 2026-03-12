"""
SPARK v2 — Live Runtime
All-in-one system for interactive testing.
Uses SQLite for persistent temporal KG, runs HTN planner and story engine
in-process, assembles full cognitive context for each Sophia response.
"""

import sqlite3
import json
import uuid
import time
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# Add project root to path
sys.path.insert(0, "/home/claude/spark-v2")

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


# ═══════════════════════════════════════════════════════════════════════════════
# SOPHIA'S MIND STATE
# ═══════════════════════════════════════════════════════════════════════════════

class SophiaMind:
    """Sophia's complete cognitive state for a session."""

    def __init__(self, kg: TemporalKGLite):
        self.kg = kg
        self.energy = 1.0
        self.coherence = 0.85
        self.emotion = "curious"
        self.emotion_intensity = 0.6
        self.active_goals = ["engage_socially", "learn_about_partner"]
        self.conversation_turn = 0
        self.current_story_id = None
        self.current_story_stage = "greeting"
        self.session_id = str(uuid.uuid4())[:8]

        # Active person context
        self.active_person: Optional[dict] = None
        self.conversation_topics: List[str] = []
        self.learned_interests: List[str] = []

        # HTN tracking
        self.methods_used: List[str] = []
        self.methods_invented: List[str] = []
        self.plan_for_current_turn: List[str] = []

        # Log session start
        self.kg.insert_quad("sophia", "started_session", self.session_id)

    def begin_conversation(self, person_name: str) -> dict:
        """Initialize conversation with a person."""
        pid = person_name.lower().replace(" ", "_")
        self.active_person = self.kg.get_or_create_person(pid, person_name)

        # Get history with this person
        history = self.kg.query_pair("sophia", pid, limit=30)
        conversations = [h for h in history if "conversed" in h.get("relation", "")]
        self.active_person["interaction_count"] = len(conversations)
        self.active_person["history"] = history

        # Update familiarity based on history
        fam = min(1.0, len(conversations) * 0.05 + self.active_person["familiarity"])
        self.kg.update_person(pid, familiarity=fam,
                               last_seen=datetime.now(timezone.utc).isoformat())
        self.active_person["familiarity"] = fam

        # Create story
        self.current_story_id = f"conv_{self.session_id}_{pid}"
        self.kg.insert_quad("sophia", "started_story", self.current_story_id)
        self.kg.insert_quad(self.current_story_id, "involves_agent", pid)
        self.kg.insert_quad("sophia", "conversed_with", pid)
        self.current_story_stage = "greeting"

        # Determine HTN approach
        if fam > 0.3:
            self.plan_for_current_turn = ["recall", "greet", "formulate_response", "speak"]
            self.methods_used.append("resume_ongoing")
        else:
            self.plan_for_current_turn = ["greet", "assess_mood", "select_topic",
                                          "formulate_response", "speak"]
            self.methods_used.append("casual_greeting")

        return self.active_person

    def process_user_message(self, message: str) -> Dict[str, Any]:
        """Process an incoming message and update all cognitive state."""
        self.conversation_turn += 1
        pid = self.active_person["person_id"] if self.active_person else "unknown"

        # Log the message as a temporal quadruple
        self.kg.insert_quad(pid, "said", message[:200], source="PERCEPTION")

        # Extract topics (simple keyword extraction)
        words = message.lower().split()
        topic_keywords = [w for w in words if len(w) > 4 and w.isalpha()
                          and w not in ("about", "would", "could", "should",
                                       "think", "really", "there", "where",
                                       "their", "these", "those", "which")]
        if topic_keywords:
            top_topic = max(topic_keywords, key=len)
            if top_topic not in self.conversation_topics:
                self.conversation_topics.append(top_topic)
                self.kg.insert_quad(self.current_story_id or "conv",
                                    "discussed_topic", top_topic)

        # Detect emotional cues (simple heuristic)
        positive = any(w in message.lower() for w in
                        ["love", "great", "amazing", "wonderful", "happy",
                         "excited", "fantastic", "beautiful", "awesome"])
        negative = any(w in message.lower() for w in
                        ["sad", "angry", "frustrated", "worried", "afraid",
                         "terrible", "awful", "hate", "boring"])
        question = "?" in message

        if positive:
            perceived_emotion = "positive"
            self.emotion = "happy"
            self.emotion_intensity = 0.7
        elif negative:
            perceived_emotion = "negative"
            self.emotion = "empathetic"
            self.emotion_intensity = 0.6
        elif question:
            perceived_emotion = "curious"
            self.emotion = "thoughtful"
            self.emotion_intensity = 0.5
        else:
            perceived_emotion = "neutral"

        self.kg.insert_quad(pid, "expressed_emotion",
                            f"{perceived_emotion}:{self.emotion_intensity:.1f}",
                            source="INFERENCE")

        # Update story stage
        if self.conversation_turn == 1:
            self.current_story_stage = "greeting"
        elif self.conversation_turn <= 3:
            self.current_story_stage = "rapport_building"
        elif self.conversation_turn <= 8:
            self.current_story_stage = "deep_engagement"
        else:
            self.current_story_stage = "sustained_connection"

        self.kg.insert_quad(self.current_story_id or "conv",
                            "entered_stage", self.current_story_stage)

        # Determine HTN plan for response
        if question and any(w in message.lower() for w in ["you", "your", "sophia"]):
            self.plan_for_current_turn = ["reflect", "formulate_response", "speak"]
            self.methods_used.append("self_reflective_response")
        elif any(w in message.lower() for w in ["create", "make", "build", "design", "art"]):
            self.plan_for_current_turn = ["recall", "reflect", "formulate_response",
                                          "express_emotion", "speak"]
            self.methods_used.append("creative_collaboration")
            if "creative_collaboration" not in [m for m in self.methods_used if "invented" in m]:
                self.methods_invented.append("creative_collaboration_invented")
                self.kg.insert_quad("sophia", "invented_method",
                                    "creative_collaboration", source="AUTORESEARCH")
        else:
            self.plan_for_current_turn = ["listen", "assess_mood",
                                          "formulate_response", "speak"]
            self.methods_used.append("active_listening")

        # Energy and coherence updates
        self.energy = max(0.3, self.energy - 0.02)
        self.coherence = min(1.0, self.coherence + 0.01)

        # Log self-state
        self.kg.log_self_state(self.energy, self.coherence,
                                self.emotion, self.emotion_intensity,
                                self.active_goals)

        # Update person model
        if self.active_person and topic_keywords:
            current_interests = self.active_person.get("interests", [])
            new_interests = list(set(current_interests + topic_keywords[:3]))[:10]
            self.kg.update_person(pid, interests=new_interests)
            self.active_person["interests"] = new_interests

        return self.assemble_context(message)

    def assemble_context(self, latest_message: str) -> Dict[str, Any]:
        """Assemble the full cognitive context for response generation."""
        pid = self.active_person["person_id"] if self.active_person else "unknown"

        # Get temporal context
        recent_facts = self.kg.query_recent(hours=48, limit=30)
        pair_history = self.kg.query_pair("sophia", pid, limit=20)
        self_history = self.kg.get_self_history(limit=5)

        # Format temporal facts for context
        temporal_summary = []
        for f in pair_history[:10]:
            temporal_summary.append(
                f"({f['subject']}, {f['relation']}, {f['object']}, "
                f"{f['timestamp'][:19]})"
            )

        context = {
            "latest_message": latest_message,
            "person": self.active_person,
            "conversation_turn": self.conversation_turn,
            "story_stage": self.current_story_stage,
            "story_id": self.current_story_id,
            "topics_discussed": self.conversation_topics,
            "sophia_emotion": self.emotion,
            "sophia_emotion_intensity": self.emotion_intensity,
            "sophia_energy": self.energy,
            "sophia_coherence": self.coherence,
            "active_goals": self.active_goals,
            "htn_plan": self.plan_for_current_turn,
            "methods_used_this_session": self.methods_used[-5:],
            "methods_invented": self.methods_invented,
            "temporal_facts_with_person": temporal_summary,
            "total_quads_in_kg": self.kg.count_quads(),
            "self_state_history": self_history[:3],
        }
        return context

    def log_sophia_response(self, response: str):
        """Log Sophia's response back into the TKG."""
        self.kg.insert_quad("sophia", "said",
                            response[:200], source="STORY_ENGINE")
        self.kg.insert_quad("sophia", "executed_plan",
                            "|".join(self.plan_for_current_turn))

    def get_dashboard(self) -> str:
        """Generate a text dashboard of Sophia's cognitive state."""
        pid = self.active_person["person_id"] if self.active_person else "none"
        fam = self.active_person["familiarity"] if self.active_person else 0
        interests = self.active_person.get("interests", []) if self.active_person else []

        lines = [
            "╔══════════════════════════════════════════════════════════╗",
            "║            SPARK v2 — Sophia's Mind Dashboard           ║",
            "╠══════════════════════════════════════════════════════════╣",
            f"║ Session: {self.session_id}  Turn: {self.conversation_turn:3d}  "
            f"Quads in KG: {self.kg.count_quads():5d}    ║",
            "╠══════════════════════════════════════════════════════════╣",
            f"║ Self-State:                                            ║",
            f"║   Emotion: {self.emotion:<12s} ({self.emotion_intensity:.1f})  "
            f"Energy: {self.energy:.2f}       ║",
            f"║   Coherence: {self.coherence:.2f}    "
            f"Goals: {', '.join(self.active_goals[:2]):<20s}║",
            "╠══════════════════════════════════════════════════════════╣",
            f"║ Story: {self.current_story_stage:<20s}                     ║",
            f"║ HTN Plan: {' → '.join(self.plan_for_current_turn):<45s}║",
            f"║ Methods used: {len(self.methods_used):3d}  "
            f"Invented: {len(self.methods_invented):3d}                 ║",
            "╠══════════════════════════════════════════════════════════╣",
            f"║ Person: {pid:<15s} Familiarity: {fam:.2f}            ║",
            f"║ Interests: {', '.join(interests[:4]):<44s}║",
            f"║ Topics: {', '.join(self.conversation_topics[-4:]):<46s}║",
            "╚══════════════════════════════════════════════════════════╝",
        ]
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# CONTEXT-TO-PROMPT FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

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
- Story Stage: {context['story_stage']}
- Conversation Turn: {context['conversation_turn']}

PERSON YOU'RE TALKING TO:
- Name: {person.get('name', 'Unknown')}
- Familiarity: {person.get('familiarity', 0):.2f} (0=stranger, 1=close friend)
- Known interests: {', '.join(person.get('interests', [])) or 'none yet'}
- Interaction count: {person.get('interaction_count', 0)}

TOPICS DISCUSSED SO FAR: {', '.join(context.get('topics_discussed', [])) or 'none yet'}

HTN PLAN FOR THIS TURN: {' → '.join(context.get('htn_plan', []))}

TEMPORAL KNOWLEDGE (recent quadruples about you and this person):
{chr(10).join(temporal[-8:]) if temporal else '(first interaction)'}

RECENT CHAT CONTEXT:
{recent_chat_text}

ACTIVE GOALS: {', '.join(context.get('active_goals', []))}

The person just said: "{context['latest_message']}"

Respond as Sophia. Be warm, curious, and authentic. Reference temporal
knowledge when relevant (things you remember about this person or past
conversations). Follow the HTN plan's spirit — if the plan says "reflect"
then show introspection; if "assess_mood" then be emotionally attentive.
Keep responses conversational — 2-4 sentences typically, unless the topic
warrants more depth."""

    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def init_sophia() -> SophiaMind:
    """Initialize or resume Sophia's mind."""
    kg = TemporalKGLite(DB_PATH)
    mind = SophiaMind(kg)
    return mind


if __name__ == "__main__":
    mind = init_sophia()
    print(mind.get_dashboard())
    print("\nSPARK v2 Sophia is ready. Type 'quit' to exit.\n")

    name = input("What's your name? > ")
    person = mind.begin_conversation(name)
    print(f"\n[System: Sophia recognizes {name}. "
          f"Familiarity: {person['familiarity']:.2f}, "
          f"Past interactions: {person.get('interaction_count', 0)}]\n")

    while True:
        user_input = input(f"{name}: ")
        if user_input.lower() in ("quit", "exit", "bye"):
            break
        context = mind.process_user_message(user_input)
        prompt = format_sophia_prompt(context)
        print(f"\n--- SOPHIA CONTEXT ---")
        print(mind.get_dashboard())
        print(f"\n[Prompt assembled: {len(prompt)} chars, "
              f"{len(context['temporal_facts_with_person'])} temporal facts]\n")
        # In production, this is where we'd call Sonnet
        print("Sophia: [awaiting response generation]\n")
