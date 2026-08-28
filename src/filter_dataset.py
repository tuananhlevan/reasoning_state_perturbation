#!/usr/bin/env python3
# Filter dataset against SciVer and MuSciClaims benchmarks
import argparse, json, math, os, re, shutil, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np
import requests
from tqdm import tqdm

DEFAULT_MODEL = "multilingual-e5-large"
DEFAULT_CLAIM_THRESHOLD = 0.85
DEFAULT_CONTEXT_THRESHOLD = 0.85
DEFAULT_BATCH_SIZE = 128
DEFAULT_WORKERS = 8

ARXIV_REGEX = re.compile(r"(?:arxiv:?\s*|abs/|html/|^|[^a-zA-Z0-9])(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)

def load_env(path: Path = Path(".env")) -> None:
    if not path.is_file(): return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        key, value = line.split("=", 1)
        val = value.strip().strip("'\"")
        os.environ.setdefault(key.strip(), val)

def normalize_text(text: str) -> str:
    if not text: return ""
    t = re.sub(r"\\[a-zA-Z]+(?:\[[^\]]*\])?\{([^}]*)\}", r" \1 ", text)
    t = re.sub(r"\\[a-zA-Z]+", " ", t)
    t = re.sub(r"[^a-zA-Z0-9]", " ", t).lower()
    return " ".join(t.split())

def extract_arxiv_ids(text: str) -> Set[str]:
    if not text: return set()
    found = set()
    for match in ARXIV_REGEX.finditer(text):
        raw_id = match.group(1).lower()
        found.add(raw_id)
        versionless = re.sub(r"v\d+$", "", raw_id)
        found.add(versionless)
    return found

def extract_paper_from_fig(fig_path: str) -> str:
    if not fig_path: return ""
    parts = Path(fig_path).parts
    if len(parts) >= 2 and parts[0].lower() == "ref": return parts[1]
    if len(parts) >= 1: return parts[0]
    return ""

def jaccard_similarity(tokens1: Set[str], tokens2: Set[str]) -> float:
    if not tokens1 or not tokens2: return 0.0
    intersection = len(tokens1.intersection(tokens2))
    union = len(tokens1.union(tokens2))
    return intersection / union if union > 0 else 0.0

def ngrams(text: str, n: int = 3) -> Set[str]:
    words = text.split()
    if len(words) < n: return {text} if text else set()
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}

class BenchmarkData:
    def __init__(self):
        self.arxiv_ids: Set[str] = set()
        self.paper_ids: Set[str] = set()
        self.normalized_titles: Dict[str, str] = {}
        self.title_token_sets: List[Tuple[Set[str], str]] = []
        self.contexts: List[Dict[str, Any]] = []
        self.claims: List[Dict[str, Any]] = []
        self.unique_claim_texts: List[str] = []

