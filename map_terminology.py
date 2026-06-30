def generate_terminology_mapping(client, claim: str, table_data: str) -> str:
    prompt = f"""
You are an expert academic assistant. 
Here is a structured table extracted from a research paper:
{table_data}

Here is a claim made about this table:
{claim}

The claim uses domain terminology and abbreviations that may not exactly match the literal column headers or row names in the table. 
Please provide a brief, explicit mapping (a glossary) that connects the concepts in the claim to the specific variables/columns in the table. 
CRITICAL: Pay extremely close attention to compound abbreviations. You MUST explicitly define these abbreviations in terms of the table's exact column names.
Do not evaluate or fact-check the claim, just map the terminology so a fact-checker can understand it. Keep it concise.
"""
    response = client.chat.completions.create(
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt}
        ],
        model="Qwen2.5-VL-7B-Instruct",
        temperature=0.0
    )
    return response.choices[0].message.content
