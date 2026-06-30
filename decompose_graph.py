import json
import re

def decompose_claim_to_graph(client, claim: str) -> dict:
    prompt = f"""
Decompose this faithful claim into a reasoning graph JSON with 'nodes' (entities/values) and 'edges' (relationships/trends).
Claim: {claim}
"""
    llm_response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a JSON parsing assistant."},
            {"role": "user", "content": prompt}
        ],
        model="Qwen2.5-VL-7B-Instruct",
        temperature=0.0
    )
    data = llm_response.choices[0].message.content
    print(data)
    
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', data, re.DOTALL)
    if match:
        json_string = match.group(1)
        clean_json_string = json_string.replace("\\", "")
        return json.loads(clean_json_string)
    
    return {} # fallback if no match
