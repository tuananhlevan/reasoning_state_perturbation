# Claim mutation pipeline

The codebase contains four scripts:

- `src/authenticate.py` — load and refresh Google OAuth credentials from `.env`.
- `src/download.py` — recursively discover Drive archives and download one file.
- `src/mutate.py` — orchestrate each complete file lifecycle and run workers.
- `src/delete.py` — safely delete one worker's local temporary directory.

## Configuration

```dotenv
FPT_API_KEY=...
GDRIVE_CREDENTIALS_JSON={...}
GDRIVE_TOKEN_JSON={...}
FPT_MODEL=Qwen3.6-27B
```

`GDRIVE_TOKEN_JSON` must include a refresh token. Authentication and refresh are then non-interactive; no token file is written.

## Run

Validate authentication once:

```bash
python3 src/authenticate.py
```

Run the pipeline sequentially:

```bash
python3 src/mutate.py \
  'https://drive.google.com/drive/folders/SOURCE_FOLDER_ID' \
  'https://drive.google.com/drive/folders/OUTPUT_FOLDER_ID' \
  --workers 1
```

For every pending Drive archive, this performs:

```text
download one file -> extract -> mutate at most one figure-referencing claim
-> preserve the remaining claims -> build one local ZIP -> optionally upload it
```

Use multiple independent processes to handle several files concurrently:

```bash
python3 src/mutate.py SOURCE_FOLDER_ID OUTPUT_FOLDER_ID --workers 4
```

Each worker still processes its assigned file sequentially. All workers merge
their results into `outputs/dataset.jsonl` and `outputs/ref/` by default. Use
`--output-dir PATH` to change that shared dataset location. ZIPs are created only
in a temporary worker directory for optional upload and are deleted together with
all downloaded and extracted inputs when processing completes.

Drive upload is enabled by default. Disable it while retaining the shared local
dataset and references:

```bash
python3 src/mutate.py SOURCE_FOLDER_ID --no-upload
```

The shell launcher accepts `UPLOAD=0 ./mutate.sh` for the same behavior.

To run locally from `.target_cache` without authenticating to, listing, or reading
the source Drive folder, use:

```bash
python3 src/mutate.py --use-cache --no-upload
```

For uploads, the sole positional folder is treated as the destination:

```bash
python3 src/mutate.py OUTPUT_FOLDER_ID --use-cache
```

Combine it with `--target-cache PATH` to use another cache directory. Every cache directory is processed directly, regardless of old file checkpoints. Cache
directory names are used as source keys. A missing or invalid cached target fails
that item; `--use-cache` never downloads or rebuilds it.

To fill all currently missing or invalid caches without running mutation, use:

```bash
python3 src/mutate.py SOURCE_FOLDER_ID --fill-missing-cache --workers 8
```

This mode lists every supported archive in the source Drive, ignores terminal
mutation checkpoints, skips valid caches and archives already proven ineligible,
prepares everything else under `.target_cache`, and exits. It does not require an
output folder or `FPT_API_KEY`.

Every lifecycle emits flushed logs when the file enters the queue, when a worker removes it from the queue, and when processing completes. Each log includes the Drive file ID, filename, worker PID, and final status.

The startup log reports `files_at_once`, which is `min(--workers, pending files)`. Queue admission is bounded: with one worker, the next `queue-enter` appears only after the current file completes; with N workers, at most N files have entered at once.

## Output artifacts

Each source archive produces one similarly named ZIP (`input.zip` -> `input.zip`,
`input.tar.gz` -> `input.zip`) containing:

```text
dataset.jsonl
ref/<paper>/<referenced figure files>
```

`dataset.jsonl` contains only successful inconsistency pairs. For each referenced
figure, the selected original claim and its mutated counterpart are adjacent. The
original is labeled `entailed`; the mutation is labeled `refuted`. Every line has
exactly this schema:

```json
{"claim":"...","fig":"ref/paper/figure.png","difficulty":"Hard","label":"entailed"}
```

The model response also includes a required concise `reasoning` field, retained in the job checkpoint for auditing but intentionally omitted from final dataset rows so their four-field schema remains stable.

