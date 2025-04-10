from typing import Dict, List

from openai import OpenAI, RateLimitError

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from . import Model


class GPTJRCModel(Model):
    def __init__(self, model_id: str = "llama-3.3-70b-instruct"):
        self.model_id = model_id
        self._api_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjQ3N2ZiNDMyLWNhZTktNDkyNC04MWUwLWEzNTkxZjNmYmNiZiIsImlzcyI6ImdwdGpyYyIsImlhdCI6MTc0MTY5MDUxMiwiZXhwIjoxNzY3MTM5MjAwLCJpc19yZXZva2VkIjpmYWxzZSwiYWNjb3VudF9pZCI6ImM0OTFhNDAwLWY5MjAtNGY4Mi1iOWFkLTEwOWI0OTA5YmFjOSIsInVzZXJuYW1lIjoibWFzc2ltaWxpYW5vLmFsdGllcmlAZWMuZXVyb3BhLmV1IiwicHJvamVjdF9pZCI6IkNSRUFURSIsImRlcGFydG1lbnQiOiJKUkMuVC4yIiwicXVvdGFzIjpbeyJtb2RlbF9uYW1lIjoiZ3B0LTRvIiwiZXhwaXJhdGlvbl9mcmVxdWVuY3kiOiJkYWlseSIsInZhbHVlIjoxNTAwMDAwfV0sImFjY2Vzc19ncm91cHMiOlt7ImlkIjoiMmI1ZjJmMWEtYjRkNy00MjMzLTg1MWYtMTEwZWEwYTAzZDNlIiwiYWNjZXNzX2dyb3VwIjoiZ2VuZXJhbCJ9XX0.Vb_i_-q5_tY4L4nNeIt23ZLjekE7uYXpRSbVE8cKy8M"
        self.client = OpenAI(
            api_key=self._api_key, base_url="https://api-gpt.jrc.ec.europa.eu/v1"
        )

    @property
    def name(self):
        """The name of the model."""
        return self.model_id

    @retry(
        stop=stop_after_attempt(5),  # Max 5 attempts
        wait=wait_exponential(multiplier=10, max=60),  # Exponential backoff (10s -> 20s -> 40s -> 60s)
        retry=retry_if_exception_type(RateLimitError,),  # Retry only on RateLimitError
        before_sleep=lambda retry_state: print(
            f"Waiting for {retry_state.next_action.sleep:.0f} seconds due to rate limit..."
        ),
    )
    def generate(self, messages: List[Dict[str, str]], **_) -> str:
        chat_completion = self.client.chat.completions.create(
            model=self.model_id,
            messages=messages,
            stream=False,
            temperature=0.7,
        )
        return chat_completion.choices[0].message.content
