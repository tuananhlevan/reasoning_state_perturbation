#!/usr/bin/env python3
"""Download, mutate, package, upload, and checkpoint each Drive archive."""
from __future__ import annotations
import random
import argparse, base64, fcntl, hashlib, json, filecmp, mimetypes, os, re, shutil, tarfile, tempfile, zipfile
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
import requests
import delete as cleanup
import download as drive
from authenticate import load_env

IMAGE_TYPES = {".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".png":"image/png", ".webp":"image/webp"}
FIGURE_REFERENCE = re.compile(r"\bfig(?:ure)?s?\b", re.IGNORECASE)

if random.randint(0, 1) < 0.33:
    DEFAULT_DIFFICULTY = "Easy"
elif random.randint(0, 1) < 0.66:
    DEFAULT_DIFFICULTY = "Medium"
else:
    DEFAULT_DIFFICULTY = "Hard"

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
    if (extracted / "test").is_dir(): return extracted / "test"
    nested = [path for path in extracted.glob("*/test") if path.is_dir()]
    return nested[0] if len(nested) == 1 else extracted

def jobs(root):
    found, skipped = [], []
    paper_dirs = [root] if list(root.glob("*.json")) else [path for path in root.iterdir() if path.is_dir()]
    for paper in sorted(paper_dirs):
        for metadata in sorted(paper.glob("*.json")):
            try: assets = json.loads(metadata.read_text(encoding="utf-8")).get("assets", [])
            except (OSError, json.JSONDecodeError) as exc: skipped.append({"paper":paper.name,"metadata_file":metadata.name,"reason":str(exc)}); continue
            for asset_index, asset in enumerate(assets if isinstance(assets, list) else []):
                contexts, images = asset.get("reference_context", []), asset.get("compiled_images", [])
                if isinstance(contexts, str): contexts = [contexts]
                if isinstance(images, str): images = [images]
                for context_index, context in enumerate(contexts if isinstance(contexts, list) else []):
                    if not isinstance(context, str) or not context.strip(): continue
                    try:
                        resolved = [safe_path(paper, str(image)) for image in images]
                        if not resolved or any(not path.is_file() or path.suffix.lower() not in IMAGE_TYPES for path in resolved): raise ValueError("Missing or unsupported compiled image")
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
    load_env(Path(config["env"])); key = drive.item_key(item); entry = Path(config["target_cache"]) / key
    if load_target_cache(entry):
        log_file("cache-hit", item)
        return True
    temp_root = Path(config["temp_root"]); work = Path(tempfile.mkdtemp(prefix=f"cache-{key[:10]}-", dir=temp_root))
    file_cp = Path(config["checkpoints"]) / "files" / f"{key}.json"
    try:
        bundle, extracted = work / "download.archive", work / "extracted"
        drive.download_file(item, bundle); extract(bundle, extracted); root = paper_root(extracted); file_jobs, _ = jobs(root)
        eligible_jobs = [job for job in file_jobs if job["figure_referenced"]]
        if not eligible_jobs:
            save(file_cp,{"status":"skipped","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"claim_count":0,"reason":"No eligible figure-referencing claim"})
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

def data_url(path):
    mime = IMAGE_TYPES.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"

def invoke(job, paper, prompt, config):
    content = [{"type":"text","text":prompt}]
    content += [{"type":"image_url","image_url":{"url":data_url(safe_path(paper, image))}} for image in job["compiled_images"]]
    response = requests.post(config["endpoint"], headers={"Authorization":f"Bearer {config['api_key']}","Content-Type":"application/json"}, json={"model":config["model"],"messages":[{"role":"user","content":content}],"temperature":0,"stream":False}, timeout=config["timeout"])
    response.raise_for_status(); raw = response.json()["choices"][0]["message"]["content"]
    result = json.loads(raw)
    if not isinstance(result, dict): raise ValueError("Model response is not a JSON object")
    return result

def successful(path):
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return record.get("status") == "success" and has_mutation(record)
    except (OSError, json.JSONDecodeError, AttributeError): return False

def has_mutation(record):
    mutation = record.get("mutation")
    return isinstance(mutation, dict) and isinstance(mutation.get("counterfactual_claim"), str) and bool(mutation["counterfactual_claim"].strip())

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
    """Build a ZIP containing one JSONL claim stream and its referenced figures."""
    staging = path.parent / "artifact"
    refs = staging / "ref"
    refs.mkdir(parents=True, exist_ok=True)
    packaged = []
    copied = {}
    for record in records:
        archived = {
            "source_key":source_key,
            "paper":record["paper"],
            "metadata_file":record["metadata_file"],
            "asset_index":record["asset_index"],
            "context_index":record["context_index"],
        }
        images = []
        paper = record.get("paper")
        for relative in record.get("compiled_images", []):
            source = safe_path(root / paper, relative)
            relative_path = Path(relative)
            parts = relative_path.parts
            if parts and parts[0].lower() == "ref": relative_path = Path(*parts[1:])
            destination = safe_path(refs, Path(source_key) / paper / relative_path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination in copied:
                if not filecmp.cmp(source, copied[destination], shallow=False):
                    raise ValueError(f"Conflicting referenced image path: {destination.relative_to(staging)}")
            else:
                shutil.copy2(source, destination)
                copied[destination] = source
            images.append(destination.relative_to(staging).as_posix())
        archived["references"] = images
        packaged.append({"claim_type":"original","claim":record["reference_context"],**archived})
        if has_mutation(record):
            packaged.append({"claim_type":"mutated","claim":record["mutation"]["counterfactual_claim"],**archived})
    append_records(staging / "dataset.jsonl", packaged)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in sorted(staging.rglob("*")):
            if entry.is_file(): archive.write(entry, entry.relative_to(staging))
    return packaged

def merge_dataset(staging, output_dir, source_key, records):
    """Idempotently merge one source into the shared dataset under a file lock."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset = output_dir / "dataset.jsonl"
    with dataset.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            handle.seek(0)
            for line in handle:
                try: existing = json.loads(line)
                except json.JSONDecodeError: continue
                if existing.get("source_key") == source_key: return False
            source_refs = staging / "ref" / source_key
            if source_refs.is_dir(): shutil.copytree(source_refs, output_dir / "ref" / source_key, dirs_exist_ok=True)
            handle.seek(0, os.SEEK_END)
            for record in records: handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush(); os.fsync(handle.fileno())
            return True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)

def process_file(item, config):
    log_file("queue-exit", item, "worker-started")
    load_env(Path(config["env"])); key = drive.item_key(item); file_cp = Path(config["checkpoints"]) / "files" / f"{key}.json"
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
            base = {"drive_file":item,**job,"difficulty":config["difficulty"]}
            material = "\0".join([key,job["paper"],job["metadata_file"],str(job["asset_index"]),str(job["context_index"]),job["reference_context"],*job["compiled_images"]]); job_id = hashlib.sha256(material.encode()).hexdigest(); job_cp = Path(config["checkpoints"]) / "jobs" / f"{job_id}.json"; base["job_id"] = job_id
            if successful(job_cp):
                cached = json.loads(job_cp.read_text(encoding="utf-8"))
                records.append({**cached, "status":"checkpointed", "checkpoint_source":str(job_cp)})
            elif config["dry_run"]: records.append({"status":"dry_run",**base})
            else:
              try:
                prompt = template.replace("[TARGET_DIFFICULTY]",config["difficulty"]).replace("[INSERT FIGURE OR FIGURE DESCRIPTION]","The figure is attached as image input.").replace("[INSERT TRUE STATEMENT]",job["reference_context"])
                record = {"status":"success",**base,"mutation":invoke(job,root/job["paper"],prompt,config)}
                if not has_mutation(record): raise ValueError("Model returned no counterfactual claim")
                save(job_cp,record)
              except Exception as exc: record={"status":"skipped",**base,"mutation_error":str(exc)}
              records.append(record)
        output_records = [record for record in records if has_mutation(record)]
        if output_records and not config["dry_run"]:
            artifact = work / output_name(item["name"])
            packaged = build_artifact(artifact, root, output_records, key)
            dataset = Path(config["output_dir"]) / "dataset.jsonl"
            merge_dataset(work / "artifact", Path(config["output_dir"]), key, packaged)
            checkpoint = {"status":"success","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"claim_count":len(packaged),"local_output":str(dataset)}
            if config["upload"]: checkpoint["output_file"] = drive.upload_file(artifact, config["output_folder"], artifact.name, key)
            save(file_cp,checkpoint)
            records = packaged
        elif not config["dry_run"]:
            save(file_cp,{"status":"skipped","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"claim_count":0,"reason":"No successful mutation"})
    except Exception as exc:
        records.append({"status":"error","drive_file":item,"error":str(exc)})
        try: save(file_cp,{"status":"failed","format_version":drive.ARTIFACT_VERSION,"drive_file":item,"error":str(exc)})
        except Exception: pass
        log_file("error", item, f"error={json.dumps(str(exc))}")
    finally:
        cleanup.delete_workdir(work,temp_root)
        status = "error" if any(record.get("status") == "error" for record in records) else ("dry-run" if config["dry_run"] else "success")
        log_file("complete", item, f"status={status}")
    return records

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("folder",help="source Google Drive folder URL or ID"); parser.add_argument("output_folder",nargs="?",help="destination Google Drive folder URL or ID (required with --upload)"); parser.add_argument("--workers",type=int,default=1); parser.add_argument("--temp-root",type=Path,default=Path(".work")); parser.add_argument("--checkpoint-dir",type=Path,default=Path(".checkpoints")); parser.add_argument("--target-cache",type=Path,default=Path(".target_cache")); parser.add_argument("--output-dir",type=Path,default=Path("outputs")); parser.add_argument("--prompt",type=Path,default=Path("prompts/mutate_claim_text_figure_short.md")); parser.add_argument("--difficulty",choices=["Easy","Medium","Hard","Very hard"],default=DEFAULT_DIFFICULTY); parser.add_argument("--model",default=None); parser.add_argument("--endpoint",default=None); parser.add_argument("--timeout",type=float,default=120,help="model API read timeout in seconds"); parser.add_argument("--drive-timeout",type=float,default=120,help="Google Drive socket timeout in seconds"); parser.add_argument("--env",type=Path,default=Path(".env")); parser.add_argument("--upload",action=argparse.BooleanOptionalAction,default=True); parser.add_argument("--dry-run",action="store_true"); args=parser.parse_args()
    if args.workers < 1: parser.error("--workers must be at least 1")
    if args.timeout <= 0 or args.drive_timeout <= 0: parser.error("timeouts must be positive")
    if args.upload and not args.output_folder: parser.error("output_folder is required with --upload")
    load_env(args.env); os.environ["GDRIVE_TIMEOUT"] = str(args.drive_timeout); api_key=os.getenv("FPT_API_KEY")
    if not args.dry_run and not api_key: parser.error("FPT_API_KEY is missing")
    args.temp_root.mkdir(parents=True,exist_ok=True); completed_keys=drive.output_source_keys(args.output_folder) if args.upload else None; pending,scanned=drive.discover(args.folder,args.checkpoint_dir,completed_keys)
    config={"env":str(args.env.resolve()),"temp_root":str(args.temp_root.resolve()),"checkpoints":str(args.checkpoint_dir.resolve()),"target_cache":str(args.target_cache.resolve()),"output_dir":str(args.output_dir.resolve()),"prompt":str(args.prompt.resolve()),"output_folder":args.output_folder,"upload":args.upload,"difficulty":args.difficulty,"model":args.model or os.getenv("FPT_MODEL","Qwen2.5-VL-7B-Instruct"),"endpoint":args.endpoint or (os.getenv("FPT_BASE_URL","").rstrip("/")+"/chat/completions" if os.getenv("FPT_BASE_URL") else "https://mkp-api.fptcloud.com/chat/completions"),"timeout":args.timeout,"dry_run":args.dry_run,"api_key":api_key}
    print(f"[pipeline] workers={args.workers} files_queued={len(pending)} files_at_once={min(args.workers, len(pending))} upload={args.upload} remote_completed={len(completed_keys or ())} output_dir={args.output_dir}", flush=True)
    print(f"[cache-phase] files={len(pending)} workers={args.workers}", flush=True)
    if args.workers == 1:
        prepared = [item for item in pending if prepare_target(item,config)]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(prepare_target,item,config):item for item in pending}
            prepared = []
            for future in futures:
                try:
                    if future.result(): prepared.append(futures[future])
                except Exception as exc: log_file("cache-error",futures[future],f"error={json.dumps(str(exc))}")
    pending = prepared
    print(f"[mutation-phase] cached_files={len(pending)}; all target caching is complete", flush=True)
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
    errors=sum(record.get("status")=="error" for record in results); print(f"Scanned {scanned}; pending {len(pending)}; workers {args.workers}; records {len(results)}; errors {errors}."); return 1 if errors else 0
if __name__ == "__main__": raise SystemExit(main())
