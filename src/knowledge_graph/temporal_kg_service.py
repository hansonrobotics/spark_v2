"""
SPARK v2 — Temporal Knowledge Graph Service
Implements quadruple-based temporal knowledge representation
following LTGQ (Geng & Luo, 2025).
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any, Tuple

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from neo4j import AsyncGraphDatabase
import redis.asyncio as redis

logger = logging.getLogger("spark.kg")

# ─── Enums ────────────────────────────────────────────────────────────────────

class TemporalGranularity(str, Enum):
    YEAR = "YEAR"
    MONTH = "MONTH"
    DAY = "DAY"
    HOUR = "HOUR"
    MINUTE = "MINUTE"
    INSTANT = "INSTANT"

class QuadrupleSource(str, Enum):
    PERCEPTION = "PERCEPTION"
    INFERENCE = "INFERENCE"
    TOLD = "TOLD"
    AUTORESEARCH = "AUTORESEARCH"
    STORY_ENGINE = "STORY_ENGINE"

# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class TemporalQuadruple:
    """A fact with temporal dimension: (subject, relation, object, timestamp)."""
    subject_id: str
    relation_type: str
    object_id: str
    timestamp: str  # ISO8601
    quad_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    confidence: float = 1.0
    source: QuadrupleSource = QuadrupleSource.PERCEPTION
    granularity: TemporalGranularity = TemporalGranularity.DAY
    valid_from: Optional[str] = None
    valid_until: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["source"] = self.source.value
        d["granularity"] = self.granularity.value
        return d

    @property
    def hierarchical_timestamp(self) -> Dict[str, int]:
        """Decompose timestamp into hierarchical granularity components."""
        dt = datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        return {
            "year": dt.year,
            "month": dt.month,
            "day": dt.day,
            "hour": dt.hour,
            "minute": dt.minute,
            "second": dt.second,
        }


@dataclass
class TemporalSubgraph:
    """A collection of quadruples forming a temporal subgraph for a story."""
    story_id: str
    quadruples: List[TemporalQuadruple] = field(default_factory=list)
    predictions: List[Dict[str, Any]] = field(default_factory=list)

    def add_quadruple(self, quad: TemporalQuadruple):
        self.quadruples.append(quad)

    def query_by_entity(self, entity_id: str) -> List[TemporalQuadruple]:
        return [q for q in self.quadruples
                if q.subject_id == entity_id or q.object_id == entity_id]

    def query_by_time_range(self, start: str, end: str) -> List[TemporalQuadruple]:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        results = []
        for q in self.quadruples:
            q_dt = datetime.fromisoformat(q.timestamp.replace("Z", "+00:00"))
            if start_dt <= q_dt <= end_dt:
                results.append(q)
        return sorted(results, key=lambda x: x.timestamp)


# ─── LTGQ Embedding Engine ───────────────────────────────────────────────────

class LTGQEmbeddingEngine:
    """
    Learning Temporal Granularity with Quadruplet Networks.
    Maps entities, relations, and timestamps into distinct specialized spaces
    using triaffine transformations and temporal DCNNs.
    """

    def __init__(self, entity_dim: int = 256, relation_dim: int = 128,
                 time_dim: int = 64, num_granularities: int = 6):
        self.entity_dim = entity_dim
        self.relation_dim = relation_dim
        self.time_dim = time_dim
        self.num_granularities = num_granularities

        # Embedding tables (in production, these are learned parameters)
        self.entity_embeddings: Dict[str, np.ndarray] = {}
        self.relation_embeddings: Dict[str, np.ndarray] = {}
        self.time_embeddings: Dict[str, np.ndarray] = {}

        # Triaffine transformation matrices
        self.W_triaffine = np.random.randn(entity_dim, relation_dim, time_dim) * 0.01

    def get_or_create_entity_embedding(self, entity_id: str) -> np.ndarray:
        if entity_id not in self.entity_embeddings:
            self.entity_embeddings[entity_id] = np.random.randn(self.entity_dim) * 0.1
        return self.entity_embeddings[entity_id]

    def get_or_create_relation_embedding(self, relation: str) -> np.ndarray:
        if relation not in self.relation_embeddings:
            self.relation_embeddings[relation] = np.random.randn(self.relation_dim) * 0.1
        return self.relation_embeddings[relation]

    def encode_timestamp_hierarchical(self, timestamp: str) -> np.ndarray:
        """Encode timestamp with hierarchical granularity."""
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        # Each granularity level gets its own embedding subspace
        granularity_encodings = []
        for val, max_val in [(dt.year - 2020, 30), (dt.month, 12),
                              (dt.day, 31), (dt.hour, 24),
                              (dt.minute, 60), (dt.second, 60)]:
            # Sinusoidal positional encoding per granularity
            dim = self.time_dim // self.num_granularities
            encoding = np.zeros(dim)
            for i in range(dim // 2):
                freq = 1.0 / (10000 ** (2 * i / dim))
                encoding[2 * i] = np.sin(val * freq / max_val)
                encoding[2 * i + 1] = np.cos(val * freq / max_val)
            granularity_encodings.append(encoding)
        result = np.concatenate(granularity_encodings)
        # Pad or truncate to exactly time_dim
        if len(result) < self.time_dim:
            result = np.pad(result, (0, self.time_dim - len(result)))
        return result[:self.time_dim]

    def score_quadruple(self, quad: TemporalQuadruple) -> float:
        """Score a quadruple using triaffine transformation."""
        s = self.get_or_create_entity_embedding(quad.subject_id)
        r = self.get_or_create_relation_embedding(quad.relation_type)
        o = self.get_or_create_entity_embedding(quad.object_id)
        t = self.encode_timestamp_hierarchical(quad.timestamp)

        # Simplified triaffine: score = s^T * W * [r; t] * o
        rt = np.concatenate([r, t])[:self.relation_dim]
        score = float(np.dot(s, np.dot(self.W_triaffine[:, :, :self.time_dim].reshape(
            self.entity_dim, -1)[:, :self.relation_dim], rt)) * np.mean(o))
        return score

    def predict_temporal_link(self, subject_id: str, relation: str,
                               timestamp: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Predict object entities given subject, relation, and timestamp."""
        s = self.get_or_create_entity_embedding(subject_id)
        r = self.get_or_create_relation_embedding(relation)
        t = self.encode_timestamp_hierarchical(timestamp)

        # Pad relation to entity dimension for combination
        r_padded = np.zeros(self.entity_dim)
        r_padded[:self.relation_dim] = r

        scores = {}
        for entity_id, embedding in self.entity_embeddings.items():
            if entity_id == subject_id:
                continue
            t_padded = np.zeros(self.entity_dim)
            t_padded[:min(self.time_dim, self.entity_dim)] = t[:min(self.time_dim, self.entity_dim)]
            score = float(np.dot(s + r_padded, embedding) +
                         0.1 * np.dot(t_padded, embedding))
            scores[entity_id] = score

        return sorted(scores.items(), key=lambda x: -x[1])[:top_k]


