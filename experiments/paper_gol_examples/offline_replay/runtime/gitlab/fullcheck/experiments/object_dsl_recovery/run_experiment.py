"""Externally supervised inference, fresh replay, then separate frozen scoring."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pins():
    paths = [HERE / "search.py", HERE / "object_queries.py", Path(__file__), ROOT / "ARCGraph.py", ROOT / "image.py",
             ROOT / "connectors/dsl_shadows.py", ROOT / "connectors/schema.py",
             ROOT / "ontology/dsl_schema.py", ROOT / "ontology/runtime_registry.py"]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def synth(args):
    from experiments.object_dsl_recovery.search import infer, execute, Limits
    from experiments.object_dsl_recovery.object_queries import QueryGap
    challenges = load(args.challenges)
    results, predictions, traces = {}, {}, {}
    for number, (provenance, challenge) in enumerate(sorted(challenges.items()), 1):
        # Neither the provenance ID nor test data enters program discovery.
        start = time.monotonic()
        found = infer(challenge["train"], Limits(evaluations=args.evaluations))
        predictions[provenance] = [None] * len(challenge["test"])
        case_traces = []
        program = found.get("program")
        found["test_dispositions"] = [{"status": "unattempted"} for _ in challenge["test"]]
        results[provenance] = found
        # Preserve a discovered program even if later application fails.
        save(args.out / "programs.json", results)
        if program is not None:
            for index, example in enumerate(challenge["train"] + challenge["test"]):
                outcomes = {}
                for backend in ("direct", "shadow"):
                    try:
                        outcomes[backend] = execute(example["input"], program, backend=backend, trace=True)
                    except QueryGap as error:
                        if index < len(challenge["train"]):
                            raise
                        outcomes[backend] = {"query_gap": str(error)}
                if any("query_gap" in value for value in outcomes.values()):
                    if outcomes["direct"] != outcomes["shadow"]:
                        raise AssertionError("query-gap disposition differs between interpreters")
                    gap = {"status": "unresolved_query_binding", **outcomes["direct"]}
                    found["test_dispositions"][index - len(challenge["train"])] = gap
                    case_traces.append(gap)
                    continue
                direct, shadow = outcomes["direct"], outcomes["shadow"]
                direct_states = [(t["objects"], t["grid"]) for t in direct["trace"]]
                shadow_states = [(t["objects"], t["grid"]) for t in shadow["trace"]]
                if direct_states != shadow_states:
                    raise AssertionError(f"intermediate interpreter mismatch at {provenance}:{index}")
                if index < len(challenge["train"]):
                    if shadow["grid"] != example["output"]:
                        raise AssertionError("discovered program does not fit training")
                else:
                    predictions[provenance][index - len(challenge["train"])] = shadow["grid"]
                    found["test_dispositions"][index - len(challenge["train"])] = {"status": "predicted"}
                case_traces.append(shadow["trace"])
            found["order_sensitive_on_training"] = len(program) > 1 and any(
                execute(pair["input"], list(reversed(program)))["grid"] != pair["output"]
                for pair in challenge["train"])
        else:
            found["test_dispositions"] = [{"status": "unresolved_no_program"} for _ in challenge["test"]]
        found["seconds"] = time.monotonic() - start
        results[provenance] = found
        traces[provenance] = case_traces
        # Preserve completed tasks if external supervision stops the fixed batch.
        save(args.out / "programs.json", results)
        save(args.out / "predictions.json", predictions)
        save(args.out / "traces.json", traces)
        print(json.dumps({"task": number, "of": len(challenges), "status": found["status"],
                          "evaluations": found.get("evaluations", 0),
                          "seconds": round(found["seconds"], 3)}), flush=True)
    save(args.out / "inference_closed.json", {
        "task_count": len(challenges), "test_slots": sum(len(t["test"]) for t in challenges.values()),
        "predictions_sha256": sha(args.out / "predictions.json"),
        "programs_sha256": sha(args.out / "programs.json"),
        "traces_sha256": sha(args.out / "traces.json"),
        "all_intermediate_parity_passed": True,
        "answers_read": False, "legacy_solver_invoked": False})


def instruction_guard(programs, challenges):
    from experiments.object_dsl_recovery.search import compile_program, shadow_step, abstract, FragmentGap
    sample = next(((key, p["program"]) for key, p in programs.items() if p.get("program")), None)
    if sample is None:
        return None
    key, program = sample
    bad_code = compile_program(program)["statements"][0]
    bad_code[-1]["implementation_digest"] = "tampered"
    # The canary needs an input inside this program's supported abstraction.
    # Resolve it before catching the intentionally tampered instruction error.
    graph = abstract(challenges[key]["train"][0]["input"])
    try:
        shadow_step(graph, bad_code)
    except FragmentGap as error:
        if str(error) == "stale_or_modified_instruction":
            return True
        raise
    raise AssertionError("modified shadow identity was not rejected")


def replay(args):
    from experiments.object_dsl_recovery.search import execute, compile_program
    from experiments.object_dsl_recovery.object_queries import QueryGap
    predictions, programs = load(args.out / "predictions.json"), load(args.out / "programs.json")
    replay_count = unresolved_replay_count = 0
    for key, challenge in sorted(load(args.challenges).items()):
        program = programs[key].get("program")
        if program is None:
            continue
        if compile_program(program) != programs[key]["compiled"]:
            raise AssertionError("persisted compilation changed")
        for index, example in enumerate(challenge["test"]):
            try:
                actual = execute(example["input"], program)["grid"]
            except QueryGap as error:
                disposition = programs[key]["test_dispositions"][index]
                if (predictions[key][index] is not None or
                        disposition != {"status": "unresolved_query_binding", "query_gap": str(error)}):
                    raise AssertionError("fresh replay query-gap disposition differs") from error
                unresolved_replay_count += 1
                continue
            if actual != predictions[key][index]:
                raise AssertionError("fresh process replay differs")
            replay_count += 1
    stale_rejected = instruction_guard(programs, load(args.challenges))
    save(args.out / "replay.json", {"fresh_process": True, "search_invoked": False,
                                   "answers_read": False, "cases_replayed": replay_count,
                                   "unresolved_cases_reproduced": unresolved_replay_count,
                                   "all_equal": True, "tampered_instruction_rejected": stale_rejected})


def score(args):
    # This is the first process allowed to open expected held-out outputs.
    predictions, programs = load(args.out / "predictions.json"), load(args.out / "programs.json")
    answers, closed = load(args.answers), load(args.out / "inference_closed.json")
    assert sha(args.out / "predictions.json") == closed["predictions_sha256"]
    correct = wrong = unresolved = 0
    rows = []
    for key, guesses in predictions.items():
        expected = answers.get(key)
        if expected is None or len(expected) != len(guesses):
            raise ValueError("answer population mismatch")
        for index, (guess, target) in enumerate(zip(guesses, expected)):
            status = "unresolved" if guess is None else "correct" if guess == target else "wrong"
            correct += status == "correct"
            wrong += status == "wrong"
            unresolved += status == "unresolved"
            rows.append({"provenance": key, "index": index, "status": status})
    multi = sum(len(p.get("program") or []) >= 2 for p in programs.values())
    ordered = sum(bool(p.get("order_sensitive_on_training")) for p in programs.values())
    result = {"correct": correct, "wrong": wrong, "unresolved": unresolved,
              "total": len(rows), "multistep_programs": multi, "order_sensitive_programs": ordered,
              "answers_sha256": sha(args.answers), "predictions_sha256": closed["predictions_sha256"],
              "cases": rows, "population": str(args.challenges),
              "authority_acceptance": False, "kaggle_success": False}
    if args.challenges.resolve() == (HERE / "fixtures/challenges.json").resolve():
        result["predeclared_pilot_passed"] = correct == 12 and wrong == 0 and unresolved == 0 and multi >= 2 and ordered >= 1
    save(args.out / "score.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "cases"}))


def supervise(args):
    args.out.mkdir(parents=True, exist_ok=False)
    before = source_pins()
    save(args.out / "start.json", {"sources": before, "challenges_sha256": sha(args.challenges),
                                  "external_seconds": args.seconds, "evaluations": args.evaluations})
    started = time.monotonic()
    stages = []
    for stage in ("synth", "replay", "score"):
        remaining = args.seconds - (time.monotonic() - started)
        cmd = [sys.executable, str(Path(__file__).resolve()), "--stage", stage,
               "--out", str(args.out), "--challenges", str(args.challenges),
               "--evaluations", str(args.evaluations)]
        if stage == "score":
            if args.answers is None:
                break
            cmd += ["--answers", str(args.answers)]
        try:
            with (args.out / f"{stage}.stdout.txt").open("w", encoding="utf-8") as stdout, \
                 (args.out / f"{stage}.stderr.txt").open("w", encoding="utf-8") as stderr:
                result = subprocess.run(cmd, cwd=ROOT, stdout=stdout, stderr=stderr,
                                        timeout=max(0.1, remaining))
            stages.append({"stage": stage, "exit_code": result.returncode})
        except subprocess.TimeoutExpired:
            stages.append({"stage": stage, "status": "timeout_unknown"})
            break
        if result.returncode != 0 or source_pins() != before:
            break
    final = {"stages": stages, "seconds": time.monotonic() - started,
             "sources_unchanged": source_pins() == before,
             "finished": len(stages) == 3 and all(s.get("exit_code") == 0 for s in stages)}
    save(args.out / "supervision.json", final)
    print(json.dumps({"out": str(args.out), **final}))
    if not final["finished"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("supervise", "synth", "replay", "score"), default="supervise")
    parser.add_argument("--out", type=Path, default=ROOT / "_goal_runs/object_dsl_recovery" /
                        datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%S_%fZ"))
    parser.add_argument("--challenges", type=Path, default=HERE / "fixtures/challenges.json")
    parser.add_argument("--answers", type=Path, default=HERE / "fixtures/answers.json")
    parser.add_argument("--seconds", type=int, default=180)
    parser.add_argument("--evaluations", type=int, default=256)
    args = parser.parse_args()
    {"supervise": supervise, "synth": synth, "replay": replay, "score": score}[args.stage](args)


if __name__ == "__main__":
    main()
