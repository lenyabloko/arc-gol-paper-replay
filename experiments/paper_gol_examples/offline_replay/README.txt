Offline replay of the paper's generated GOL examples

From the repository root, with Python3.12 and dependencies installed:
  python experiments/paper_gol_examples/offline_replay/run.py --out <new-output-directory>

requirements.txt records the dependency versions. Replay makes no LLM or network calls. The runner refuses an existing output directory, verifies the unchanged bundled runtime/checker manifest, and verifies all selected program/store/case inputs against INPUT_MANIFEST.json.

Nine replay groups:
- diagonal and downward: two original graph-assisted programs, empty store, three demonstrations each;
- stored_definition: first acquired action with its original one-definition store;
- stored_diagonal: second acquired action with the cumulative two-definition store;
- preserved_support: first action with that cumulative store;
- family32: original downward program,32 fixed synthetic cases;
- stored_family32: acquired downward action on the same32 cases;
- original_test_downward and original_test_diagonal: one original public task test example each, already scored after prediction freeze in the separate acquisition test record.

Each group executes twice in fresh processes. Checks compare exact outputs, graph/mirror consistency and semantic traces. Source-path manifests are preserved but excluded from semantic equality. Each job restores its own input data; synthetic cases cannot spill into another group's demonstration population.

The original test examples are now published replay fixtures with expected outputs. Replaying them is not a new held-out test or repeated acquisition. These and the repeated family/support checks are overlapping evidence, never independent tasks or new ARC accuracy. No historical large learned store or model credentials are included. The only stored knowledge used here is the explicitly selected one- or two-definition acquired study store. Runtime and checker code remain unchanged. Preserve the MIT notice and bundled source notices.

See VERIFIED_RESULT.json for the complete measured replay receipt. This command checks reproducibility of execution; it does not rerun model readings, historical search, or ARC2 applicability search.

Cross-platform check: all nine groups also passed twice in a fresh WSL/Linux Python3.12.14 environment, from public commit599891c. Expanded programs and semantic traces matched Windows for every group. WINDOWS_LINUX_REPLAY.json records this same-implementation portability check. It is not cross-consumer transfer.
