import environments
from evaluation import EvaluationV2
from models import GPTJRCModel, HuggingfaceModel
from paradigms import SimpleReActParadigm

paradigms = [SimpleReActParadigm]
envs = [environments.MCPEnvironment(mcp_server="aloha")]

evaluation = EvaluationV2(verbose=True)

evaluation.evaluate_all(
    models=[
        GPTJRCModel(),
        # HuggingfaceModel("/mnt/storage2/hf_models/Llama-3.1-8B-Instruct")
    ],
    paradigms=[paradigm() for paradigm in paradigms],
    environments=envs,
    tasklist="gaia_tasks",
)