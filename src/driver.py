import environments
from evaluation import Evaluation
from models import GPTJRCModel, HuggingfaceModel
from paradigms import SimpleReActParadigm

paradigms = [SimpleReActParadigm]
envs = [environments.MCPEnvironment]

evaluation = Evaluation(
    models=[
        GPTJRCModel(),
        # HuggingfaceModel("/mnt/storage2/hf_models/Llama-3.1-8B-Instruct")
    ],
    paradigms=[paradigm() for paradigm in paradigms],
    environments=[env() for env in envs],
    tasklist="gaia_tasks",
    verbose=False,
    # task_amount_limit=5,
)
evaluation.evaluate_all()