def load_benchmarks(related_dir: Path, sciver_dir: Optional[Path] = None, musci_dir: Optional[Path] = None) -> BenchmarkData:
    bench = BenchmarkData()
    sciver_path = sciver_dir or (related_dir / "SciVer")
    musci_path = musci_dir or (related_dir / "MuSciClaims")
    print(f"[benchmarks] Loading benchmarks from {related_dir}...")
    if sciver_path.is_dir():
        papers_dir = sciver_path / "papers"
        if papers_dir.is_dir():
            for pfile in sorted(papers_dir.glob("*.json")):
                try:
                    pdata = json.loads(pfile.read_text(encoding="utf-8"))
                    pid = pfile.stem
                    bench.arxiv_ids.update(extract_arxiv_ids(pid))
                    title = pdata.get("title", "")
                    if title:
                        norm_t = normalize_text(title)
                        if norm_t:
                            bench.normalized_titles[norm_t] = f"SciVer:{pid}:{title}"
                            bench.title_token_sets.append((set(norm_t.split()), f"SciVer:{pid}:{title}"))
                    url = pdata.get("url", "")
                    if url: bench.arxiv_ids.update(extract_arxiv_ids(url))
                    for sec in pdata.get("sections", []):
                        sec_text = sec.get("text", "")
                        if sec_text and len(sec_text) > 30:
                            norm_sec = normalize_text(sec_text)
                            bench.contexts.append({"source": f"SciVer:{pid}:section:{sec.get('section_name','')}", "text": sec_text, "norm": norm_sec, "ngrams": ngrams(norm_sec, 4)})
                except Exception as e:
                    print(f"    [SciVer] Warning: Failed to parse {pfile}: {e}")
        for split_name in ["testset.json", "valset.json"]:
            split_file = sciver_path / split_name
            if split_file.is_file():
                try:
                    split_data = json.loads(split_file.read_text(encoding="utf-8"))
                    for item in split_data:
                        pid = item.get("paperid", "")
                        if pid: bench.arxiv_ids.update(extract_arxiv_ids(pid))
                        for k in ["claim", "origin_statement", "perturbed_statement"]:
                            c = item.get(k, "")
                            if c and isinstance(c, str) and c.strip():
                                bench.claims.append({"source": f"SciVer:{split_name}:{k}", "claim": c.strip(), "paper_id": pid})
                except Exception as e:
                    print(f"    [SciVer] Warning: Failed to load {split_file}: {e}")
        print(f"  [SciVer] Loaded {len(bench.arxiv_ids)} arXiv IDs, {len(bench.normalized_titles)} titles.")

    if musci_path.is_dir():
        test_jsonl = musci_path / "test_set.jsonl"
        if test_jsonl.is_file():
            try:
                with test_jsonl.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip(): continue
                        item = json.loads(line)
                        pid = item.get("paper_id", "")
                        if pid:
                            bench.paper_ids.add(pid.strip())
                            bench.arxiv_ids.update(extract_arxiv_ids(pid))
                        cap = item.get("caption", "")
                        if cap and len(cap) > 20:
                            norm_cap = normalize_text(cap)
                            bench.contexts.append({"source": f"MuSciClaims:{pid}:caption", "text": cap, "norm": norm_cap, "ngrams": ngrams(norm_cap, 4)})
                        claim_text = item.get("claim_text", "")
                        if claim_text and claim_text.strip():
                            bench.claims.append({"source": f"MuSciClaims:{pid}", "claim": claim_text.strip(), "paper_id": pid})
            except Exception as e:
                print(f"  [MuSciClaims] Warning: Failed to load {test_jsonl}: {e}")
        print(f"  [MuSciClaims] Loaded {len(bench.paper_ids)} paper IDs, {len(bench.claims)} claims.")

    seen = set()
    for entry in bench.claims:
        c = entry["claim"]
        if c not in seen:
            seen.add(c)
            bench.unique_claim_texts.append(c)
    print(f"[benchmarks] Total unique benchmark claims to embed: {len(bench.unique_claim_texts)}")
    return bench

