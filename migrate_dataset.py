import json
from pathlib import Path

checkpoints_dir = Path(".checkpoints/jobs")
dataset_file = Path("outputs/dataset.jsonl")

# Map of claim -> context
claim_to_context = {}
for jpath in checkpoints_dir.glob("*.json"):
    try:
        data = json.loads(jpath.read_text(encoding="utf-8"))
        if data.get("status") == "success":
            ctx = data.get("reference_context")
            mutation = data.get("mutation", {})
            if ctx:
                # new format
                ent = mutation.get("entailed_claim")
                ref = mutation.get("claim") # this is counterfactual_claim
                if ent: claim_to_context[ent] = ctx
                if ref: claim_to_context[ref] = ctx
                # old format
                if "entailed_claim" not in mutation:
                    # for old format, the original context is the entailed claim
                    claim_to_context[ctx] = ctx
    except Exception as e:
        print(f"Failed to parse {jpath}: {e}")

print(f"Loaded {len(claim_to_context)} claim-to-context mappings from checkpoints.")

new_records = []
missing_count = 0
with dataset_file.open("r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        record = json.loads(line)
        c = record["claim"]
        if c in claim_to_context:
            record["context"] = claim_to_context[c]
        else:
            record["context"] = "UNKNOWN_CONTEXT"
            missing_count += 1
            
        # Ensure exact key order: context, claim, fig, difficulty, label
        ordered_record = {
            "context": record["context"],
            "claim": record["claim"],
            "fig": record["fig"],
            "difficulty": record["difficulty"],
            "label": record["label"]
        }
        new_records.append(ordered_record)

with dataset_file.open("w", encoding="utf-8") as f:
    for record in new_records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Migration complete! Processed {len(new_records)} records. Missing contexts: {missing_count}")
