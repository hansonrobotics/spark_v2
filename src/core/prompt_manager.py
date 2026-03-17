"""
Global YAML-backed prompt manager for SPARK.

Prompts are stored in a single YAML file and rendered through Jinja templates.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml
from jinja2 import ChainableUndefined, Environment, TemplateError


DEFAULT_PROMPTS_PATH = os.environ.get(
    "SPARK_PROMPTS_PATH",
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "..",
        "config",
        "prompts.yml",
    ),
)


class PromptValidationError(ValueError):
    """Raised when a prompt template cannot be loaded or rendered."""


@dataclass
class PromptSpec:
    prompt_id: str
    title: str
    description: str
    system_template: str
    user_template: str

    @classmethod
    def from_dict(cls, prompt_id: str, payload: Dict[str, Any]) -> "PromptSpec":
        return cls(
            prompt_id=prompt_id,
            title=str(payload.get("title", prompt_id)),
            description=str(payload.get("description", "")),
            system_template=str(payload.get("system_template", "")),
            user_template=str(payload.get("user_template", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "title": self.title,
            "description": self.description,
            "system_template": self.system_template,
            "user_template": self.user_template,
        }


class _PromptYAMLDumper(yaml.SafeDumper):
    pass


def _string_presenter(dumper: yaml.SafeDumper, data: str):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_PromptYAMLDumper.add_representer(str, _string_presenter)


class PromptManager:
    _instance: Optional["PromptManager"] = None
    _instance_lock = threading.RLock()

    def __init__(self, path: Optional[str] = None):
        self.path = os.path.abspath(path or DEFAULT_PROMPTS_PATH)
        self._lock = threading.RLock()
        self._env = Environment(
            autoescape=False,
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
            undefined=ChainableUndefined,
        )
        self._prompts: Dict[str, PromptSpec] = {}
        self.reload()

    @classmethod
    def get_instance(cls, path: Optional[str] = None) -> "PromptManager":
        with cls._instance_lock:
            resolved = os.path.abspath(path or DEFAULT_PROMPTS_PATH)
            if cls._instance is None or cls._instance.path != resolved:
                cls._instance = cls(resolved)
            return cls._instance

    @classmethod
    def reset_instance(cls):
        with cls._instance_lock:
            cls._instance = None

    def reload(self):
        with self._lock:
            if not os.path.exists(self.path):
                raise FileNotFoundError(f"Prompt YAML not found: {self.path}")
            with open(self.path, "r", encoding="utf-8") as handle:
                payload = yaml.safe_load(handle) or {}
            prompts = payload.get("prompts")
            if not isinstance(prompts, dict) or not prompts:
                raise PromptValidationError(
                    f"Prompt YAML must contain a non-empty 'prompts' mapping: {self.path}"
                )
            loaded: Dict[str, PromptSpec] = {}
            for prompt_id, item in prompts.items():
                if not isinstance(item, dict):
                    raise PromptValidationError(
                        f"Prompt '{prompt_id}' must be a mapping in {self.path}"
                    )
                spec = PromptSpec.from_dict(prompt_id, item)
                self._validate_spec(spec)
                loaded[prompt_id] = spec
            self._prompts = loaded

    def list_prompts(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {
                prompt_id: spec.to_dict()
                for prompt_id, spec in sorted(self._prompts.items())
            }

    def get_prompt(self, prompt_id: str) -> Dict[str, Any]:
        with self._lock:
            spec = self._require_prompt(prompt_id)
            return spec.to_dict()

    def render(self, prompt_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        ctx = dict(context or {})
        with self._lock:
            spec = self._require_prompt(prompt_id)
            try:
                system_text = self._env.from_string(spec.system_template).render(**ctx).strip()
                user_text = self._env.from_string(spec.user_template).render(**ctx).strip()
            except TemplateError as exc:
                raise PromptValidationError(
                    f"Failed to render prompt '{prompt_id}': {exc}"
                ) from exc
            return {
                "prompt_id": prompt_id,
                "title": spec.title,
                "description": spec.description,
                "system": system_text,
                "user": user_text,
            }

    def update_prompt(
        self,
        prompt_id: str,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        system_template: Optional[str] = None,
        user_template: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            current = self._require_prompt(prompt_id)
            updated = PromptSpec(
                prompt_id=prompt_id,
                title=current.title if title is None else str(title),
                description=current.description if description is None else str(description),
                system_template=(
                    current.system_template if system_template is None else str(system_template)
                ),
                user_template=current.user_template if user_template is None else str(user_template),
            )
            self._validate_spec(updated)
            self._prompts[prompt_id] = updated
            self._save_locked()
            return updated.to_dict()

    def _save_locked(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        payload = {
            "version": 1,
            "prompts": {
                prompt_id: {
                    "title": spec.title,
                    "description": spec.description,
                    "system_template": spec.system_template,
                    "user_template": spec.user_template,
                }
                for prompt_id, spec in sorted(self._prompts.items())
            },
        }
        with open(self.path, "w", encoding="utf-8") as handle:
            yaml.dump(
                payload,
                handle,
                Dumper=_PromptYAMLDumper,
                allow_unicode=False,
                sort_keys=False,
                width=1000,
            )

    def _require_prompt(self, prompt_id: str) -> PromptSpec:
        spec = self._prompts.get(prompt_id)
        if spec is None:
            raise KeyError(f"Unknown prompt id: {prompt_id}")
        return spec

    def _validate_spec(self, spec: PromptSpec):
        if not spec.user_template.strip():
            raise PromptValidationError(f"Prompt '{spec.prompt_id}' is missing a user_template")
        try:
            self._env.parse(spec.system_template)
            self._env.parse(spec.user_template)
        except TemplateError as exc:
            raise PromptValidationError(
                f"Prompt '{spec.prompt_id}' has invalid Jinja syntax: {exc}"
            ) from exc


def get_prompt_manager(path: Optional[str] = None) -> PromptManager:
    return PromptManager.get_instance(path)
