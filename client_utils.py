import os
import base64
from openai import OpenAI
from dotenv import load_dotenv

def get_client():
    load_dotenv('.env')
    return OpenAI(api_key=os.getenv("FPT_API_KEY"), base_url="https://mkp-api.fptcloud.com")

def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
