import json
import re

def mutate_claim_graph(client, original_graph: dict) -> dict:
    prompt = f"""
You are an expert logician and data manipulator.
Given the following reasoning graph (represented as JSON with 'nodes' and 'edges'), your goal is to deliberately mutate it to introduce a logical CONTRADICTION with its original meaning.

You should alter the graph by targeting one or more of the following reasoning concepts:
- Comparison (e.g., flip 'greater than' to 'less than')
- Aggregation (e.g., change 'total' to 'average', or modify sum)
- Ranking (e.g., swap 'best' to 'worst', or change ordinal position)
- Trend (e.g., reverse 'increasing' to 'decreasing')
- Statistical significance (e.g., change 'significant' to 'insignificant')
- Correlation (e.g., change 'positive correlation' to 'negative correlation')
- Causation (e.g., flip cause and effect)
- Temporal ordering (e.g., swap 'before' and 'after')
- Generalization (e.g., change 'all' to 'some' or 'none')
- Exception (e.g., introduce or remove an exception)
- Uncertainty (e.g., change 'certain' to 'unlikely')

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
