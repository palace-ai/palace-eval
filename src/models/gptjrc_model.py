from typing import Dict, List

from openai import OpenAI

from . import Model


class GPTJRCModel(Model):
    def __init__(self, model_id: str = "llama-3.3-70b-instruct"):
        self.model_id = model_id
        self._api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjQ3N2ZiNDMyLWNhZTktNDkyNC04MWUwLWEzNTkxZjNmYmNiZiIsImlzcyI6ImdwdGpyYyIsImlhdCI6MTc0MTY5MDUxMiwiZXhwIjoxNzY3MTM5MjAwLCJpc19yZXZva2VkIjpmYWxzZSwiYWNjb3VudF9pZCI6ImM0OTFhNDAwLWY5MjAtNGY4Mi1iOWFkLTEwOWI0OTA5YmFjOSIsInVzZXJuYW1lIjoibWFzc2ltaWxpYW5vLmFsdGllcmlAZWMuZXVyb3BhLmV1IiwicHJvamVjdF9pZCI6IkNSRUFURSIsImRlcGFydG1lbnQiOiJKUkMuVC4yIiwicXVvdGFzIjpbeyJtb2RlbF9uYW1lIjoiZ3B0LTRvIiwiZXhwaXJhdGlvbl9mcmVxdWVuY3kiOiJkYWlseSIsInZhbHVlIjoxNTAwMDAwfV0sImFjY2Vzc19ncm91cHMiOlt7ImlkIjoiMmI1ZjJmMWEtYjRkNy00MjMzLTg1MWYtMTEwZWEwYTAzZDNlIiwiYWNjZXNzX2dyb3VwIjoiZ2VuZXJhbCJ9XX0.Vb_i_-q5_tY4L4nNeIt23ZLjekE7uYXpRSbVE8cKy8M"

    @property
    def name(self):
        """The name of the model."""
        return self.model_id

    def generate(self, messages: List[Dict[str, str]], **_) -> str:
        client = OpenAI(
            api_key=self._api_key, base_url="https://api-gpt.jrc.ec.europa.eu/v1"
        )
        chat_completion = client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            stream=False,
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content
