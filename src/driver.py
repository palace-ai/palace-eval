import environments
from evaluation import Evaluation
from models import GPTJRCModel, HuggingfaceModel
from paradigms import SimpleReActParadigm

paradigms = [SimpleReActParadigm]
envs = [
    environments.MCPEnvironment(mcp_server="local"),
    # environments.MCPEnvironment(mcp_server="aloha"),
]

evaluation = Evaluation(
    name="eval2", verbose=False, task_amount_limit=20, runs_per_configuration=5
)

results = evaluation.evaluate_all(
    models=[
        GPTJRCModel(),
        # HuggingfaceModel("/mnt/storage2/hf_models/Llama-3.1-8B-Instruct")
    ],
    paradigms=[paradigm() for paradigm in paradigms],
    environments=envs,
    tasklist="gaia_tasks",
    _temperatures=[1.0, 0.7, 0.0],  # [0.0, 0.7],
)
print(results)
