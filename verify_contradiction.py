def verify_contradiction(client, encoded_img: str, claim: str, context: str = "", table_data: str = "") -> bool:
    system_prompt = "You are an expert fact-checker. Determine if the provided text CONTRADICTS the data in the image. Note that the text may use domain terminology that corresponds to the variables in the table. You must infer these mappings based on context. If the text asserts a trend or ranking that opposes the numerical data in the table, you must conclude it is a contradiction. \nThink step by step: \n1. Understand the claim and identify the main assertion. \n2. Understand the table and identify the relevant data. \n3. Map the terminology from the claim to the variables in the table. \n4. Compare the assertion with the data. \n5. Conclude whether it is a contradiction."
    
    if context:
        system_prompt += f"\n\nDomain Context to help map terminology:\n{context}"

    verify_response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}}, 
                    {"type": "text", "text": f"Extracted Table Data:\n{table_data}\n\nClaim: {claim}\nDoes this claim contradict the data? Explain your reasoning step-by-step, then conclude with YES or NO."}
                ],
            },
        ],
        model="Qwen2.5-VL-7B-Instruct",
        temperature=0.0
    )
    raw_response = verify_response.choices[0].message.content
    print("--- Verification Raw Response ---")
    print(raw_response)
    print("---------------------------------")
    return "YES" in raw_response.upper()
