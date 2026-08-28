#!/usr/bin/env python3
"""Download, mutate, package, upload, and checkpoint each Drive archive."""
from __future__ import annotations
import random
import argparse, fcntl, hashlib, json, filecmp, os, re, shutil, tarfile, tempfile, zipfile
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
import requests
import delete as cleanup
import download as drive
from authenticate import load_env

IMAGE_TYPES = {".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".png":"image/png", ".webp":"image/webp"}
FIGURE_REFERENCE = re.compile(r"\bfig(?:ure)?s?\b", re.IGNORECASE)
DEFAULT_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "claim_text_fig.md"
MODEL_RESPONSE_ATTEMPTS = 3
CACHE_SCAN_FORMAT = 2
DIFFICULTIES = ("Easy", "Medium", "Hard")

def choose_difficulty(requested=None):
    return requested or random.choice(DIFFICULTIES)

def source_key(item):
    return item.get("source_key") or drive.item_key(item)

def cached_items(cache_root):
    """Create pending work items directly from cache directory names."""
    entries = sorted(path for path in cache_root.iterdir() if path.is_dir()) if cache_root.is_dir() else []
    items = [{"id":entry.name, "name":f"{entry.name}.zip", "source_key":entry.name} for entry in entries]
    return items, len(entries)

def log_file(event, item, detail=""):
    suffix = f" {detail}" if detail else ""
    print(f"[file:{event}] id={item['id']} name={json.dumps(item['name'])} pid={os.getpid()}{suffix}", flush=True)

def safe_path(root, relative):
    path, base = (root / relative).resolve(), root.resolve()
    if path != base and base not in path.parents: raise ValueError(f"Path escapes input root: {relative}")
    return path

def extract(bundle, target):
    target.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(bundle):
        with zipfile.ZipFile(bundle) as archive:
            for member in archive.infolist(): safe_path(target, member.filename)
            archive.extractall(target)
        return
    if tarfile.is_tarfile(bundle):
        with tarfile.open(bundle) as archive:
            for member in archive.getmembers():
                safe_path(target, member.name)
                if member.issym() or member.islnk(): raise ValueError(f"Archive links unsupported: {member.name}")
            archive.extractall(target)
        return
    raise ValueError("Drive file is not a supported ZIP/tar archive")

def paper_root(extracted):
    direct = extracted / "test"
    if direct.is_dir():
        return extracted if any(direct.glob("*.json")) else direct
    nested = [path for path in extracted.glob("*/test") if path.is_dir()]
    if len(nested) == 1:
        return nested[0].parent if any(nested[0].glob("*.json")) else nested[0]
    return extracted

def list_value(value):
    if isinstance(value, str): return [value]
    return value if isinstance(value, list) else []

def resolve_asset_images(paper, asset):
    raw_paths = list_value(asset.get("compiled_images")) + list_value(asset.get("includegraphics_paths"))
    resolved = []
    for raw in raw_paths:
        if not isinstance(raw, str) or not raw.strip(): continue
        relative = Path(raw.strip().lstrip("/"))
        variants = [relative]
        if not relative.suffix:
            variants.extend(relative.with_suffix(extension) for extension in IMAGE_TYPES)
        matches = []
        for variant in variants:
            try: candidate = safe_path(paper, variant)
            except ValueError: continue
            if candidate.is_file() and candidate.suffix.lower() in IMAGE_TYPES: matches.append(candidate)
        if not matches:
            names = {variant.name for variant in variants}
            matches = [path for path in paper.rglob("*") if path.is_file() and path.name in names and path.suffix.lower() in IMAGE_TYPES]
        for match in matches:
            if match not in resolved: resolved.append(match)
    return resolved

def jobs(root):
    found, skipped = [], []
    paper_dirs = [root] if list(root.glob("*.json")) else [path for path in root.iterdir() if path.is_dir()]
    for paper in sorted(paper_dirs):
        for metadata in sorted(paper.glob("*.json")):
            try: assets = json.loads(metadata.read_text(encoding="utf-8")).get("assets", [])
            except (OSError, json.JSONDecodeError) as exc: skipped.append({"paper":paper.name,"metadata_file":metadata.name,"reason":str(exc)}); continue
            for asset_index, asset in enumerate(assets if isinstance(assets, list) else []):
                contexts = list_value(asset.get("reference_context"))
                for context_index, context in enumerate(contexts if isinstance(contexts, list) else []):
                    if not isinstance(context, str) or not context.strip(): continue
                    try:
                        resolved = resolve_asset_images(paper, asset)
                        if not resolved: raise ValueError("No usable image in compiled_images or includegraphics_paths")
                        found.append({"paper":paper.name,"metadata_file":metadata.name,"asset_index":asset_index,"context_index":context_index,"reference_context":context.strip(),"figure_referenced":bool(FIGURE_REFERENCE.search(context)),"compiled_images":[str(path.relative_to(paper.resolve())) for path in resolved]})
                    except ValueError as exc: skipped.append({"paper":paper.name,"asset_index":asset_index,"context_index":context_index,"reason":str(exc)})
    return found, skipped

def load_target_cache(entry):
    try:
        job = json.loads((entry / "target.json").read_text(encoding="utf-8"))
        content = entry / "content"
        if not isinstance(job, dict) or not job.get("figure_referenced"): return None
        images = job.get("compiled_images")
        if not isinstance(images, list) or not images: return None
        if any(not safe_path(content / job["paper"], image).is_file() for image in images): return None
        return job, content
    except (OSError, ValueError, KeyError, json.JSONDecodeError, TypeError): return None

def cache_target(root, job, entry):
    """Persist the selected target and its images before any mutation attempt."""
    content = entry / "content"
    for image in job["compiled_images"]:
        source = safe_path(root / job["paper"], image)
        destination = safe_path(content / job["paper"], image)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    save(entry / "target.json", job)
    return job, content

def prepare_target(item, config):
    """Cache one randomly selected target; never call the mutation model."""
    log_file("cache-start", item)
    load_env(Path(config["env"])); key = source_key(item); entry = Path(config["target_cache"]) / key
    if load_target_cache(entry):
        log_file("cache-hit", item)
        return True
    temp_root = Path(config["temp_root"]); work = Path(tempfile.mkdtemp(prefix=f"cache-{key[:10]}-", dir=temp_root))
    file_cp = Path(config["checkpoints"]) / "files" / f"{key}.json"
    try:
        bundle, extracted = work / "download.archive", work / "extracted"
        drive.download_file(item, bundle); extract(bundle, extracted); root = paper_root(extracted); file_jobs, skipped = jobs(root)
        eligible_jobs = [job for job in file_jobs if job["figure_referenced"]]
        if not eligible_jobs:
            reason_counts = {}
            for skipped_job in skipped:
                reason = skipped_job.get("reason", "Unknown")
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            save(file_cp,{"status":"skipped","format_version":drive.ARTIFACT_VERSION,"cache_scan_format":CACHE_SCAN_FORMAT,"drive_file":item,"claim_count":0,"reason":"No eligible figure-referencing claim","scan_summary":{"jobs_found":len(file_jobs),"jobs_eligible":0,"rejections":reason_counts}})
            return False
        cache_target(root, random.choice(eligible_jobs), entry)
        log_file("cached", item)
        return True
    except Exception as exc:
        try: save(file_cp,{"status":"failed","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"error":str(exc)})
        except Exception: pass
        log_file("cache-error", item, f"error={json.dumps(str(exc))}")
        return False
    finally:
        cleanup.delete_workdir(work,temp_root)

def prepare_items(items, config, workers):
    if workers == 1:
        return [item for item in items if prepare_target(item, config)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(prepare_target, item, config):item for item in items}
        prepared = []
        for future, item in futures.items():
            try:
                if future.result(): prepared.append(item)
            except Exception as exc:
                log_file("cache-error", item, f"error={json.dumps(str(exc))}")
        return prepared

def known_ineligible(path):
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return record.get("cache_scan_format") == CACHE_SCAN_FORMAT and record.get("reason") == "No eligible figure-referencing claim"
    except (OSError, json.JSONDecodeError, AttributeError):
        return False

def parse_model_content(raw):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Model returned empty content")
    text = raw.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.IGNORECASE | re.DOTALL)
    if fenced: text = fenced.group(1).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError as first_error:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try: result = json.loads(text[start:end + 1])
            except json.JSONDecodeError: result = None
        else:
            result = None
        if result is None:
            preview = " ".join(text[:200].splitlines())
            raise ValueError(f"Model returned invalid JSON: {preview!r}") from first_error
    if not isinstance(result, dict): raise ValueError("Model response is not a JSON object")
    return result

def invoke(prompt, config):
    content = [{"type":"text","text":prompt}]
    parse_error = None
    for attempt in range(1, MODEL_RESPONSE_ATTEMPTS + 1):
        response = requests.post(config["endpoint"], headers={"Authorization":f"Bearer {config['api_key']}","Content-Type":"application/json"}, json={"model":config["model"],"messages":[{"role":"user","content":content}],"temperature":0,"stream":False}, timeout=config["timeout"])
        response.raise_for_status(); raw = response.json()["choices"][0]["message"].get("content")
        try: return parse_model_content(raw)
        except ValueError as exc:
            parse_error = exc
            if attempt < MODEL_RESPONSE_ATTEMPTS: continue
    raise ValueError(f"{parse_error} after {MODEL_RESPONSE_ATTEMPTS} attempts")

def successful(path):
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return record.get("status") == "success" and has_mutation(record)
    except (OSError, json.JSONDecodeError, AttributeError): return False

def has_mutation(record):
    mutation = record.get("mutation")
    return (
        isinstance(mutation, dict)
        and set(mutation) == {"entailed_claim", "claim", "reasoning", "difficulty", "label"}
        and isinstance(mutation.get("claim"), str)
        and bool(mutation["claim"].strip())
        and isinstance(mutation.get("entailed_claim"), str)
        and bool(mutation["entailed_claim"].strip())
        and isinstance(mutation.get("reasoning"), str)
        and bool(mutation["reasoning"].strip())
        and mutation.get("difficulty") == record.get("difficulty")
        and mutation.get("label") == "refuted"
    )

def valid_output(record):
    return (
        isinstance(record, dict)
        and set(record) == {"context", "claim", "fig", "difficulty", "label"}
        and isinstance(record.get("context"), str)
        and bool(record["context"].strip())
        and isinstance(record.get("claim"), str)
        and bool(record["claim"].strip())
        and isinstance(record.get("fig"), str)
        and bool(record["fig"].strip())
        and record.get("difficulty") in {"Easy", "Medium", "Hard", "Very hard"}
        and record.get("label") in {"entailed", "refuted"}
    )

def save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(f".{os.getpid()}.tmp"); temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"); temporary.replace(path)

def append_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def output_name(name):
    lowered = name.lower()
    for suffix in sorted(drive.ARCHIVE_SUFFIXES, key=len, reverse=True):
        if lowered.endswith(suffix): return name[:-len(suffix)] + ".zip"
    return name + ".zip"

def build_artifact(path, root, records, source_key):
    """Build a ZIP containing validated claim/figure JSONL records."""
    staging = path.parent / "artifact"
    refs = staging / "ref"
    refs.mkdir(parents=True, exist_ok=True)
    packaged = []
    copied = {}
    for record in records:
        paper = record["paper"]
        images = record.get("compiled_images", [])
        if not images:
            continue
        relative = random.choice(images)
        source = safe_path(root / paper, relative)
        relative_path = Path(relative)
        parts = relative_path.parts
        if parts and parts[0].lower() == "ref": relative_path = Path(*parts[1:])
        destination = safe_path(refs, Path(paper) / relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination in copied:
            if not filecmp.cmp(source, copied[destination], shallow=False):
                raise ValueError(f"Conflicting referenced image path: {destination.relative_to(staging)}")
        else:
            shutil.copy2(source, destination)
            copied[destination] = source
        fig = destination.relative_to(staging).as_posix()
        pair = [
            {"context":record["reference_context"], "claim":record["mutation"]["entailed_claim"], "fig":fig, "difficulty":record["difficulty"], "label":"entailed"},
            {"context":record["reference_context"], "claim":record["mutation"]["claim"], "fig":fig, "difficulty":record["difficulty"], "label":"refuted"},
        ]
        if not all(valid_output(item) for item in pair):
            raise ValueError("Packaged record does not match the required output schema")
        packaged.extend(pair)
    append_records(staging / "dataset.jsonl", packaged)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in sorted(staging.rglob("*")):
            if entry.is_file(): archive.write(entry, entry.relative_to(staging))
    return packaged

def merge_dataset(staging, output_dir, source_key, records):
    """Idempotently merge validated records and paper-named reference folders."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = output_dir / "dataset.jsonl"
    with dataset.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.seek(0)
            existing_records = []
            for line in handle:
                try: existing = json.loads(line)
                except json.JSONDecodeError as exc: raise ValueError("Existing dataset contains invalid JSON") from exc
                if not valid_output(existing): raise ValueError("Existing dataset uses an incompatible output schema")
                existing_records.append(existing)
            if not all(valid_output(record) for record in records):
                raise ValueError("Records do not match the required output schema")
            new_records = [record for record in records if record not in existing_records]
            if not new_records: return False
            staged_refs = staging / "ref"
            if staged_refs.is_dir():
                for source in sorted(path for path in staged_refs.rglob("*") if path.is_file()):
                    destination = safe_path(output_dir / "ref", source.relative_to(staged_refs))
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if destination.exists():
                        if not filecmp.cmp(source, destination, shallow=False):
                            raise ValueError(f"Conflicting referenced image path: {destination.relative_to(output_dir)}")
                    else:
                        shutil.copy2(source, destination)
            handle.seek(0, os.SEEK_END)
            for record in new_records: handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush(); os.fsync(handle.fileno())
            return True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

def process_file(item, config):
    log_file("queue-exit", item, "worker-started")
    load_env(Path(config["env"])); key = source_key(item); file_cp = Path(config["checkpoints"]) / "files" / f"{key}.json"
    temp_root = Path(config["temp_root"]); work = Path(tempfile.mkdtemp(prefix=f"claim-{key[:10]}-", dir=temp_root)); records = []
    try:
        cache_entry = Path(config["target_cache"]) / key
        cached_target = load_target_cache(cache_entry)
        if not cached_target: raise RuntimeError("Prepared target cache is missing or invalid")
        mutation_target, root = cached_target
        log_file("cache-hit", item)
        template = Path(config["prompt"]).read_text(encoding="utf-8")
        if mutation_target:
            job = mutation_target
            difficulty = choose_difficulty(config["difficulty"])
            base = {"drive_file":item,**job,"difficulty":difficulty}
            material = "\0".join([key,job["paper"],job["metadata_file"],str(job["asset_index"]),str(job["context_index"]),job["reference_context"],difficulty,*job["compiled_images"]]); job_id = hashlib.sha256(material.encode()).hexdigest(); job_cp = Path(config["checkpoints"]) / "jobs" / f"{job_id}.json"; base["job_id"] = job_id
            if successful(job_cp):
                cached = json.loads(job_cp.read_text(encoding="utf-8"))
                records.append({**cached, "status":"checkpointed", "checkpoint_source":str(job_cp)})
            elif config["dry_run"]: records.append({"status":"dry_run",**base})
            else:
              try:
                prompt = template.replace("[TARGET_DIFFICULTY]",difficulty).replace("[INSERT TRUE STATEMENT]",job["reference_context"])
                raw_mutation = invoke(prompt,config)
                intermediate_dir = Path(config["output_dir"]) / "intermediate"
                intermediate_dir.mkdir(parents=True, exist_ok=True)
                with open(intermediate_dir / f"{job_id}.json", "w", encoding="utf-8") as f:
                    json.dump(raw_mutation, f, indent=2, ensure_ascii=False)
                processed_mutation = {
                    "entailed_claim": raw_mutation.get("entailed_claim", ""),
                    "claim": raw_mutation.get("counterfactual_claim", ""),
                    "reasoning": raw_mutation.get("why_it_is_false", ""),
                    "difficulty": raw_mutation.get("difficulty_rating", ""),
                    "label": "refuted"
                }
                record = {"status":"success",**base,"mutation":processed_mutation}
                if not has_mutation(record): raise ValueError("Model response does not match expected schema")
                save(job_cp,record)
              except Exception as exc:
                record={"status":"skipped",**base,"mutation_error":str(exc)}
                log_file("rejected", item, f"reason={json.dumps(str(exc))}")
              records.append(record)
        output_records = [record for record in records if has_mutation(record)]
        if output_records and not config["dry_run"]:
            artifact = work / output_name(item["name"])
            packaged = build_artifact(artifact, root, output_records, key)
            dataset = Path(config["output_dir"]) / "dataset.jsonl"
            merged = merge_dataset(work / "artifact", Path(config["output_dir"]), key, packaged)
            log_file("output", item, f"records={len(packaged)} dataset={json.dumps(str(dataset))} written={str(merged).lower()}")
            checkpoint = {"status":"success","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"claim_count":len(packaged),"local_output":str(dataset)}
            if config["upload"]: checkpoint["output_file"] = drive.upload_file(artifact, config["output_folder"], artifact.name, key)
            save(file_cp,checkpoint)
            records = packaged
        elif not config["dry_run"]:
            reason = next((record.get("mutation_error") for record in records if record.get("mutation_error")), "No successful mutation")
            save(file_cp,{"status":"skipped","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"claim_count":0,"reason":reason})
    except Exception as exc:
        records.append({"status":"error","drive_file":item,"error":str(exc)})
        try: save(file_cp,{"status":"failed","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"error":str(exc)})
        except Exception: pass
        log_file("error", item, f"error={json.dumps(str(exc))}")
    finally:
        cleanup.delete_workdir(work,temp_root)
        output_count = sum(valid_output(record) for record in records)
        if output_count:
            log_file("complete", item, f"status=success records={output_count}")
        elif any(record.get("status") == "error" for record in records):
            log_file("failed", item, "status=error records=0")
        elif config["dry_run"]:
            log_file("dry-run", item, "records=0")
        else:
            reason = next((record.get("mutation_error") for record in records if record.get("mutation_error")), "No successful mutation")
            log_file("skipped", item, f"status=skipped records=0 reason={json.dumps(reason)}")
    return records

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("folder",nargs="?",help="source Drive folder; with --use-cache and upload, the destination folder"); parser.add_argument("output_folder",nargs="?",help="destination Google Drive folder URL or ID (required with --upload)"); parser.add_argument("--workers",type=int,default=1); parser.add_argument("--temp-root",type=Path,default=Path(".work")); parser.add_argument("--checkpoint-dir",type=Path,default=Path(".checkpoints")); parser.add_argument("--target-cache",type=Path,default=Path(".target_cache")); parser.add_argument("--use-cache",action="store_true",help="run directly from --target-cache without reading the source folder"); parser.add_argument("--fill-missing-cache",action="store_true",help="prepare every missing Drive archive cache and exit"); parser.add_argument("--output-dir",type=Path,default=Path("outputs")); parser.add_argument("--prompt",type=Path,default=DEFAULT_PROMPT); parser.add_argument("--difficulty",choices=DIFFICULTIES,help="fixed difficulty; default is a uniform per-claim choice"); parser.add_argument("--model",default=None); parser.add_argument("--endpoint",default=None); parser.add_argument("--timeout",type=float,default=120,help="model API read timeout in seconds"); parser.add_argument("--drive-timeout",type=float,default=120,help="Google Drive socket timeout in seconds"); parser.add_argument("--env",type=Path,default=Path(".env")); parser.add_argument("--upload",action=argparse.BooleanOptionalAction,default=True); parser.add_argument("--dry-run",action="store_true"); args=parser.parse_args()
    if args.use_cache and args.fill_missing_cache: parser.error("--use-cache and --fill-missing-cache cannot be combined")
    if args.use_cache and args.upload and not args.output_folder:
        args.output_folder, args.folder = args.folder, None
    if not args.use_cache and not args.folder: parser.error("folder is required unless --use-cache is set")
    if args.workers < 1: parser.error("--workers must be at least 1")
    if args.timeout <= 0 or args.drive_timeout <= 0: parser.error("timeouts must be positive")
    if args.upload and not args.fill_missing_cache and not args.output_folder: parser.error("output_folder is required with --upload")
    load_env(args.env); os.environ["GDRIVE_TIMEOUT"] = str(args.drive_timeout); api_key=os.getenv("FPT_API_KEY")
    if not args.fill_missing_cache and not args.dry_run and not api_key: parser.error("FPT_API_KEY is missing")
    args.temp_root.mkdir(parents=True,exist_ok=True)
    completed_keys = None
    pending, scanned = (cached_items(args.target_cache) if args.use_cache else ([], 0))
    config={"env":str(args.env.resolve()),"temp_root":str(args.temp_root.resolve()),"checkpoints":str(args.checkpoint_dir.resolve()),"target_cache":str(args.target_cache.resolve()),"output_dir":str(args.output_dir.resolve()),"prompt":str(args.prompt.resolve()),"output_folder":args.output_folder,"upload":args.upload,"difficulty":args.difficulty,"model":args.model or os.getenv("FPT_MODEL","Qwen2.5-VL-7B-Instruct"),"endpoint":args.endpoint or (os.getenv("FPT_BASE_URL","").rstrip("/")+"/chat/completions" if os.getenv("FPT_BASE_URL") else "https://mkp-api.fptcloud.com/chat/completions"),"timeout":args.timeout,"dry_run":args.dry_run,"api_key":api_key}
    if args.fill_missing_cache:
        all_files = drive.list_files(drive.service(), drive.folder_id(args.folder))
        archives = [item for item in all_files if item["name"].lower().endswith(drive.ARCHIVE_SUFFIXES)]
        pending = []
        cached_count = ineligible_count = 0
        for item in archives:
            key = drive.item_key(item)
            entry = args.target_cache / key
            checkpoint = args.checkpoint_dir / "files" / f"{key}.json"
            if load_target_cache(entry): cached_count += 1
            elif known_ineligible(checkpoint): ineligible_count += 1
            else: pending.append(item)
        print(f"[fill-cache] archives={len(archives)} already_cached={cached_count} known_ineligible={ineligible_count} missing={len(pending)} workers={args.workers}", flush=True)
        prepared = prepare_items(pending, config, args.workers)
        print(f"[fill-cache:complete] attempted={len(pending)} cached={len(prepared)} unresolved={len(pending)-len(prepared)} target_cache={args.target_cache}", flush=True)
        return 0
    if not args.use_cache:
        completed_keys = drive.output_source_keys(args.output_folder) if args.upload else None
        pending, scanned = drive.discover(args.folder,args.checkpoint_dir,completed_keys)
    print(f"[pipeline] workers={args.workers} files_queued={len(pending)} files_at_once={min(args.workers, len(pending))} upload={args.upload} remote_completed={len(completed_keys or ())} output_dir={args.output_dir}", flush=True)
    if args.use_cache:
        print(f"[cache-phase] skipped=true source={args.target_cache} files={len(pending)}", flush=True)
    else:
        print(f"[cache-phase] files={len(pending)} workers={args.workers}", flush=True)
        pending = prepare_items(pending, config, args.workers)
    print(f"[mutation-phase] cached_files={len(pending)}; target preparation complete", flush=True)
    results=[]
    if args.workers == 1:
        for item in pending:
            log_file("queue-enter", item)
            batch = process_file(item,config); results.extend(batch)
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            iterator, futures = iter(pending), {}
            def submit_next():
                try: item = next(iterator)
                except StopIteration: return False
                log_file("queue-enter", item)
                futures[pool.submit(process_file,item,config)] = item
                return True
            for _ in range(args.workers):
                if not submit_next(): break
            while futures:
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    item = futures.pop(future)
                    try: batch = future.result()
                    except Exception as exc: batch = [{"status":"error","drive_file":item,"error":str(exc)}]
                    results.extend(batch)
                    submit_next()
    errors=sum(record.get("status")=="error" for record in results); rejected=sum(record.get("status")=="skipped" for record in results); outputs=sum(valid_output(record) for record in results); print(f"Scanned {scanned}; processed {len(pending)}; workers {args.workers}; output_records {outputs}; rejected {rejected}; errors {errors}."); return 1 if errors else 0
if __name__ == "__main__": raise SystemExit(main())
