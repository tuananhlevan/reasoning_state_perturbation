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

Every lifecycle emits flushed logs when the file enters the queue, when a worker removes it from the queue, and when processing completes. Each log includes the Drive file ID, filename, worker PID, and final status.

The startup log reports `files_at_once`, which is `min(--workers, pending files)`. Queue admission is bounded: with one worker, the next `queue-enter` appears only after the current file completes; with N workers, at most N files have entered at once.

## Output artifacts

Each source archive produces one similarly named ZIP (`input.zip` -> `input.zip`,
`input.tar.gz` -> `input.zip`) containing:

```text
mutations.jsonl
ref/<referenced figure files>
```

`dataset.jsonl` contains only successful inconsistency pairs. For each source
archive, the one selected original claim and its mutated counterpart are written
as adjacent records with the same source metadata and references. No unselected
original claims or their figures are retained.
Each line's `references` array points at its figure under
`ref/<source_key>/<paper>/`. A line has this shape:

```json
{"claim_type":"original","claim":"...","source_key":"...","paper":"...","metadata_file":"...","asset_index":0,"context_index":0,"references":["ref/source-key/paper/figure.png"]}
```

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
