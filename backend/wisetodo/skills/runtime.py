"""On-demand reloads with immutable, explicitly owned Run snapshots."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from wisetodo.skills.metadata import SkillLoad, ValidatedSkill, load_skills
from wisetodo.skills.selection import filter_available_skills, select_skills


@dataclass(frozen=True)
class RunSkillSnapshot:
    loaded: SkillLoad

    def candidates(
        self, input_types: Iterable[str], tool_names: Iterable[str] = ()
    ) -> tuple[ValidatedSkill, ...]:
        """All phases of a Run use this snapshot, never the current filesystem."""
        return filter_available_skills(select_skills(self.loaded.skills, input_types), tool_names)


@dataclass(frozen=True)
class SkillSource:
    root: Path

    def __post_init__(self) -> None:
        if not self.root.is_absolute():
            raise ValueError("Skill root must be absolute")

    def begin_run(self) -> RunSkillSnapshot:
        """Reload once at the Run boundary; no watcher, shared cache or retained Runs.

        The caller owns the returned snapshot through generation and repair. A
        new model Run must call again; a pending Todo-only commit needs no reload.
        File reads are independent, not an atomic multi-file filesystem transaction.
        """
        return RunSkillSnapshot(load_skills(self.root))
