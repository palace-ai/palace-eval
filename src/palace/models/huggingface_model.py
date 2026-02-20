# DEPRECATED: this file is no longer used. PALACE now only supports evaluation of remote models/agents


# # import os

# from transformers import AutoTokenizer
# from vllm import LLM, SamplingParams

# from palace.models import Model
# from palace.utils.paths import MODELS_DIR


# class HuggingfaceModel(Model):
#     os.environ["HF_HUB_CACHE"] = str(MODELS_DIR)

#     def __init__(self, model_id: str, tensor_parallel_size: int = 2, **kwargs):
#         self.model_id = model_id
#         self.tensor_parallel_size = tensor_parallel_size
#         self.kwargs = kwargs
#         self.initialized = False

#     @property
#     def name(self):
#         """The name of the model."""
#         return self.model_id

#     # load the model lazily into the memory (on first generate call), for efficiency reasons
#     def _initialize(self):
#         if not self.initialized:
#             self.model = LLM(
#                 model=self.model_id,
#                 tensor_parallel_size=self.tensor_parallel_size,
#                 max_model_len=4096,  # 32768
#                 tokenizer_mode="auto",
#                 enable_prefix_caching=True,
#                 **self.kwargs,
#             )
#             self.tokenizer = AutoTokenizer.from_pretrained(
#                 self.model_id, trust_remote_code=True
#             )
#         self.initialized = True

#     def generate(self, messages: list[dict[str, str]], **_) -> str:
#         if not self.initialized:
#             self._initialize()

#         inputs = self.tokenizer.apply_chat_template(
#             messages,
#             tokenize=False,
#             add_generation_prompt=True,
#         )
#         sampling_params = SamplingParams(
#             max_tokens=16384,
#             n=1,
#             stop="###STOP###",
#         )
#         outputs = self.model.generate(inputs, sampling_params)
#         return outputs[0].outputs[0].text
