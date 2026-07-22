#!/usr/bin/env python3
"""Run download -> mutate -> checkpoint -> delete for each Drive archive."""
from __future__ import annotations
import random
import argparse, base64, hashlib, json, mimetypes, os, tarfile, tempfile, zipfile
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
import requests
import delete as cleanup
import download as drive
from authenticate import load_env

IMAGE_TYPES = {".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".png":"image/png", ".webp":"image/webp"}

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
                        found.append({"paper":paper.name,"metadata_file":metadata.name,"asset_index":asset_index,"context_index":context_index,"reference_context":context.strip(),"compiled_images":[str(path.relative_to(paper.resolve())) for path in resolved]})
                    except ValueError as exc: skipped.append({"paper":paper.name,"asset_index":asset_index,"context_index":context_index,"reason":str(exc)})
    return found, skipped

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
    try: return json.loads(path.read_text(encoding="utf-8")).get("status") == "success"
    except (OSError, json.JSONDecodeError, AttributeError): return False

def save(path, record):
    path.parent.mkdir(parents=True, exist_ok=True); temporary = path.with_suffix(f".{os.getpid()}.tmp"); temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2)+"\n", encoding="utf-8"); temporary.replace(path)

def append_records(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

def process_file(item, config):
    log_file("queue-exit", item, "worker-started")
    load_env(Path(config["env"])); key = drive.item_key(item); file_cp = Path(config["checkpoints"]) / "files" / f"{key}.json"
    if successful(file_cp):
        log_file("complete", item, "status=file-checkpointed")
        return [{"status":"file_checkpointed","drive_file":item}]
    temp_root = Path(config["temp_root"]); work = Path(tempfile.mkdtemp(prefix=f"claim-{key[:10]}-", dir=temp_root)); records, all_ok = [], True
    try:
        bundle, extracted = work / "download.archive", work / "extracted"
        drive.download_file(item, bundle); extract(bundle, extracted); root = paper_root(extracted); file_jobs, skipped = jobs(root)
        records.extend({"status":"skipped","drive_file":item,**entry} for entry in skipped); all_ok = bool(file_jobs)
        template = Path(config["prompt"]).read_text(encoding="utf-8")
        for job in file_jobs:
            material = "\0".join([key,job["paper"],job["metadata_file"],str(job["asset_index"]),str(job["context_index"]),job["reference_context"],*job["compiled_images"]]); job_id = hashlib.sha256(material.encode()).hexdigest(); job_cp = Path(config["checkpoints"]) / "jobs" / f"{job_id}.json"; base = {"drive_file":item,"job_id":job_id,**job,"difficulty":config["difficulty"]}
            if successful(job_cp):
                cached = json.loads(job_cp.read_text(encoding="utf-8"))
                records.append({**cached, "status":"checkpointed", "checkpoint_source":str(job_cp)})
                continue
            if config["dry_run"]: all_ok=False; records.append({"status":"dry_run",**base}); continue
            try:
                prompt = template.replace("[TARGET_DIFFICULTY]",config["difficulty"]).replace("[INSERT FIGURE OR FIGURE DESCRIPTION]","The figure is attached as image input.").replace("[INSERT TRUE STATEMENT]",job["reference_context"])
                record = {"status":"success",**base,"mutation":invoke(job,root/job["paper"],prompt,config)}; save(job_cp,record)
            except Exception as exc: all_ok=False; record={"status":"error",**base,"error":str(exc)}
            records.append(record)
        if all_ok: save(file_cp,{"status":"success","drive_file":item,"job_count":len(file_jobs)})
    except Exception as exc: records.append({"status":"error","drive_file":item,"error":str(exc)})
    finally:
        cleanup.delete_workdir(work,temp_root)
        status = "error" if any(record.get("status") == "error" for record in records) else ("dry-run" if config["dry_run"] else "success")
        log_file("complete", item, f"status={status}")
    return records

def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("folder"); parser.add_argument("--workers",type=int,default=1); parser.add_argument("--temp-root",type=Path,default=Path(".work")); parser.add_argument("--checkpoint-dir",type=Path,default=Path("outputs/checkpoints")); parser.add_argument("--prompt",type=Path,default=Path("prompts/short.md")); parser.add_argument("--output",type=Path,default=Path("outputs/mutations.jsonl")); parser.add_argument("--difficulty",choices=["Easy","Medium","Hard","Very hard"],default=DEFAULT_DIFFICULTY); parser.add_argument("--model",default=None); parser.add_argument("--endpoint",default=None); parser.add_argument("--timeout",type=float,default=120); parser.add_argument("--env",type=Path,default=Path(".env")); parser.add_argument("--dry-run",action="store_true"); args=parser.parse_args()
    if args.workers < 1: parser.error("--workers must be at least 1")
    load_env(args.env); api_key=os.getenv("FPT_API_KEY")
    if not args.dry_run and not api_key: parser.error("FPT_API_KEY is missing")
    args.temp_root.mkdir(parents=True,exist_ok=True); pending,scanned=drive.discover(args.folder,args.checkpoint_dir)
    config={"env":str(args.env.resolve()),"temp_root":str(args.temp_root.resolve()),"checkpoints":str(args.checkpoint_dir.resolve()),"prompt":str(args.prompt.resolve()),"difficulty":args.difficulty,"model":args.model or os.getenv("FPT_MODEL","Qwen2.5-VL-7B-Instruct"),"endpoint":args.endpoint or (os.getenv("FPT_BASE_URL","").rstrip("/")+"/chat/completions" if os.getenv("FPT_BASE_URL") else "https://mkp-api.fptcloud.com/chat/completions"),"timeout":args.timeout,"dry_run":args.dry_run,"api_key":api_key}
    print(f"[pipeline] workers={args.workers} files_queued={len(pending)} files_at_once={min(args.workers, len(pending))} output={args.output}", flush=True)
    results=[]
    if args.workers == 1:
        for item in pending:
            log_file("queue-enter", item)
            batch = process_file(item,config); append_records(args.output,batch); results.extend(batch)
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
                    append_records(args.output,batch); results.extend(batch)
                    submit_next()
    errors=sum(record["status"]=="error" for record in results); print(f"Scanned {scanned}; pending {len(pending)}; workers {args.workers}; records {len(results)}; errors {errors}."); return 1 if errors else 0
if __name__ == "__main__": raise SystemExit(main())