`label` is either `entailed` or `refuted`, and `difficulty` is one of `Easy`,
`Medium`, `Hard`, or `Very hard`. Without `--difficulty`, each claim independently
receives a uniform random choice across all four levels. Passing `--difficulty`
uses that fixed level for every claim. Claims with multiple figures produce one pair
per figure.

Only a claim explicitly containing `Fig`, `Figure`, or `Figures` is eligible to be
the single mutation target. If mutation fails, that target is omitted from the
JSONL; it is not logged as an original or uploaded claim.

The mutation target is chosen uniformly at random from all eligible claims in the
source archive; it is not biased toward the first paper, asset, or context.

Runs have two strict phases. First, every pending source archive is downloaded,
scanned, and assigned one random eligible claim; the claim and only its referenced
images are saved under `.target_cache/<source_key>/`, and all downloaded/extracted
data is deleted. Only after caching finishes for every file does the mutation
phase begin. Mutation workers read cache entries only and never download or
reselect targets. The cached target remains pinned for that immutable source
version; delete its cache directory to force a fresh random selection. Use
`--target-cache PATH` to change the cache location.

`--timeout` controls the model API read timeout. `--drive-timeout` independently
controls Google Drive listing, download, and upload socket operations; both default
to 120 seconds. Every cache attempt emits `cache-start` before network access, so
the currently active file is always visible in logs.

Uploads are idempotent per source file version: retrying after an interrupted
upload replaces the matching Drive artifact instead of creating another copy.
Artifact layout versions are stored in Drive metadata. At startup, the destination
folder is swept recursively for outputs using the current layout version and
source-version keys. An input is skipped only when its corresponding current-layout
output ZIP is present, so the destination Drive acts as the durable checkpoint.

## Checkpoints

- `.checkpoints/files/<file-version>.json` records successful dataset metadata and, when enabled, upload metadata. In upload mode Drive is authoritative; in local-only mode the checkpoint prevents repeated processing.
- `.checkpoints/jobs/<job>.json` remains local and marks one reference context complete. If a file failed halfway through or its remote output was deleted, successful mutations are reused while rebuilding the ZIP.
- Checkpoints are written atomically. Errors and dry runs do not receive successful checkpoints.
- A changed Drive version produces a different file key and is processed again.

Each immutable source-file version is attempted only once. Success, skipped
mutation, and processing/upload failure checkpoints are all terminal; later runs
do not retry them automatically. A changed source-file version has a new key and
is eligible for one new attempt.

Temporary data is created under `.work/` and deleted in a `finally` block after every file, whether it succeeds or fails. `src/delete.py` is also available for manual cleanup of an interrupted worker directory.

Use `--dry-run` to download, extract, validate, and delete inputs without calling FPT or writing successful checkpoints.

## Dataset Decontamination and Similarity Filtering

`filter_dataset.py` (and `src/filter_dataset.py`) decontaminates `outputs/dataset.jsonl` by comparing against benchmark datasets in `related_data` (`SciVer` and `MuSciClaims`) and removing similar/overlapping entries based on:

1. **Same Paper**: Matching arXiv IDs, paper IDs, DOIs, or normalized paper titles.
2. **Similar Context**: Comparing context text, figure captions, and section paragraphs.
3. **Semantic Claim Similarity**: Sentence embedding cosine similarity threshold $\ge 0.85$ using FPT API embedding model (e.g. `multilingual-e5-large`).

Run decontamination:

```bash
python3 filter_dataset.py \
  --dataset outputs/dataset.jsonl \
  --output outputs/dataset_filtered.jsonl \
  --removed-output outputs/dataset_removed.jsonl \
  --claim-threshold 0.85 \
  --model multilingual-e5-large \
  --workers 8
```

Options:
- `--claim-threshold`: Cosine similarity threshold for claims (default: `0.85`).
- `--context-threshold`: Similarity threshold for contexts (default: `0.85`).
- `--model`: FPT embedding model name (default: `multilingual-e5-large`).
- `--remove-pairs`: Keep/remove entailed-refuted pairs together (default: `True`).
- `--in-place`: Replace `outputs/dataset.jsonl` with filtered dataset (creates timestamped backup).
- `--dry-run`: Evaluate similarity without writing output files.

