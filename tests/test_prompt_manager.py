import os

from src.core.prompt_manager import PromptManager, get_prompt_manager


def test_prompt_manager_renders_and_updates_yaml(tmp_path):
    prompt_file = tmp_path / "prompts.yml"
    prompt_file.write_text(
        """version: 1
prompts:
  demo_prompt:
    title: Demo
    description: Test prompt
    system_template: |
      System for {{ name }}
    user_template: |
      Hello {{ name }}
""",
        encoding="utf-8",
    )

    PromptManager.reset_instance()
    manager = get_prompt_manager(str(prompt_file))
    rendered = manager.render("demo_prompt", {"name": "Sophia"})
    assert rendered["system"] == "System for Sophia"
    assert rendered["user"] == "Hello Sophia"

    updated = manager.update_prompt(
        "demo_prompt",
        description="Updated description",
        user_template="Hi {{ name }} from YAML",
    )
    assert updated["description"] == "Updated description"
    assert "Hi {{ name }} from YAML" in prompt_file.read_text(encoding="utf-8")

    PromptManager.reset_instance()
    manager = get_prompt_manager(str(prompt_file))
    rendered_again = manager.render("demo_prompt", {"name": "David"})
    assert rendered_again["user"] == "Hi David from YAML"


def test_default_prompt_file_contains_live_runtime_prompts():
    PromptManager.reset_instance()
    manager = get_prompt_manager()
    prompts = manager.list_prompts()
    assert os.path.exists(manager.path)
    assert "sophia_response" in prompts
    assert "unified_plan_narrative_step" in prompts
    assert "initiative_generation" in prompts
