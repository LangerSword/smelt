"""Run state, append-only event stream, and hashing helpers.

state.json is the checkpoint: resume reads it, re-validates the oracle hash and the
target file hash, and continues from the last completed node. events.jsonl is the
single stream that the CLI prints today and the TUI (L4) will subscribe to later.
"""

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field

SMELT_VERSION = "0.1.0"

EVENT_SCHEMA_VERSION = "1"



def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(t: str) -> str:
    return sha256_bytes(t.encode())


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def new_run_id(target_path: str, qualname: str) -> str:
    stamp = time.strftime("%y%m%d-%H%M%S")
    salt = sha256_text(f"{target_path}:{qualname}:{time.time_ns()}")[:6]
    return f"{stamp}-{salt}"


@dataclass
class RunState:
    run_id: str
    created_at: str
    smelt_version: str
    target: dict  # {path, qualname, source_sha256}
    oracle: dict  # {dir, sha256, n_cases, seed}
    config: dict  # {provider, model, max_attempts, cases, bench_min_s}
    attempts: list = field(default_factory=list)
    status: str = "in_progress"  # in_progress | accepted | rejected | refused | error
    stop_reason: str = ""

    def save(self, run_dir: str) -> None:
        with open(os.path.join(run_dir, "state.json"), "w") as f:
            json.dump(asdict(self), f, indent=2)

    @staticmethod
    def load(run_dir: str) -> "RunState":
        with open(os.path.join(run_dir, "state.json")) as f:
            return RunState(**json.load(f))


class EventLog:
    """Append-only JSONL event stream (one record per state transition)."""

    def __init__(self, path: str):
        self.path = path

    def emit(self, event: str, node: str = "", **data) -> None:
        rec = {"ts": time.time(), "schema_version": EVENT_SCHEMA_VERSION,
               "event": event, "node": node}
        rec.update(data)
        with open(self.path, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
