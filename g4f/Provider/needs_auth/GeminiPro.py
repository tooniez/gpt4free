from __future__ import annotations

from ..template import OpenaiTemplate


class GeminiPro(OpenaiTemplate):
    label = "Google Gemini API"
    url = "https://ai.google.dev"
    login_url = "https://aistudio.google.com/u/0/apikey"
    base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
    backup_url = "https://g4f.space/api/gemini"
    quota_url = backup_url + "/quota"
    active_by_default = True
    working = True
    models_needs_auth = True
    add_thought_signature = True