# ─── Neo4j Temporal KG Store ─────────────────────────────────────────────────

class TemporalKGStore:
    """Neo4j-backed temporal knowledge graph with quadruple support."""

    def __init__(self, uri: str = "bolt://neo4j:7687",
                 user: str = "neo4j", password: str = "spark_password"):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def initialize(self):
        """Create indexes and constraints for temporal queries."""
        async with self.driver.session() as session:
            await session.run("""
                CREATE INDEX quad_timestamp IF NOT EXISTS
                FOR ()-[r:TEMPORAL_FACT]-()
                ON (r.timestamp)
            """)
            await session.run("""
                CREATE INDEX entity_name IF NOT EXISTS
                FOR (n:Entity)
                ON (n.name)
            """)
            await session.run("""
                CREATE CONSTRAINT entity_id IF NOT EXISTS
                FOR (n:Entity)
                REQUIRE n.entity_id IS UNIQUE
            """)

    async def insert_quadruple(self, quad: TemporalQuadruple):
        """Insert a temporal quadruple into Neo4j."""
        query = """
        MERGE (s:Entity {entity_id: $subject_id})
        MERGE (o:Entity {entity_id: $object_id})
        CREATE (s)-[r:TEMPORAL_FACT {
            quad_id: $quad_id,
            relation_type: $relation_type,
            timestamp: datetime($timestamp),
            confidence: $confidence,
            source: $source,
            granularity: $granularity,
            valid_from: CASE WHEN $valid_from IS NOT NULL
                         THEN datetime($valid_from) ELSE NULL END,
            valid_until: CASE WHEN $valid_until IS NOT NULL
                          THEN datetime($valid_until) ELSE NULL END
        }]->(o)
        RETURN r.quad_id AS id
        """
        async with self.driver.session() as session:
            result = await session.run(query, **quad.to_dict())
            record = await result.single()
            return record["id"] if record else None

    async def query_entity_timeline(self, entity_id: str,
                                      limit: int = 50) -> List[dict]:
        """Get temporal facts about an entity, ordered by time."""
        query = """
        MATCH (s:Entity {entity_id: $entity_id})-[r:TEMPORAL_FACT]->(o:Entity)
        RETURN s.entity_id AS subject, r.relation_type AS relation,
               o.entity_id AS object, r.timestamp AS timestamp,
               r.confidence AS confidence, r.granularity AS granularity
        ORDER BY r.timestamp DESC
        LIMIT $limit
        """
        async with self.driver.session() as session:
            result = await session.run(query, entity_id=entity_id, limit=limit)
            return [dict(record) async for record in result]

    async def query_time_range(self, start: str, end: str,
                                entity_id: Optional[str] = None) -> List[dict]:
        """Query quadruples within a time range."""
        if entity_id:
            query = """
            MATCH (s:Entity)-[r:TEMPORAL_FACT]->(o:Entity)
            WHERE r.timestamp >= datetime($start)
              AND r.timestamp <= datetime($end)
              AND (s.entity_id = $entity_id OR o.entity_id = $entity_id)
            RETURN s.entity_id AS subject, r.relation_type AS relation,
                   o.entity_id AS object, r.timestamp AS timestamp,
                   r.confidence AS confidence
            ORDER BY r.timestamp
            """
        else:
            query = """
            MATCH (s:Entity)-[r:TEMPORAL_FACT]->(o:Entity)
            WHERE r.timestamp >= datetime($start)
              AND r.timestamp <= datetime($end)
            RETURN s.entity_id AS subject, r.relation_type AS relation,
                   o.entity_id AS object, r.timestamp AS timestamp,
                   r.confidence AS confidence
            ORDER BY r.timestamp
            """
        async with self.driver.session() as session:
            result = await session.run(query, start=start, end=end,
                                        entity_id=entity_id)
            return [dict(record) async for record in result]

    async def get_relationship_evolution(self, entity1: str, entity2: str,
                                          relation: str) -> List[dict]:
        """Track how a relationship evolves over time."""
        query = """
        MATCH (s:Entity {entity_id: $e1})-[r:TEMPORAL_FACT {
            relation_type: $relation
        }]->(o:Entity {entity_id: $e2})
        RETURN r.timestamp AS timestamp, r.confidence AS confidence,
               r.quad_id AS quad_id
        ORDER BY r.timestamp
        """
        async with self.driver.session() as session:
            result = await session.run(query, e1=entity1, e2=entity2,
                                        relation=relation)
            return [dict(record) async for record in result]

    async def close(self):
        await self.driver.close()


