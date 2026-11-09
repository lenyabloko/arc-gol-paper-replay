# Exploring the Kaleidoscope Hypothesis
*Executable Abstraction Discovery in ARC-AGI-2*

Len Yabloko

## Research question

The kaleidoscope hypothesis proposes that diverse situations arise from compositions and transformations of a relatively small stock of abstractions. Even if such a stock exists, a learner must still discover its elements, recognize where they apply and learn how to combine them. We ask whether knowledge elicited from pretrained language models can be recovered as explicit, executable abstractions whose reuse improves subsequent task solving.

ARC tests whether a solver produces the correct output grid for a new input after seeing a few demonstrations. This assesses abstraction and reasoning: the solver must identify a transformation shared by the examples and apply it beyond them. ARC does not directly test whether the solver retains that transformation as reusable knowledge or whether it helps solve later tasks. Our paper proposes an architecture and measurements for testing that additional capability.

## Approach: combining perceptual and linguistic priors

Our principle is to combine two sources of structure. ARGA's perceptual inductive bias turns a grid into candidate objects, properties and relations. This supplies explicit, human-designed assumptions about how a scene can be organized. The LLM brings a different resource: representations shaped by broad linguistic and cultural knowledge acquired during pretraining. We ask it to interpret the graph using those priors, connecting the particular objects in a task to more general ideas about relations, transformations and their composition.

The graph constrains interpretation by specifying what objects and relations are present under a candidate reading. The LLM supplies hypotheses about what those structures mean and how they explain the demonstrated change. We express the resulting interpretation in GOL, making it possible to check its effects and reuse its operations. The intended gain is to recover transferable structure already implicit in pretrained knowledge through a perceptually grounded, executable description.

