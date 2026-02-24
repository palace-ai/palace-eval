import re

from palace.models.api_model import APIModel
from palace.utils.constants import GPTJRC_PROD_API_URL
from palace.utils.printing import print
from palace.utils.secrets import GPTJRC_PROD_TOKEN


class Judge:
    def __init__(
        self,
        judge_model: str,
        judge_prompt: str,
        output_keywords: list[str] = ["reasoning", "judgement"],
        judge_inference: str = "remote",
    ) -> None:
        """Initialize the Judge.

        Parameters
        ----------
        judge_model : str
            The model to use for judging.
        judge_prompt : str
            The system prompt to use for the judge model.
            It MUST instruct the judge model to provide a judgement in the format:
            ```
            <keyword1>
            value for keyword1
            </keyword1>
            <keyword2>
            value for keyword2
            </keyword2>
            ...
            ```
        output_keywords : list[str]
            The list of keywords to extract from the judge model's output.
            It MUST match the keywords in the judge prompt.
            Defaults to ["reasoning", "judgement"].
        judge_inference : str
            The inference method for the judge model. Can be "local" or "remote". Defaults to "remote".
        """
        self.judge_prompt = judge_prompt
        self.output_keywords = output_keywords

        # initialize judge model
        assert judge_inference in ["local", "remote"]
        if judge_inference == "local":
            raise NotImplementedError("Local judge inference is no longer supported.")
            # judge_model_id = "/mnt/storage2/hf_models/Qwen2.5-3B-Instruct"
            # self.judge_model = HuggingfaceModel(
            #     judge_model_id, gpu_memory_utilization=0.3
            # )
        if judge_inference == "remote":
            assert GPTJRC_PROD_API_URL is not None, (
                "GPTJRC_PROD_API_URL is not set in the environment variables."
            )
            self.judge_model = APIModel(
                judge_model,
                GPTJRC_PROD_API_URL,
                GPTJRC_PROD_TOKEN,
            )

    def judge(self, prompt: str) -> dict[str, str]:
        """Judge the given prompt and extract keyword values.

        Parameters
        ----------
        prompt : str
            The prompt to be judged.

        Returns
        -------
        dict[str, str]
            A dictionary containing the extracted keyword values.
        """
        conversation = []
        if self.judge_prompt is not None:
            conversation.append({"role": "system", "content": self.judge_prompt})
        conversation.append({"role": "user", "content": prompt})

        count, max_attempts = 0, 5
        while count < max_attempts:
            count += 1
            keyword_values = {}

            judge_output = self.judge_model.generate(conversation)
            for keyword in self.output_keywords:
                try:
                    value = re.findall(
                        rf"<{keyword}>(.*?)</{keyword}>", judge_output, flags=re.S
                    )[0]
                    keyword_values[keyword] = value.strip()
                except Exception as e:
                    print(
                        f"[bold yellow]Couldn't get value for keyword '{keyword}' from judge output:\n{judge_output}\n\nEncountered the following exception: {e}"
                    )
                    continue

            # check that all keywords were found
            if set(keyword_values.keys()) != set(self.output_keywords):
                print(
                    f"[bold yellow]Not all keywords found in judge output. Retrying ({count}/{max_attempts})..."
                )
            else:
                return keyword_values
        else:
            raise ValueError(
                f"[bold red]Max attempts ({max_attempts}) exceeded. Could not extract all keywords from judge output."
            )
