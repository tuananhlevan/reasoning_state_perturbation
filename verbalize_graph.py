def verbalize_graph_to_claim(client, mutated_claim_graph) -> str:
    verbalize_prompt = f"""
Given the following strict JSON graph, write a natural language paragraph that seamlessly reflects its exact nodes and edges. 
Pay special attention to the directional edges (`source` -> `relation` -> `target`). Ensure your text captures these relationships exactly as they are defined.
IMPORTANT: DO NOT attempt to correct the information or align it with facts. Your job is ONLY to verbalize exactly what is in the graph, even if it is logically contradictory or factually incorrect.
Graph: {mutated_claim_graph}
"""
    verbalized_response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a technical writer."}, 
            {"role": "user", "content": verbalize_prompt}
        ],
        model="Qwen2.5-VL-7B-Instruct",
        temperature=0.7 # Slight temperature increase for natural language generation
    )
    return verbalized_response.choices[0].message.content
