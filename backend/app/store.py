"""In-memory run store {run_id: AnalysisResult}. Keeps the newest `max_runs` runs (default 20).

Runs are lost when the server restarts; the frontend then simply runs the analysis again.
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime

from backend.app.schemas import AnalysisResult
from backend.app.settings import get_settings


@dataclass
class StoredRun:
    result: AnalysisResult
    is_demo: bool  # demo runs may fall back to saved AMD reports (data/demo_reports/)
    created_at: datetime = field(default_factory=datetime.now)


class RunStore:
    def __init__(self, max_runs: int):
        self.max_runs = max(1, max_runs)
        self._runs: "OrderedDict[str, StoredRun]" = OrderedDict()
        self._lock = threading.Lock()

    def put(self, result: AnalysisResult, is_demo: bool) -> StoredRun:
        run = StoredRun(result=result, is_demo=is_demo)
        with self._lock:
            self._runs[result.run_id] = run
            self._runs.move_to_end(result.run_id)
            while len(self._runs) > self.max_runs:
                self._runs.popitem(last=False)
        return run

    def get(self, run_id: str) -> StoredRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def newest_first(self) -> list[StoredRun]:
        """All stored runs, newest first."""
        with self._lock:
            return list(reversed(self._runs.values()))

    def __len__(self) -> int:
        with self._lock:
            return len(self._runs)

    def clear(self) -> None:
        with self._lock:
            self._runs.clear()


runs = RunStore(get_settings().max_runs)
