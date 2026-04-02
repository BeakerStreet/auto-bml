import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List

from .models import BmlState, RunMetadata, RunStatus

RUN_FILE = Path(".bml/runs.json")
STATE_FILE = Path(".bml/state.json")
ITERATION_HOURS = 6


def load() -> List[RunMetadata]:
    if not RUN_FILE.exists():
        return []
    data = json.loads(RUN_FILE.read_text())
    return [RunMetadata.model_validate(r) for r in data]


def save(runs: List[RunMetadata]) -> None:
    RUN_FILE.parent.mkdir(exist_ok=True)
    RUN_FILE.write_text(
        json.dumps([r.model_dump(mode="json") for r in runs], indent=2)
    )


def append(run: RunMetadata) -> None:
    runs = load()
    runs.append(run)
    save(runs)


def update(run: RunMetadata) -> None:
    runs = load()
    for i, r in enumerate(runs):
        if r.run_id == run.run_id:
            runs[i] = run
            break
    save(runs)


def find_ready_runs(runs: List[RunMetadata]) -> List[RunMetadata]:
    """Returns running runs that have been live for at least ITERATION_HOURS."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=ITERATION_HOURS)
    return [
        r for r in runs
        if r.status == RunStatus.running and r.started_at <= cutoff
    ]


def load_state() -> BmlState:
    if not STATE_FILE.exists():
        return BmlState()
    return BmlState.model_validate(json.loads(STATE_FILE.read_text()))


def save_state(state: BmlState) -> None:
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state.model_dump(mode="json"), indent=2))
