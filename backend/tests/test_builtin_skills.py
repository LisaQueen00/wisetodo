from wisetodo.skills.runtime import SkillSource, builtin_skill_root
from wisetodo.tools.defaults import builtin_tools
from wisetodo.tools.failures import tool_failure_message


def test_fallback_restart_and_user_directory_override(tmp_path):
    root = tmp_path / "skills"
    source = SkillSource(root, fallback=builtin_skill_root())
    before = source.begin_run()
    assert len(before.loaded.skills) == 3 and not before.loaded.issues
    assert source.begin_run() == before
    assert not root.exists()
    assert before.candidates(["github_url"], [tool.name for tool in builtin_tools()])
    root.mkdir()
    assert source.begin_run().loaded.skills == ()
    assert len(before.loaded.skills) == 3


def test_explicit_missing_directory_has_no_fallback(tmp_path):
    assert SkillSource(tmp_path / "explicit").begin_run().loaded.skills == ()


def test_safe_failure_categories():
    assert "限流" in tool_failure_message("rate_limited")
    assert "未启用" in tool_failure_message("unknown_tool")
    assert "网络" in tool_failure_message("web_network_failed")
    assert "PRIVATE" not in tool_failure_message("PRIVATE server message")