This connects to the [Platonic Representation Hypothesis](https://arxiv.org/abs/2405.07987): different representational routes may capture common structure in the world. In [Balestriero and LeCun's JEPA study](https://arxiv.org/abs/2610.39302), suitable paired observations of a scene provide "good views" for learning aligned representations. Our proposed route combines a view structured by ARGA's human-designed perceptual bias with an interpretation elicited from the LLM's learned linguistic priors. Both investigations ask how shared structure can be recovered through different views; the means of obtaining and using those views differ.

We hypothesize that this pairing can make task-relevant structure easier to recover and express as reusable GOL abstractions. A derived graph is not an independent observation, and this pairing is not established to satisfy the JEPA theorem's good-view conditions. Its usefulness must therefore be tested through executable predictions and reuse across tasks. The complementary emphasis is on what recovered knowledge enables a solver to do, alongside the representational alignment examined by PRH studies.

## What is implemented, and what the research adds

The [submitted notebook](https://www.kaggle.com/code/lenyabloko/situation-lattice-for-arc-agi-2?scriptVersionId=358393778) implements the basic solving infrastructure on which this architectural proposal builds: object abstraction, task-local rule induction, deterministic execution and bounded composition over a frozen prior vocabulary. Object attributes and their conjunctions guide search; demonstrations constrain candidate transformations. Solving makes no LLM calls and does not change persistent knowledge between tasks.

The research adds acquisition and retention above that foundation: learning callable recognition and action constructs, selecting them through applicability conditions, and making them available for composition and reuse by later consumers. The notebook uses decision-list and whole-grid program representations; it does not contain the newly acquired GOL definitions or implement the complete dream–wake learning loop. The GOL prototypes test parts of that extension separately. This distinction separates the deployed infrastructure from the proposed learning architecture and its experimental support.

## How the architecture was tested

The experiments isolate acquisition, composition, preservation and portability on selected public training tasks and controlled scene variations. Grid-only and graph-assisted observations test the perception interface; empty and acquired stores separate access to observations from access to executable knowledge. Tests on tasks different from those used to acquire the actions examine whether a definition becomes a building block for another solution.

Graph-assisted readers generated diagonal-growth and column-filling programs that reproduced demonstrations withheld during construction. Separate acquisitions retained callable actions, and adding a second action preserved the first action's demonstrated behavior. Controlled changes to dimensions, colours and seed configurations tested the downward-extension action's scope. Comparisons with altered programs distinguished the intended transformation from fitting only the original examples.

A reader directly invoked the retained downward-extension action while constructing a cross on a different task. The resulting program reproduced the demonstrations and test output. The same task was also solved without the store, so this demonstrates executable cross-task reuse without establishing an accuracy advantage. Replacing identical bodies in other generated programs with calls to the definition exposed additional shared structure; this retrospective factoring differs from selecting a saved action during construction.

LLM-free caller search also incorporated an acquired action into a program. A separately implemented control interpreter preserved the behavior of unchanged definitions and callers while sharing perception and primitive operations. Together, these results support bounded instances of acquisition, persistence, composition and control-interface portability. They do not yet establish an accumulating vocabulary that improves solving across successive learning cycles.

The notebook's Kaggle public leaderboard score is **2.50**. It reports deployment of the frozen-prior infrastructure, not evaluation of the new GOL acquisition-and-reuse mechanism.

## What should be measured beyond task accuracy

The proposal is intended to make knowledge reusable, so evaluation must measure what survives acquisition and helps subsequent reasoning. Forward transfer compares later-task performance with and without acquired definitions. Retention measures preservation after store additions. Conversion yield measures how much of a reference LLM's target-task capability an LLM-free consumer can recover. External reuse asks whether definitions retain their meaning and usefulness in another consumer, including the cost of adapting its interfaces. Acquisition, retrieval, checking and search costs determine whether reuse is practically worthwhile.

These measures connect the architecture to its central objective: turning experience into knowledge that improves later solving. The completed experiments demonstrate parts of this connection. The next step is to establish its cumulative benefit on separate task families, then extend evaluation to interactive skill acquisition.

## Paper and reproducibility

[Read the paper](https://github.com/lenyabloko/arc-gol-paper-replay/blob/main/paper/paperARC.pdf). The [public repository](https://github.com/lenyabloko/arc-gol-paper-replay) contains the manuscript source, executable examples, replay instructions and evidence supplements.

The author used commercial LLMs to assist in conducting experiments and writing the paper. Designated wake execution and deterministic replay make no LLM calls. Manuscript: CC BY 4.0; source: MIT, with third-party notices preserved.

---

## Reproducibility package

This release contains the final manuscript PDF and source, the required GOL/ARCGraph runtime and checker, two acquired definitions, and the public cases needed for nine replay groups. It does not include the private project repository or its full experiment history.

### Run the examples

Use Python 3.12. Install the versions in `experiments/paper_gol_examples/offline_replay/requirements.txt`, then run from this repository root:

```shell
python experiments/paper_gol_examples/offline_replay/run.py --out /path/to/new-output-directory
```

Choose a new output directory. Replay makes no LLM calls and requires no network access after dependencies are installed. See the [replay instructions](experiments/paper_gol_examples/offline_replay/README.txt) and [verified results](experiments/paper_gol_examples/offline_replay/VERIFIED_RESULT.json).

All nine groups passed twice in fresh processes in the recorded Windows run. Repeated demonstrations, family cases and already-scored public test examples are overlapping replay evidence, not additional independent ARC tasks. This command does not reproduce model acquisition, the historical search, or a benchmark evaluation.

### Paper and provenance

[Read the current manuscript (PDF)](paper/paperARC.pdf) | [LaTeX source](paper/edits/executable_understanding_position.tex). The current PDF has 17 pages and includes the shortened abstract. The earlier `paper/finalARC.pdf` is retained as a previous version. [Manuscript checksums](paper/MANUSCRIPT_MANIFEST.json) identify these versions. `PACKAGE_MANIFEST.json` preserves the hashes of the approved original package files; it is not a manifest of subsequent manuscript revisions.

### Licenses

The manuscript states CC BY 4.0. Bundled code retains its [MIT notice](experiments/paper_gol_examples/offline_replay/LICENSE) and original source notices. Third-party dependencies retain their respective licenses. Public release does not change those rights.

### Evidence supplement

The separately approved [199-file evidence supplement](evidence/paper_evidence_supplement_v2.zip) adds the original and matched source-task reader records, synthetic and control-interpreter records, native caller-search results, and all three fixed-schedule cost passes. Its [SHA-256](evidence/paper_evidence_supplement_v2.sha256) is provided beside the archive.

Extract it into a new directory and run `python verify.py` there (Python 3.10 or newer; no dependencies). The verifier checks file hashes and recomputes counts, trace comparisons and paired costs from saved records. It does not call a model, execute GOL or remeasure speed; use the runtime command above for executable replay.

The archive is the exact reviewed snapshot, so its internal README retains the preparation-time release status. Publication was authorized on 8 November 2026. The later twenty-reader target-task study is not in this supplement. The archive includes its dataset attribution and Apache 2.0 notice; inherited source licenses are preserved.

### Target-study executable replay

The separately approved [426-file target-study supplement](evidence/paper_target_replay_supplement_v1.zip) contains all twenty saved target proposals, three exactly factored versions, the reader inputs, public training cases, and the unchanged ARCGraph/GOL runtime. Its [SHA-256](evidence/paper_target_replay_supplement_v1.sha256) identifies the exact approved archive.

Extract it into a new directory. With Python 3.12, install its `requirements.txt`, then run `python -B replay.py --out ../target_replay_results`, choosing a new output directory outside the extraction. No model calls are made. Fresh local execution reproduced every saved outcome and primitive trace, including the four original native rejections. It also verified the three exact expansion proofs; these factored proposals concern one target task, not three new task successes.

This replay checks executable behavior, not acquisition, beneficial retrieval or cumulative learning. The archive's internal README preserves its preparation-time approval status; publication was authorized on 8 November 2026. Public training data retain the included Apache 2.0 notice, and the runtime retains its MIT notice. The private competition solver payload is not included.

### Second-reader executable replay

The approved [327-file second-reader supplement](evidence/paper_second_reader_replay_supplement_v1.zip) preserves all twenty opportunities on the same five public training targets: nineteen saved responses and one timeout. The reader was Claude Opus 5.5. Prompts and images match the first-reader comparison; provider contexts differ, so this is not a controlled model ranking. The [SHA-256](evidence/paper_second_reader_replay_supplement_v1.sha256) identifies the exact approved archive.

Extract into a new directory, install its `requirements.txt` with Python 3.12, and run `python -B replay.py --out ../second_reader_results` with a new output directory outside the extraction. No model calls occur. Fresh local replay reproduced every recorded outcome and primitive trace, including native rejections. The timeout remains recorded and is not retried.

One generated cross-drawing program directly invokes a saved downward-extension action from a different task. Its three demonstration outputs and original test output are exact; native traces record nine state-changing saved calls across the demonstrations. This is one reuse case among ten store-enabled opportunities. The no-store condition also solves that task, so no general accuracy or search-cost advantage is established. All condition results remain in `SUMMARY.json`. The package excludes raw model reasoning, authentication and the private competition solver payload. Existing MIT and public-task Apache 2.0 notices are retained.
