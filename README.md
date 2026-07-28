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
download one file -> extract -> mutate all reference_context jobs
-> build and upload one output ZIP -> write the file checkpoint
```

Use multiple independent processes to handle several files concurrently:

```bash
python3 src/mutate.py SOURCE_FOLDER_ID OUTPUT_FOLDER_ID --workers 4
```

Each worker still processes its assigned file sequentially. It creates the output
only in its temporary work directory, uploads it to the destination Drive folder,
and then removes the temporary directory. No aggregate local `mutations.jsonl` is
written.

Every lifecycle emits flushed logs when the file enters the queue, when a worker removes it from the queue, and when processing completes. Each log includes the Drive file ID, filename, worker PID, and final status.

The startup log reports `files_at_once`, which is `min(--workers, pending files)`. Queue admission is bounded: with one worker, the next `queue-enter` appears only after the current file completes; with N workers, at most N files have entered at once.

## Output artifacts

Each source archive produces one similarly named ZIP (`input.zip` -> `input.zip`,
`input.tar.gz` -> `input.zip`) containing:

```text
mutations.jsonl
ref/<referenced figure files>
```

The `compiled_images` paths in each JSONL record point at the packaged files under
`ref/`. Only figures referenced by emitted claims are copied.

Uploads are idempotent per source file version: retrying after an interrupted
upload replaces the matching Drive artifact instead of creating another copy.
Artifact layout versions are stored in Drive metadata. At startup, the destination
folder is swept recursively for outputs using the current layout version and
source-version keys. An input is skipped only when its corresponding current-layout
output ZIP is present, so the destination Drive acts as the durable checkpoint.

## Checkpoints

- `outputs/checkpoints/files/<file-version>.json` records successful upload metadata locally for auditing. Destination Drive is authoritative: if its output ZIP is deleted, the input is processed again even if this local file exists.
- `outputs/checkpoints/jobs/<job>.json` remains local and marks one reference context complete. If a file failed halfway through or its remote output was deleted, successful mutations are reused while rebuilding the ZIP.
- Checkpoints are written atomically. Errors and dry runs do not receive successful checkpoints.
- A changed Drive version produces a different file key and is processed again.

Temporary data is created under `.work/` and deleted in a `finally` block after every file, whether it succeeds or fails. `src/delete.py` is also available for manual cleanup of an interrupted worker directory.

Use `--dry-run` to download, extract, validate, and delete inputs without calling FPT or writing successful checkpoints.
