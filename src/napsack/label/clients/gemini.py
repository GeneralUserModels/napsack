from typing import Optional, Any, Dict
import json
import os
import time
from napsack.label.clients.client import VLMClient, CAPTION_SCHEMA

from google import genai
from google.genai import types


class GeminiResponse:
    def __init__(self, response):
        self.response = response
        self._json = None

    @property
    def text(self) -> str:
        return self.response.text

    @property
    def json(self):
        if self._json is None:
            self._json = json.loads(self.text)
        return self._json


class GeminiClient(VLMClient):
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        if genai is None:
            raise RuntimeError("google-genai not installed")

        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def upload_file(self, path: str, session_id: str = None) -> Any:
        video_file = self.client.files.upload(file=path)

        while True:
            video_file = self.client.files.get(name=video_file.name)
            state = getattr(getattr(video_file, "state", None), "name", None)

            if state == "PROCESSING":
                time.sleep(2)
            elif state == "FAILED":
                raise RuntimeError("Gemini failed processing file")
            elif state == "ACTIVE":
                break
            else:
                break

        return video_file

    def generate(self, prompt: str, file_descriptor: Optional[Any] = None,
                 schema: Optional[Dict] = None) -> GeminiResponse:

        inputs = [prompt]
        if file_descriptor:
            inputs.append(file_descriptor)

        if "gemini-3" in self.model_name:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema or CAPTION_SCHEMA,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
            )
        else:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
                response_schema=schema or CAPTION_SCHEMA
            )

        res = self.client.models.generate_content(
            model=self.model_name,
            contents=inputs,
            config=config
        )

        return GeminiResponse(res)
