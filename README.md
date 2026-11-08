# Executable abstraction discovery: paper replay package

Public, limited reproducibility release for **Exploring the Kaleidoscope Hypothesis: Executable Abstraction Discovery in ARC-AGI-2**, by Len Yabloko.

This release contains the manuscript source, the required GOL/ARCGraph runtime and checker, two acquired definitions, and the public cases needed for nine replay groups. It does not include the private project repository or its full experiment history.

## Run the examples

Use Python 3.12. Install the versions in `experiments/paper_gol_examples/offline_replay/requirements.txt`, then run from this repository root:

```shell
python experiments/paper_gol_examples/offline_replay/run.py --out /path/to/new-output-directory
```

Choose a new output directory. Replay makes no LLM calls and requires no network access after dependencies are installed. See the [replay instructions](experiments/paper_gol_examples/offline_replay/README.txt) and [verified results](experiments/paper_gol_examples/offline_replay/VERIFIED_RESULT.json).

All nine groups passed twice in fresh processes in the recorded Windows run. Repeated demonstrations, family cases and already-scored public test examples are overlapping replay evidence, not additional independent ARC tasks. This command does not reproduce model acquisition, the historical search, or a benchmark evaluation.

## Paper and provenance

[Manuscript source](paper/edits/executable_understanding_position.tex). The manuscript contains links to additional project records that are not included in this limited release. `PACKAGE_MANIFEST.json` records the hashes of the approved original package files.

## Licenses

The manuscript states CC BY 4.0. Bundled code retains its [MIT notice](experiments/paper_gol_examples/offline_replay/LICENSE) and original source notices. Third-party dependencies retain their respective licenses. Public release does not change those rights.

## Evidence supplement

The separately approved [199-file evidence supplement](evidence/paper_evidence_supplement_v2.zip) adds the original and matched source-task reader records, synthetic and control-interpreter records, native caller-search results, and all three fixed-schedule cost passes. Its [SHA-256](evidence/paper_evidence_supplement_v2.sha256) is provided beside the archive.

Extract it into a new directory and run `python verify.py` there (Python 3.10 or newer; no dependencies). The verifier checks file hashes and recomputes counts, trace comparisons and paired costs from saved records. It does not call a model, execute GOL or remeasure speed; use the runtime command above for executable replay.

The archive is the exact reviewed snapshot, so its internal README retains the preparation-time release status. Publication was authorized on 8 November 2026. The later twenty-reader target-task study is not in this supplement. The archive includes its dataset attribution and Apache 2.0 notice; inherited source licenses are preserved.