# ─── FastAPI Service ──────────────────────────────────────────────────────────

app = FastAPI(title="SPARK Temporal Knowledge Graph Service", version="2.0")

kg_store: Optional[TemporalKGStore] = None
embedding_engine: Optional[LTGQEmbeddingEngine] = None
redis_client: Optional[redis.Redis] = None


class QuadrupleRequest(BaseModel):
    subject_id: str
    relation_type: str
    object_id: str
    timestamp: str
    confidence: float = 1.0
    source: str = "PERCEPTION"
    granularity: str = "DAY"


class TimeRangeQuery(BaseModel):
    start: str
    end: str
    entity_id: Optional[str] = None


@app.on_event("startup")
async def startup():
    global kg_store, embedding_engine, redis_client
    import os
    kg_store = TemporalKGStore(
        uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "spark_password"),
    )
    await kg_store.initialize()
    embedding_engine = LTGQEmbeddingEngine()
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379"))


@app.on_event("shutdown")
async def shutdown():
    if kg_store:
        await kg_store.close()
    if redis_client:
        await redis_client.close()


@app.post("/quadruples")
async def insert_quadruple(req: QuadrupleRequest):
    quad = TemporalQuadruple(
        subject_id=req.subject_id,
        relation_type=req.relation_type,
        object_id=req.object_id,
        timestamp=req.timestamp,
        confidence=req.confidence,
        source=QuadrupleSource(req.source),
        granularity=TemporalGranularity(req.granularity),
    )
    quad_id = await kg_store.insert_quadruple(quad)
    # Cache in Redis for real-time access
    await redis_client.setex(
        f"quad:{quad_id}", 3600, json.dumps(quad.to_dict())
    )
    return {"quad_id": quad_id, "status": "inserted"}


@app.get("/entities/{entity_id}/timeline")
async def get_entity_timeline(entity_id: str, limit: int = 50):
    facts = await kg_store.query_entity_timeline(entity_id, limit)
    return {"entity_id": entity_id, "facts": facts}


@app.post("/query/time-range")
async def query_time_range(req: TimeRangeQuery):
    facts = await kg_store.query_time_range(req.start, req.end, req.entity_id)
    return {"facts": facts, "count": len(facts)}


@app.get("/entities/{e1}/relationship/{relation}/with/{e2}")
async def get_relationship_evolution(e1: str, relation: str, e2: str):
    evolution = await kg_store.get_relationship_evolution(e1, e2, relation)
    return {"entity1": e1, "entity2": e2, "relation": relation,
            "evolution": evolution}


@app.post("/predict/link")
async def predict_link(subject_id: str, relation: str,
                       timestamp: str, top_k: int = 5):
    predictions = embedding_engine.predict_temporal_link(
        subject_id, relation, timestamp, top_k
    )
    return {"predictions": [{"entity": e, "score": s} for e, s in predictions]}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "spark-kg", "version": "2.0"}
