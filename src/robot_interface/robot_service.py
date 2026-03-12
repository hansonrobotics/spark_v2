"""
SPARK v2 — Robot Interface Service
Unified abstraction for physical Sophia (Hanson SDK) and virtual Sophia (SAIL).
Executes HTN primitive tasks through the appropriate bridge.
"""

import logging
import time
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, WebSocket
from pydantic import BaseModel
import httpx

logger = logging.getLogger("spark.robot")

# ─── Robot Mode ───────────────────────────────────────────────────────────────

class RobotMode(str, Enum):
    PHYSICAL = "physical"
    VIRTUAL = "virtual"
    HYBRID = "hybrid"
    SIMULATION = "simulation"  # No hardware, pure logging


# ─── Expression Mapping (FACS Action Units) ──────────────────────────────────

EXPRESSION_MAP = {
    "happy": {"AU6": 0.8, "AU12": 0.9},
    "sad": {"AU1": 0.6, "AU15": 0.7, "AU17": 0.4},
    "surprised": {"AU1": 0.9, "AU2": 0.9, "AU5": 0.8, "AU26": 0.7},
    "curious": {"AU1": 0.4, "AU2": 0.5, "AU5": 0.3},
    "angry": {"AU4": 0.7, "AU7": 0.5, "AU23": 0.6},
    "disgusted": {"AU9": 0.7, "AU15": 0.4},
    "fearful": {"AU1": 0.8, "AU4": 0.5, "AU5": 0.7, "AU20": 0.6},
    "neutral": {"AU6": 0.0, "AU12": 0.1},
    "attentive_smile": {"AU6": 0.3, "AU12": 0.4, "AU5": 0.2},
    "thinking": {"AU4": 0.3, "AU7": 0.2, "AU14": 0.3},
    "empathetic": {"AU1": 0.3, "AU6": 0.4, "AU12": 0.3},
}


# ─── Hanson SDK Bridge ───────────────────────────────────────────────────────

class HansonSDKBridge:
    """
    Bridge between SPARK HTN primitives and the Hanson Robotics SDK.
    Translates abstract actions into motor commands, TTS calls, etc.
    """

    def __init__(self, sdk_endpoint: str = "http://hanson-sdk:9090"):
        self.endpoint = sdk_endpoint
        self.client = httpx.AsyncClient(timeout=30.0)
        self.connected = False

    async def connect(self):
        try:
            resp = await self.client.get(f"{self.endpoint}/status")
            self.connected = resp.status_code == 200
            logger.info(f"Hanson SDK connected: {self.connected}")
        except Exception as e:
            logger.warning(f"Hanson SDK not available: {e}")
            self.connected = False

    async def execute_primitive(self, task_name: str,
                                  params: Dict[str, Any]) -> Dict[str, Any]:
        dispatch = {
            "speak": self._speak,
            "express_emotion": self._express_emotion,
            "gaze_at": self._gaze_at,
            "gesture": self._gesture,
            "listen": self._listen,
            "greet": self._greet,
            "scan_environment": self._scan_environment,
        }
        handler = dispatch.get(task_name, self._default_handler)
        return await handler(params)

    async def _speak(self, params: Dict) -> Dict:
        utterance = params.get("utterance", "")
        return await self._send_command("speech", {
            "text": utterance,
            "lang": params.get("language", "en"),
            "emotion": params.get("emotion", "neutral"),
        })

    async def _express_emotion(self, params: Dict) -> Dict:
        emotion = params.get("emotion", "neutral")
        intensity = params.get("intensity", 0.5)
        aus = EXPRESSION_MAP.get(emotion, EXPRESSION_MAP["neutral"])
        scaled_aus = {au: val * intensity for au, val in aus.items()}
        return await self._send_command("expression", {
            "action_units": scaled_aus,
            "duration_ms": params.get("duration_ms", 1000),
        })

    async def _gaze_at(self, params: Dict) -> Dict:
        return await self._send_command("gaze", {
            "target_x": params.get("x", 0),
            "target_y": params.get("y", 0),
            "target_z": params.get("z", 1.5),
            "speed": params.get("speed", 0.5),
        })

    async def _gesture(self, params: Dict) -> Dict:
        return await self._send_command("gesture", {
            "gesture_name": params.get("gesture", "wave"),
            "speed": params.get("speed", 1.0),
        })

    async def _listen(self, params: Dict) -> Dict:
        return await self._send_command("listen", {
            "duration_ms": params.get("duration_ms", 5000),
            "language": params.get("language", "en"),
        })

    async def _greet(self, params: Dict) -> Dict:
        name = params.get("person_name", "")
        greeting = f"Hello{', ' + name if name else ''}!"
        await self._express_emotion({"emotion": "happy", "intensity": 0.7})
        return await self._speak({"utterance": greeting})

    async def _scan_environment(self, params: Dict) -> Dict:
        return await self._send_command("perception", {"mode": "scan"})

    async def _default_handler(self, params: Dict) -> Dict:
        return {"status": "no_handler", "params": params}

    async def _send_command(self, command_type: str,
                              payload: Dict) -> Dict:
        if not self.connected:
            return {"status": "simulated", "command": command_type, **payload}
        try:
            resp = await self.client.post(
                f"{self.endpoint}/command/{command_type}",
                json=payload,
            )
            return resp.json()
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ─── SAIL Virtual Bridge ─────────────────────────────────────────────────────

