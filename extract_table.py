def extract_table_from_image(client, encoded_img: str) -> str:
    vlm_response = client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "You are a data extraction assistant. Extract the table in this image into a JSON format."
            },
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded_img}"}},
                    {"type": "text", "text": "Extract all rows and columns from this table."}
                ],
            },
        ],
        model="Qwen2.5-VL-7B-Instruct",
        temperature=0.0
    )
    return vlm_response.choices[0].message.content
