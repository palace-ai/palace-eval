from agents_eval.environments import MCPEnvironment
from agents_eval.evaluation import Evaluation
from agents_eval.models import GPTJRCModel, HuggingfaceModel
from agents_eval.paradigms import SimpleReActParadigm

paradigms = [SimpleReActParadigm]
envs = [
    MCPEnvironment(mcp_server="local"),
    # MCPEnvironment(mcp_server="aloha"),
]

evaluation = Evaluation(verbose=True, task_amount_limit=20, runs_per_configuration=1)

results = evaluation.evaluate_all(
    models=[
        GPTJRCModel(),
        # HuggingfaceModel("/mnt/storage2/hf_models/Llama-3.1-8B-Instruct")
    ],
    paradigms=[paradigm() for paradigm in paradigms],
    environments=envs,
    tasklist="Fever",
    _temperatures=[1.0, 0.7, 0.0],  # [0.0, 0.7],
)
print(results)
