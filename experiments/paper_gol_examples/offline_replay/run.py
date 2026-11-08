"""Replay the paper's frozen generated programs; no reader, learning, or network calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path,
                        help="New output directory; existing directories are never overwritten")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = read(HERE / "MANIFEST.json")["files"]
    for name, expected in manifest.items():
        actual = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError("Source checksum mismatch: " + name)
    runtime = out / "runtime"
    shutil.copytree(HERE / "runtime", runtime)
    store = out / "empty_store"
    store.mkdir()
    for name in ("defs.json", "constructs.json", "leaves.json"):
        (store / name).write_text("[]", encoding="utf-8")
    acquired_store = out / "acquired_store"
    acquired_store.mkdir()
    shutil.copyfile(EXAMPLES / "definition_acquisition_20261108/stored_defs.json",
                    acquired_store / "defs.json")
    for name in ("constructs.json", "leaves.json"):
        (acquired_store / name).write_text("[]", encoding="utf-8")
    cumulative_store = out / "cumulative_store"
    cumulative_store.mkdir()
    shutil.copyfile(EXAMPLES / "second_acquisition_20261108/stored_defs.json",
                    cumulative_store / "defs.json")
    for name in ("constructs.json", "leaves.json"):
        (cumulative_store / name).write_text("[]", encoding="utf-8")
    input_manifest = read(HERE / "INPUT_MANIFEST.json")["files"]
    for name, expected in input_manifest.items():
        if hashlib.sha256((EXAMPLES / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Example input checksum mismatch: " + name)
    jobs = [
        ("diagonal", "50c07299", "nbccg8", "modal_color",
         EXAMPLES / "reader_pilot_20261108/plan_B.json", None),
        ("downward", "d037b0a7", "mcccg8", "corner_supported",
         EXAMPLES / "reader_second_task_20261108/plan_B.json", None),
        ("stored_definition", "d037b0a7", "mcccg8", "corner_supported",
         EXAMPLES / "definition_acquisition_20261108/stored_program.json", None),
        ("stored_diagonal", "50c07299", "nbccg8", "modal_color",
         EXAMPLES / "second_acquisition_20261108/stored_program.json", None),
        ("preserved_support", "d037b0a7", "mcccg8", "corner_supported",
         EXAMPLES / "definition_acquisition_20261108/stored_program.json", None),
        ("stored_family32", "d037b0a7", "mcccg8", "corner_supported",
         EXAMPLES / "definition_acquisition_20261108/stored_program.json",
         EXAMPLES / "downward_generalization_20261108/cases.json"),
        ("original_test_downward", "d037b0a7", "mcccg8", "corner_supported",
         EXAMPLES / "definition_acquisition_20261108/stored_program.json",
         HERE / "public_test_replay/d037b0a7.json"),
        ("original_test_diagonal", "50c07299", "nbccg8", "modal_color",
         EXAMPLES / "second_acquisition_20261108/stored_program.json",
         HERE / "public_test_replay/50c07299.json"),
        ("family32", "d037b0a7", "mcccg8", "corner_supported",
         EXAMPLES / "downward_generalization_20261108/plan.json",
         EXAMPLES / "downward_generalization_20261108/cases.json"),
    ]
    env = os.environ.copy()
    env.update(TRACE_R7=str(runtime), STUDY_REGISTRY="original",
               PYTHONDONTWRITEBYTECODE="1")
    rows = []
    save(out / "RUN.json", {"status": "running", "jobs": [x[0] for x in jobs],
                             "seconds_per_process": 300, "replays_per_job": 2,
                             "python": sys.version, "source_files_verified": len(manifest)})
    for name, task, abstraction, background, plan, cases in jobs:
        # Restore each job's original input before optionally selecting a replay population.
        shutil.copyfile(cases or HERE / "runtime/data15b" / task / "task.json",
                        runtime / "data15b" / task / "task.json")
        data = read(runtime / "data15b" / task / "task.json")
        count = len(data["train"])
        seen = list(range(count)) if cases else list(range(count - 1))
        hidden = [] if cases else [count - 1]
        meta = dict(task=task, key=name, condition="B", order=1, seen=seen,
                    hidden=hidden, view=dict(abstraction=abstraction, background=background),
                    store_exec=str(acquired_store if name == "stored_definition" else
                                   store if name in ("diagonal", "downward", "family32") else cumulative_store))
        metap = out / (name + ".meta.json")
        save(metap, meta)
        traces, verdicts = [], []
        for repeat in (1, 2):
            dest = out / (name + "_" + str(repeat))
            cmd = [sys.executable, "-B", str(HERE / "checker/checker.py"),
                   str(metap), str(plan), str(dest)]
            with (out / (name + "_" + str(repeat) + ".log")).open("wb") as log:
                result = subprocess.run(cmd, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=300)
            if result.returncode:
                raise RuntimeError("Checker stopped; inspect " + name + " log")
            verdicts.append(read(dest / "verdict.json"))
            traces.append(read(dest / "trace.json"))
        v = verdicts[0]
        checks = list(v["seen"].values()) + list(v["hidden"].values())
        same = all(traces[0][k] == traces[1][k] for k in ("expanded_program", "demos"))
        row = dict(example=name, exact=sum(x["pass"] for x in checks), cases=count,
                   actions=v["arcgraph_equals_mirror"]["acts_checked"],
                   mismatches=v["arcgraph_equals_mirror"]["mismatches"],
                   semantic_replay_identical=same,
                   stored_definition_calls=sum(len(d.get("witnesses", [])) for d in traces[0]["demos"].values()),
                   program_sha256=hashlib.sha256(plan.read_bytes()).hexdigest(),
                   population_kind="original_test_replay" if name.startswith("original_test_") else
                                   "synthetic_family_replay" if "family32" in name else "demonstration_replay")
        rows.append(row)
        save(out / "SUMMARY.json", {"rows": rows, "scope": "Execution and within-family tests; not an ARC score"})
        print(json.dumps(row), flush=True)
    passed = all(r["exact"] == r["cases"] and not r["mismatches"] and
                 r["semantic_replay_identical"] for r in rows)
    save(out / "RESULT.json", {"passed": passed, "rows": rows,
                               "note": "Semantic traces omit only path-dependent source manifests when compared."})
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
