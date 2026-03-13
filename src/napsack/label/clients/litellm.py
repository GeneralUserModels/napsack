import base64
import json
import os
import time
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any

import litellm
from napsack.label.clients.client import VLMClient, CAPTION_SCHEMA


class LiteLLMClient(VLMClient):
    """
    Unified LiteLLM-backed client. Pass the full litellm model string as model_name:

      gemini/gemini-2.5-flash                                    — Gemini (GEMINI_API_KEY)
      openai/gpt-4o                                              — OpenAI (OPENAI_API_KEY)
      anthropic/claude-3-5-sonnet-20241022                       — Anthropic (ANTHROPIC_API_KEY)
      hosted_vllm/Qwen/Qwen3-VL-8B + api_base=http://host/v1    — vLLM server
    """

    def __init__(
        self,
        model_name: str,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        max_tokens: int = 8192,
    ):
        self.max_tokens = max_tokens
        self.api_base = api_base
        self.model_name = model_name

        self._is_gemini = model_name.startswith("gemini/")
        self._is_vllm = model_name.startswith("hosted_vllm/")

        if self._is_gemini:
            self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
            if not self.api_key:
                raise RuntimeError("GEMINI_API_KEY not set")
        else:
            # Let litellm pick up the appropriate env var (OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.)
            self.api_key = api_key

        print(f"[LiteLLMClient] Model: {self.model_name}")
        if api_base:
            print(f"[LiteLLMClient] API base: {api_base}")

    def upload_file(self, path: str, session_id: str = None) -> Any:
        if self._is_gemini:
            return self._upload_gemini(path)
        else:
            return self._upload_inline(path)

    def _upload_gemini(self, path: str) -> Any:
        """Upload via litellm Files API (Gemini backend), waiting for ACTIVE state."""
        p = Path(path)
        suffix = p.suffix.lower()
        mime_map = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo", ".mkv": "video/x-matroska"}
        mime_type = mime_map.get(suffix, "video/mp4")
        with open(path, "rb") as f:
            file_obj = litellm.create_file(
                file=(p.name, f, mime_type),
                purpose="assistants",
                custom_llm_provider="gemini",
                api_key=self.api_key,
            )
        poll_url = f"{file_obj.id}?key={self.api_key}"
        for _ in range(60):
            with urllib.request.urlopen(poll_url) as resp:
                if json.loads(resp.read()).get("state") == "ACTIVE":
                    break
            time.sleep(2)
        else:
            raise RuntimeError(f"Gemini file {file_obj.id} never reached ACTIVE state")
        file_obj._mime_type = mime_type
        return file_obj

    def _upload_inline(self, path: str) -> Dict:
        """Base64-encode file for inline embedding in the request."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"File not found: {path}")
        with open(p, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        file_type = "video" if p.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"} else "image"
        mime_type = "video/mp4" if file_type == "video" else "image/jpeg"
        return {
            "path": str(p.absolute()),
            "type": file_type,
            "data_url": f"data:{mime_type};base64,{b64_data}",
        }

    def upload_images(self, paths: list, session_id: str = None) -> Dict:
        """Upload a list of image paths for frame-by-frame image mode (always base64)."""
        frames = []
        for i, path in enumerate(paths):
            p = Path(path)
            mime_type = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
            with open(p, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
            frames.append({"data_url": f"data:{mime_type};base64,{b64_data}", "label": f"Frame {i + 1}"})
        return {"type": "image_list", "frames": frames}

    def generate(
        self,
        prompt: str,
        file_descriptor: Optional[Any] = None,
        schema: Optional[Dict] = None,
    ) -> Any:
        if schema is None:
            schema = CAPTION_SCHEMA

        messages = self._build_messages(prompt, file_descriptor)

        params = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "api_base": self.api_base,
            "api_key": self.api_key,
        }

        if self._is_gemini:
            params["response_schema"] = schema
            params["response_mime_type"] = "application/json"
        elif self._is_vllm:
            params["extra_body"] = {"guided_json": schema}
        else:
            params["response_format"] = {"type": "json_object"}

        try:
            completion = litellm.completion(**params)
            return json.loads(completion.choices[0].message.content)
        except Exception as e:
            print(f"[LiteLLMClient] Error during generation: {e}")
            raise

    def _build_messages(self, prompt: str, file_desc: Optional[Any]) -> list:
        if not file_desc:
            return [{"role": "user", "content": prompt}]

        # Image-list mode: interleave "Frame N" labels with base64 image blocks
        if isinstance(file_desc, dict) and file_desc.get("type") == "image_list":
            content = []
            for frame in file_desc["frames"]:
                content.append({"type": "text", "text": frame["label"]})
                content.append({"type": "image_url", "image_url": {"url": frame["data_url"]}})
            content.append({"type": "text", "text": prompt})
            return [{"role": "user", "content": content}]

        if self._is_gemini:
            mime_type = getattr(file_desc, "_mime_type", "video/mp4")
            content = [
                {"type": "file", "file": {"file_id": file_desc.id, "format": mime_type}},
                {"type": "text", "text": prompt},
            ]
        else:
            file_type = file_desc.get("type", "image")
            data_url = file_desc.get("data_url")
            if not data_url:
                file_path = file_desc.get("path")
                with open(file_path, "rb") as f:
                    b64_data = base64.b64encode(f.read()).decode("utf-8")
                mime_type = "video/mp4" if file_type == "video" else "image/jpeg"
                data_url = f"data:{mime_type};base64,{b64_data}"

            if file_type == "video":
                content = [
                    {"type": "video_url", "video_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ]
            else:
                content = [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ]

        return [{"role": "user", "content": content}]
