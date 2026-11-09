# Executable abstraction discovery: paper replay package

Public, limited reproducibility release for **Exploring the Kaleidoscope Hypothesis: Executable Abstraction Discovery in ARC-AGI-2**, by Len Yabloko.

This release contains the final manuscript PDF and source, the required GOL/ARCGraph runtime and checker, two acquired definitions, and the public cases needed for nine replay groups. It does not include the private project repository or its full experiment history.

## Run the examples

Use Python 3.12. Install the versions in `experiments/paper_gol_examples/offline_replay/requirements.txt`, then run from this repository root:

```shell
python experiments/paper_gol_examples/offline_replay/run.py --out /path/to/new-output-directory
```

Choose a new output directory. Replay makes no LLM calls and requires no network access after dependencies are installed. See the [replay instructions](experiments/paper_gol_examples/offline_replay/README.txt) and [verified results](experiments/paper_gol_examples/offline_replay/VERIFIED_RESULT.json).

All nine groups passed twice in fresh processes in the recorded Windows run. Repeated demonstrations, family cases and already-scored public test examples are overlapping replay evidence, not additional independent ARC tasks. This command does not reproduce model acquisition, the historical search, or a benchmark evaluation.

## Paper and provenance

[Read the final manuscript (PDF)](paper/finalARC.pdf) | [LaTeX source](paper/edits/executable_understanding_position.tex). The 18-page PDF matches this source, including the final appendix revisions. [Manuscript checksums](paper/MANUSCRIPT_MANIFEST.json) identify these versions. `PACKAGE_MANIFEST.json` preserves the hashes of the approved original package files; it is not a manifest of subsequent manuscript revisions.

## Licenses

The manuscript states CC BY 4.0. Bundled code retains its [MIT notice](experiments/paper_gol_examples/offline_replay/LICENSE) and original source notices. Third-party dependencies retain their respective licenses. Public release does not change those rights.

## Evidence supplement

The separately approved [199-file evidence supplement](evidence/paper_evidence_supplement_v2.zip) adds the original and matched source-task reader records, synthetic and control-interpreter records, native caller-search results, and all three fixed-schedule cost passes. Its [SHA-256](evidence/paper_evidence_supplement_v2.sha256) is provided beside the archive.

Extract it into a new directory and run `python verify.py` there (Python 3.10 or newer; no dependencies). The verifier checks file hashes and recomputes counts, trace comparisons and paired costs from saved records. It does not call a model, execute GOL or remeasure speed; use the runtime command above for executable replay.

The archive is the exact reviewed snapshot, so its internal README retains the preparation-time release status. Publication was authorized on 8 November 2026. The later twenty-reader target-task study is not in this supplement. The archive includes its dataset attribution and Apache 2.0 notice; inherited source licenses are preserved.

## Target-study executable replay

The separately approved [426-file target-study supplement](evidence/paper_target_replay_supplement_v1.zip) contains all twenty saved target proposals, three exactly factored versions, the reader inputs, public training cases, and the unchanged ARCGraph/GOL runtime. Its [SHA-256](evidence/paper_target_replay_supplement_v1.sha256) identifies the exact approved archive.

Extract it into a new directory. With Python 3.12, install its `requirements.txt`, then run `python -B replay.py --out ../target_replay_results`, choosing a new output directory outside the extraction. No model calls are made. Fresh local execution reproduced every saved outcome and primitive trace, including the four original native rejections. It also verified the three exact expansion proofs; these factored proposals concern one target task, not three new task successes.

This replay checks executable behavior, not acquisition, beneficial retrieval or cumulative learning. The archive's internal README preserves its preparation-time approval status; publication was authorized on 8 November 2026. Public training data retain the included Apache 2.0 notice, and the runtime retains its MIT notice. The private competition solver payload is not included.

## Second-reader executable replay

The approved [327-file second-reader supplement](evidence/paper_second_reader_replay_supplement_v1.zip) preserves all twenty opportunities on the same five public training targets: nineteen saved responses and one timeout. The reader was Claude Opus 5.5. Prompts and images match the first-reader comparison; provider contexts differ, so this is not a controlled model ranking. The [SHA-256](evidence/paper_second_reader_replay_supplement_v1.sha256) identifies the exact approved archive.

Extract into a new directory, install its `requirements.txt` with Python 3.12, and run `python -B replay.py --out ../second_reader_results` with a new output directory outside the extraction. No model calls occur. Fresh local replay reproduced every recorded outcome and primitive trace, including native rejections. The timeout remains recorded and is not retried.

One generated cross-drawing program directly invokes a saved downward-extension action from a different task. Its three demonstration outputs and original test output are exact; native traces record nine state-changing saved calls across the demonstrations. This is one reuse case among ten store-enabled opportunities. The no-store condition also solves that task, so no general accuracy or search-cost advantage is established. All condition results remain in `SUMMARY.json`. The package excludes raw model reasoning, authentication and the private competition solver payload. Existing MIT and public-task Apache 2.0 notices are retained.