class SAILBridge:
    """
    Bridge to the SAIL (Sophia AI Lab) virtual simulation environment.
    Translates HTN primitives into SAIL WebSocket commands.
    """

    def __init__(self, sail_endpoint: str = "ws://sail-server:8765"):
        self.endpoint = sail_endpoint
        self.ws = None
        self.connected = False

    async def connect(self):
        try:
            # In production, use websockets library
            self.connected = True
            logger.info("SAIL bridge initialized (simulation mode)")
        except Exception as e:
            logger.warning(f"SAIL not available: {e}")
            self.connected = False

    async def execute_primitive(self, task_name: str,
                                  params: Dict[str, Any]) -> Dict[str, Any]:
        sail_cmd = self._translate_to_sail(task_name, params)
        return await self._send_sail_command(sail_cmd)

    def _translate_to_sail(self, task_name: str,
                            params: Dict) -> Dict[str, Any]:
        """Translate HTN primitives to SAIL command format."""
        return {
            "type": "robot_command",
            "action": task_name,
            "params": params,
            "timestamp": time.time(),
            "source": "spark_htn",
        }

    async def _send_sail_command(self, command: Dict) -> Dict:
        if not self.connected:
            return {"status": "simulated", **command}
        # In production: await self.ws.send(json.dumps(command))
        return {"status": "sent", "command": command["action"]}

    async def get_perception(self) -> Dict[str, Any]:
        """Get current perception from SAIL virtual sensors."""
        return {
            "entities_detected": [],
            "audio_input": None,
            "environment": {"type": "virtual", "scene": "default"},
        }


# ─── Unified Interface ───────────────────────────────────────────────────────

class UnifiedRobotInterface:
    """
    Unified abstraction layer supporting physical, virtual, and hybrid modes.
    """

    def __init__(self, mode: RobotMode = RobotMode.SIMULATION):
        self.mode = mode
        self.hanson_bridge = HansonSDKBridge()
        self.sail_bridge = SAILBridge()
        self.execution_log: List[Dict[str, Any]] = []
        self.kg_url = "http://spark-kg:8001"
        self.http_client = httpx.AsyncClient(timeout=10.0)

    async def initialize(self):
        if self.mode in (RobotMode.PHYSICAL, RobotMode.HYBRID):
            await self.hanson_bridge.connect()
        if self.mode in (RobotMode.VIRTUAL, RobotMode.HYBRID):
            await self.sail_bridge.connect()

    async def execute(self, task_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an HTN primitive through the appropriate bridge(s)."""
        start = time.time()
        results = {}

        if self.mode == RobotMode.PHYSICAL:
            results["physical"] = await self.hanson_bridge.execute_primitive(
                task_name, params)
        elif self.mode == RobotMode.VIRTUAL:
            results["virtual"] = await self.sail_bridge.execute_primitive(
                task_name, params)
        elif self.mode == RobotMode.HYBRID:
            results["physical"] = await self.hanson_bridge.execute_primitive(
                task_name, params)
            results["virtual"] = await self.sail_bridge.execute_primitive(
                task_name, params)
        else:  # SIMULATION
            results["simulation"] = {
                "status": "simulated",
                "task": task_name,
                "params": params,
            }

        elapsed = time.time() - start

        # Log execution
        log_entry = {
            "task": task_name,
            "mode": self.mode.value,
            "elapsed_ms": elapsed * 1000,
            "timestamp": datetime.utcnow().isoformat() if datetime else time.time(),
            "results": results,
        }
        self.execution_log.append(log_entry)

        # Log to TKG
        await self._log_action_quadruple(task_name, params, results)

        return {"status": "ok", "mode": self.mode.value, **results}

    async def _log_action_quadruple(self, task_name: str,
                                      params: Dict, results: Dict):
        """Record action as a temporal quadruple in the knowledge graph."""
        try:
            await self.http_client.post(
                f"{self.kg_url}/quadruples",
                json={
                    "subject_id": "sophia",
                    "relation_type": f"executed_{task_name}",
                    "object_id": params.get("target", "environment"),
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "source": "PERCEPTION",
                    "confidence": 1.0,
                }
            )
        except Exception:
            pass  # Non-critical

    def set_mode(self, mode: RobotMode):
        self.mode = mode


# ─── FastAPI Service ──────────────────────────────────────────────────────────

from datetime import datetime

app = FastAPI(title="SPARK Robot Interface", version="2.0")

robot = UnifiedRobotInterface(mode=RobotMode.SIMULATION)


class ExecuteRequest(BaseModel):
    task_name: str
    params: Dict[str, Any] = {}


class ModeRequest(BaseModel):
    mode: str


@app.on_event("startup")
async def startup():
    await robot.initialize()


@app.post("/execute")
async def execute_task(req: ExecuteRequest):
    result = await robot.execute(req.task_name, req.params)
    return result


@app.post("/mode")
async def set_mode(req: ModeRequest):
    try:
        mode = RobotMode(req.mode)
        robot.set_mode(mode)
        await robot.initialize()
        return {"status": "ok", "mode": mode.value}
    except ValueError:
        return {"error": f"Invalid mode: {req.mode}",
                "valid": [m.value for m in RobotMode]}


@app.get("/mode")
async def get_mode():
    return {"mode": robot.mode.value}


@app.get("/log")
async def get_execution_log(limit: int = 50):
    return {"log": robot.execution_log[-limit:]}


@app.get("/expressions")
async def list_expressions():
    return {"expressions": {k: list(v.keys()) for k, v in EXPRESSION_MAP.items()}}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "spark-robot",
        "version": "2.0",
        "mode": robot.mode.value,
        "hanson_connected": robot.hanson_bridge.connected,
        "sail_connected": robot.sail_bridge.connected,
    }