class FptEmbeddingClient:
    def __init__(self, api_key: str, base_url: str = "https://mkp-api.fptcloud.com", model: str = DEFAULT_MODEL, workers: int = DEFAULT_WORKERS, timeout: float = 30.0):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/embeddings"
        self.model = model
        self.workers = workers
        self.timeout = timeout
        self.session = requests.Session()
        self.headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _embed_single_batch(self, batch: List[str], max_retries: int = 5) -> List[List[float]]:
        payload = {"model": self.model, "input": batch}
        for attempt in range(1, max_retries + 1):
            try:
                resp = self.session.post(self.endpoint, headers=self.headers, json=payload, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", [])
                    if items and "index" in items[0]:
                        items = sorted(items, key=lambda x: x["index"])
                    return [item["embedding"] for item in items]
                elif resp.status_code in (429, 500, 502, 503, 504):
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                else:
                    raise RuntimeError(f"Embedding API error {resp.status_code}: {resp.text}")
            except (requests.RequestException, TimeoutError) as exc:
                if attempt == max_retries: raise RuntimeError(f"Embedding failed: {exc}") from exc
                time.sleep(0.5 * (2 ** (attempt - 1)))
        raise RuntimeError("Embedding failed after retries")

    def embed_texts(self, texts: List[str], batch_size: int = DEFAULT_BATCH_SIZE, desc: str = "Embedding") -> np.ndarray:
        if not texts: return np.empty((0, 1024), dtype=np.float32)
        batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
        embeddings: List[Optional[List[List[float]]]] = [None] * len(batches)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            future_to_idx = {pool.submit(self._embed_single_batch, batch): idx for idx, batch in enumerate(batches)}
            with tqdm(total=len(texts), desc=desc, unit="sent") as pbar:
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    batch_res = future.result()
                    embeddings[idx] = batch_res
                    pbar.update(len(batch_res))
        flat = []
        for b in embeddings:
            if b is not None: flat.extend(b)
        arr = np.array(flat, dtype=np.float32)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms

def check_paper_match(record: Dict[str, Any], bench: BenchmarkData) -> Tuple[bool, str, str]:
    fig = record.get("fig", "")
    context = record.get("context", "")
    claim = record.get("claim", "")
    paper_dir = extract_paper_from_fig(fig)
    all_arxiv_ids = extract_arxiv_ids(paper_dir) | extract_arxiv_ids(context) | extract_arxiv_ids(claim)
    for aid in all_arxiv_ids:
        if aid in bench.arxiv_ids:
            return True, "same_paper_arxiv_id", f"arXiv:{aid}"
    for pid in bench.paper_ids:
        if pid.lower() in paper_dir.lower() or pid.lower() in context.lower():
            return True, "same_paper_id", f"PaperID:{pid}"
    if paper_dir:
        norm_paper = normalize_text(paper_dir)
        if norm_paper:
            if norm_paper in bench.normalized_titles:
                return True, "same_paper_title_exact", bench.normalized_titles[norm_paper]
            if len(norm_paper) >= 25:
                for norm_t, raw_t in bench.normalized_titles.items():
                    if len(norm_t) >= 25 and (norm_paper.startswith(norm_t) or norm_t.startswith(norm_paper)):
                        return True, "same_paper_title_prefix", raw_t
            paper_tokens = set(norm_paper.split())
            if len(paper_tokens) >= 4:
                for bench_tokens, raw_t in bench.title_token_sets:
                    if len(bench_tokens) >= 4 and jaccard_similarity(paper_tokens, bench_tokens) >= 0.80:
                        return True, "same_paper_title_token_jaccard", raw_t
    return False, "", ""

def check_context_match(record: Dict[str, Any], bench: BenchmarkData, threshold: float = DEFAULT_CONTEXT_THRESHOLD) -> Tuple[bool, str, str]:
    ctx = record.get("context", "")
    if not ctx or len(ctx) < 40: return False, "", ""
    norm_ctx = normalize_text(ctx)
    if len(norm_ctx) < 40: return False, "", ""
    ctx_ngrams = ngrams(norm_ctx, 4)
    if not ctx_ngrams: return False, "", ""
    for b_ctx in bench.contexts:
        b_ngrams = b_ctx.get("ngrams", set())
        if not b_ngrams: continue
        sim = jaccard_similarity(ctx_ngrams, b_ngrams)
        if sim >= 0.70:
            return True, f"similar_context_overlap_{sim:.3f}", b_ctx["source"]
        if len(norm_ctx) > 80 and len(b_ctx["norm"]) > 80:
            if norm_ctx[:100] in b_ctx["norm"] or b_ctx["norm"][:100] in norm_ctx:
                return True, "similar_context_substring", b_ctx["source"]
    return False, "", ""

def run_filter(
    dataset_path: Path, related_dir: Path, output_path: Path, removed_path: Path,
    sciver_dir: Optional[Path] = None, musciclaims_dir: Optional[Path] = None,
    claim_threshold: float = DEFAULT_CLAIM_THRESHOLD, context_threshold: float = DEFAULT_CONTEXT_THRESHOLD,
    model: str = DEFAULT_MODEL, batch_size: int = DEFAULT_BATCH_SIZE, workers: int = DEFAULT_WORKERS,
    remove_pairs: bool = True, dry_run: bool = False, in_place: bool = False
) -> Dict[str, Any]:
    start_time = time.time()
    load_env()
    api_key = os.getenv("FPT_API_KEY")
    base_url = os.getenv("FPT_BASE_URL", "https://mkp-api.fptcloud.com")
    if not api_key: raise ValueError("FPT_API_KEY is not set.")

    print(f"[filter] Reading input dataset from {dataset_path}...")
    records: List[Dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line_idx, line in enumerate(f):
            line_str = line.strip()
            if not line_str: continue
            try:
                rec = json.loads(line_str)
                rec["_line_idx"] = line_idx
                records.append(rec)
            except json.JSONDecodeError: pass
    print(f"[filter] Loaded {len(records)} total records from {dataset_path}.")

    bench = load_benchmarks(related_dir, sciver_dir=sciver_dir, musci_dir=musciclaims_dir)

    print("\n[filter] Stage 1 & 2: Checking Paper Identity & Context Similarity...")
    flagged_reasons: Dict[int, List[Dict[str, Any]]] = {}
    paper_match_count = context_match_count = 0

    for rec in tqdm(records, desc="Paper & Context Check", unit="rec"):
        idx = rec["_line_idx"]
        p_match, p_reason, p_detail = check_paper_match(rec, bench)
        if p_match:
            flagged_reasons.setdefault(idx, []).append({"criterion": "same_paper", "reason": p_reason, "detail": p_detail})
            paper_match_count += 1
            continue
        c_match, c_reason, c_detail = check_context_match(rec, bench, threshold=context_threshold)
        if c_match:
            flagged_reasons.setdefault(idx, []).append({"criterion": "similar_context", "reason": c_reason, "detail": c_detail})
            context_match_count += 1

    print(f"[filter] Stage 1 (Paper match) flagged: {paper_match_count} records.")
    print(f"[filter] Stage 2 (Context match) flagged: {context_match_count} records.")

    print(f"\n[filter] Stage 3: Computing Semantic Claim Similarity with model '{model}' (threshold={claim_threshold})...")
    client = FptEmbeddingClient(api_key=api_key, base_url=base_url, model=model, workers=workers)

    bench_cache_file = Path("outputs") / "intermediate" / f"benchmark_embeddings_{model.replace('/', '_')}.npy"
    bench_cache_file.parent.mkdir(parents=True, exist_ok=True)
    if bench_cache_file.is_file():
        print(f"  Loading cached benchmark embeddings from {bench_cache_file}...")
        bench_embs = np.load(bench_cache_file)
    else:
        print(f"  Embedding {len(bench.unique_claim_texts)} benchmark claims via FPT API...")
        bench_embs = client.embed_texts(bench.unique_claim_texts, batch_size=batch_size, desc="Bench Claims")
        np.save(bench_cache_file, bench_embs)
        print(f"  Cached benchmark embeddings to {bench_cache_file}.")

    dataset_claims = [rec.get("claim", "").strip() for rec in records]
    print(f"  Embedding {len(dataset_claims)} dataset claims via FPT API...")
    dataset_embs = client.embed_texts(dataset_claims, batch_size=batch_size, desc="Dataset Claims")

    print("  Computing cosine similarity matrix...")
    chunk_size = 5000
    claim_match_count = 0
    for i in range(0, len(dataset_embs), chunk_size):
        end = min(i + chunk_size, len(dataset_embs))
        chunk_embs = dataset_embs[i:end]
        sim_matrix = np.dot(chunk_embs, bench_embs.T)
        max_sims = np.max(sim_matrix, axis=1)
        best_bench_indices = np.argmax(sim_matrix, axis=1)
        for local_idx, (sim_score, bench_idx) in enumerate(zip(max_sims, best_bench_indices)):
            global_idx = i + local_idx
            rec_line_idx = records[global_idx]["_line_idx"]
            if sim_score >= claim_threshold:
                matched_bench_claim = bench.unique_claim_texts[bench_idx]
                flagged_reasons.setdefault(rec_line_idx, []).append({
                    "criterion": "similar_claim",
                    "reason": f"cosine_similarity_{sim_score:.4f}",
                    "score": float(sim_score),
                    "matched_claim": matched_bench_claim,
                })
                claim_match_count += 1

    print(f"[filter] Stage 3 (Claim similarity >= {claim_threshold}) flagged: {claim_match_count} records.")

    removed_line_indices: Set[int] = set(flagged_reasons.keys())
    if remove_pairs:
        print("\n[filter] Applying pair-aware decontamination (grouping by fig & context)...")
        pair_groups: Dict[Tuple[str, str], List[int]] = {}
        for rec in records:
            key = (rec.get("fig", ""), rec.get("context", ""))
            pair_groups.setdefault(key, []).append(rec["_line_idx"])
        pair_expanded_removals = 0
        for key, indices in pair_groups.items():
            if any(idx in removed_line_indices for idx in indices):
                for idx in indices:
                    if idx not in removed_line_indices:
                        removed_line_indices.add(idx)
                        flagged_reasons.setdefault(idx, []).append({
                            "criterion": "paired_record_removal",
                            "reason": "pair_counterpart_contaminated",
                            "detail": f"Fig: {key[0]}",
                        })
                        pair_expanded_removals += 1
        print(f"[filter] Removed {pair_expanded_removals} paired counterparts to maintain balanced pairs.")

    clean_records: List[Dict[str, Any]] = []
    removed_records: List[Dict[str, Any]] = []
    for rec in records:
        idx = rec["_line_idx"]
        clean_rec = {
            "context": rec.get("context", ""),
            "claim": rec.get("claim", ""),
            "fig": rec.get("fig", ""),
            "difficulty": rec.get("difficulty", ""),
            "label": rec.get("label", ""),
        }
        if idx in removed_line_indices:
            removed_records.append({"record": clean_rec, "reasons": flagged_reasons.get(idx, [])})
        else:
            clean_records.append(clean_rec)

    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("           DECONTAMINATION & FILTERING SUMMARY")
    print("=" * 60)
    print(f"Total Input Records:             {len(records):,}")
    print(f"Flagged by Same Paper:           {paper_match_count:,}")
    print(f"Flagged by Context Match:        {context_match_count:,}")
    print(f"Flagged by Claim Sim (>= {claim_threshold}): {claim_match_count:,}")
    print(f"Total Unique Records Removed:    {len(removed_records):,} ({len(removed_records)/len(records)*100:.2f}%)")
    print(f"Clean Records Retained:          {len(clean_records):,} ({len(clean_records)/len(records)*100:.2f}%)")
    print(f"Total Processing Time:           {total_time:.2f} seconds")
    print("=" * 60)

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        removed_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[filter] Writing {len(clean_records):,} clean records to {output_path}...")
        with output_path.open("w", encoding="utf-8") as f:
            for rec in clean_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[filter] Writing {len(removed_records):,} removed records to {removed_path}...")
        with removed_path.open("w", encoding="utf-8") as f:
            for rec in removed_records:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if in_place:
            backup_path = dataset_path.with_suffix(f".backup_{int(time.time())}.jsonl")
            print(f"[filter] Creating backup of original dataset at {backup_path}...")
            shutil.copy2(dataset_path, backup_path)
            print(f"[filter] Replacing {dataset_path} with filtered dataset...")
            shutil.copy2(output_path, dataset_path)
        print("[filter] Done! Filtering completed successfully.")
    else:
        print("[filter] Dry run complete. No files written.")

    return {
        "total_records": len(records),
        "removed_records": len(removed_records),
        "clean_records": len(clean_records),
        "paper_matches": paper_match_count,
        "context_matches": context_match_count,
        "claim_matches": claim_match_count,
        "duration_seconds": total_time,
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("outputs/dataset.jsonl"), help="Path to input dataset JSONL")
    parser.add_argument("--related-data-dir", type=Path, default=Path("related_data"), help="Path to related_data folder")
    parser.add_argument("--sciver-dir", type=Path, default=None, help="Path to SciVer folder (optional)")
    parser.add_argument("--musciclaims-dir", type=Path, default=None, help="Path to MuSciClaims folder (optional)")
    parser.add_argument("--output", type=Path, default=Path("outputs/dataset_filtered.jsonl"), help="Output path for clean dataset")
    parser.add_argument("--removed-output", type=Path, default=Path("outputs/dataset_removed.jsonl"), help="Output path for removed records audit")
    parser.add_argument("--claim-threshold", type=float, default=DEFAULT_CLAIM_THRESHOLD, help="Cosine similarity threshold for claims (default: 0.85)")
    parser.add_argument("--context-threshold", type=float, default=DEFAULT_CONTEXT_THRESHOLD, help="Similarity threshold for context (default: 0.85)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Embedding model name via FPT API (default: multilingual-e5-large)")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Batch size for embedding API (default: 128)")
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="Parallel worker threads for embedding API (default: 8)")
    parser.add_argument("--remove-pairs", action=argparse.BooleanOptionalAction, default=True, help="Remove paired counterpart when one record matches (default: True)")
    parser.add_argument("--dry-run", action="store_true", help="Run examination without writing output files")
    parser.add_argument("--in-place", action="store_true", help="Replace the input dataset file with filtered dataset")
    args = parser.parse_args()

    run_filter(
        dataset_path=args.dataset,
        related_dir=args.related_data_dir,
        sciver_dir=args.sciver_dir,
        musciclaims_dir=args.musciclaims_dir,
        output_path=args.output,
        removed_path=args.removed_output,
        claim_threshold=args.claim_threshold,
        context_threshold=args.context_threshold,
        model=args.model,
        batch_size=args.batch_size,
        workers=args.workers,
        remove_pairs=args.remove_pairs,
        dry_run=args.dry_run,
        in_place=args.in_place,
    )

if __name__ == "__main__":
    main()
