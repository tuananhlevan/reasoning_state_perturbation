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
python3 src/mutate.py 'https://drive.google.com/drive/folders/FOLDER_ID' --workers 1
```

For every pending Drive archive, this performs:

```text
download one file -> extract -> mutate all reference_context jobs
-> write checkpoints -> delete its local data -> select the next file
```

Use multiple independent processes to handle several files concurrently:

```bash
python3 src/mutate.py 'https://drive.google.com/drive/folders/FOLDER_ID' --workers 4
```

Each worker still processes its assigned file sequentially. Model results are returned to the parent process, which immediately appends each completed file batch to `outputs/mutations.jsonl`, avoiding concurrent output writes and preserving completed results during long runs.

Every lifecycle emits flushed logs when the file enters the queue, when a worker removes it from the queue, and when processing completes. Each log includes the Drive file ID, filename, worker PID, and final status.

The startup log reports `files_at_once`, which is `min(--workers, pending files)`. Queue admission is bounded: with one worker, the next `queue-enter` appears only after the current file completes; with N workers, at most N files have entered at once.

## Checkpoints

- `outputs/checkpoints/files/<file-version>.json` marks an entire Drive file complete. The folder scan does not download it again.
- `outputs/checkpoints/jobs/<job>.json` marks one reference context complete. If a file previously failed halfway through, its successful jobs are skipped after it is downloaded again.
- Checkpoints are written atomically. Errors and dry runs do not receive successful checkpoints.
- A changed Drive version produces a different file key and is processed again.

Temporary data is created under `.work/` and deleted in a `finally` block after every file, whether it succeeds or fails. `src/delete.py` is also available for manual cleanup of an interrupted worker directory.

Use `--dry-run` to download, extract, validate, and delete inputs without calling FPT or writing successful checkpoints.
