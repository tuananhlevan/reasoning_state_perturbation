import json
import re

def mutate_claim_graph(client, original_graph: dict) -> dict:
    prompt = f"""
You are an expert logician and data manipulator.
Given the following strict JSON reasoning graph, your goal is to deliberately mutate it to introduce a strong logical CONTRADICTION with its original meaning.

Crucially, the graph contains directional edges representing comparisons or relationships. You MUST mutate the `relation` field of the edges to create a mathematical or logical opposite (e.g., if the relation is "better_than", flip it to "worse_than"). DO NOT just swap node names; explicitly change the relationship logic.

You should alter the graph by targeting one or more of the following reasoning concepts when flipping the relations:
- Maximum
- Minimum
- Ranking
- Average
- Variance
- Trend
- Plateau
- Acceleration
- Correlation
- Causation
- Generalization
- Exception
- Statistical significance
- Confidence
- Interaction
- Tradeoff
- Ablation
- Sensitivity
- Consistency
- Robustness

Original Graph:
{json.dumps(original_graph, indent=2)}

Output the mutated graph as valid JSON containing 'nodes' and 'edges', reflecting the contradictory claim.
Ensure the response is wrapped in a JSON block like:
```json
{{ ... }}
```
"""
    llm_response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a JSON generating assistant."},
            {"role": "user", "content": prompt}
        ],
        model="Qwen2.5-VL-7B-Instruct",
        temperature=0.7 # Higher temperature for creative mutation
    )
    data = llm_response.choices[0].message.content
    print("--- LLM Mutation Response ---")
    print(data)
    print("-----------------------------")
    
    match = re.search(r'```(?:json)?\s*(.*?)\s*```', data, re.DOTALL)
    if match:
        clean_json_string = match.group(1)
        try:
            return json.loads(clean_json_string)
        except json.JSONDecodeError:
            print("Warning: Failed to decode parsed JSON block.")
    
    # Fallback if no code block or bad json
    try:
        return json.loads(data)
    except Exception:
        print("Warning: Returning original graph as fallback due to JSON parsing error.")
        return original_graph
