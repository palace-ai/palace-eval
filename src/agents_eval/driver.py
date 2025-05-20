from agents_eval.environments import MCPEnvironment
from agents_eval.evaluation import Evaluation
from agents_eval.models import GPTJRCModel, HuggingfaceModel
from agents_eval.paradigms import (
    PlanAndExecuteParadigm,
    ReActParadigm,
    ReflectionParadigm,
)

paradigms = [ReActParadigm, PlanAndExecuteParadigm, ReflectionParadigm]
envs = [
    MCPEnvironment(mcp_server="local"),
    # MCPEnvironment(mcp_server="aloha"),
]

evaluation = Evaluation(verbose=False, task_amount_limit=20, runs_per_configuration=1)

results = evaluation.evaluate_all(
    models=[
        # GPTJRCModel(),
        HuggingfaceModel(
            "Qwen/Qwen3-32B"
        )  # /mnt/storage2/hf_models/Llama-3.1-8B-Instruct
    ],
    paradigms=[paradigm() for paradigm in paradigms],
    environments=envs,
    tasklist="Fever",
    # _temperatures=[1.0, 0.7, 0.0],
)
print(results)
