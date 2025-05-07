import questionary
from agents_eval.environments import (
    AssistantEnvironment,
    IsolatedEnvironment,
    IsolatedEnvironmentWithInterpreter,
    IsolatedEnvironmentWithLetterCount,
    MCPEnvironment,
)
from agents_eval.evaluation import Evaluation
from agents_eval.models import GPTJRCModel, HuggingfaceModel
from agents_eval.paradigms import SimpleReActParadigm


def main():
    print("""
        ▗           ▜ 
▀▌▛▌█▌▛▌▜▘▛▘▄▖█▌▌▌▀▌▐ 
█▌▙▌▙▖▌▌▐▖▄▌  ▙▖▚▘█▌▐▖
  ▄▌                  
""")
    print("Welcome to the Agents Evaluation CLI!")
    print("This is a simple evaluation script for the Agents Evaluation framework.")
    print(
        "It will evaluate the performance of different models and paradigms on various environments."
    )
    print("Please make sure you have the required dependencies installed.")
    print("You can find the documentation at <...>")
    print("If you have any questions, please contact us at <...>")
    print("")

    _PARADIGMS = [SimpleReActParadigm()]
    _MODELS = [
        "llama-3.3-70b-instruct",
        "mistral-small-3-24b",
        "gpt-4o",
        "qwen-coder-2.5-instruct",
    ]
    _ENVIRONMENTS = [
        AssistantEnvironment(),
        IsolatedEnvironment(),
        IsolatedEnvironmentWithInterpreter(),
        IsolatedEnvironmentWithLetterCount(),
        MCPEnvironment(mcp_server="local"),
        MCPEnvironment(mcp_server="aloha"),
    ]
    _TASKLISTS = ["AssistantBench", "GAIA", "SimpleQA"]

    paradigm = questionary.select(
        "Select Reasoning Paradigm:",
        choices=[p.name for p in _PARADIGMS],
    ).ask()
    paradigm = next(p for p in _PARADIGMS if p.name == paradigm)

    model = questionary.select(
        "Select Model:",
        choices=_MODELS,
        default="llama-3.3-70b-instruct",
    ).ask()

    local_mode = questionary.select(
        "Local Mode:",
        choices=["True", "False"],
        default="False",
    ).ask()
    local_mode = True if local_mode == "True" else False

    environment = questionary.select(
        "Select Environment:",
        choices=[e.name for e in _ENVIRONMENTS],
    ).ask()
    environment = next(e for e in _ENVIRONMENTS if e.name == environment)

    tasklist = questionary.select(
        "Select Tasklist:",
        choices=_TASKLISTS,
        default="GAIA",
    ).ask()

    verbose = questionary.select(
        "Verbose Mode:",
        choices=["True", "False"],
        default="False",
    ).ask()
    verbose = True if verbose == "True" else False

    task_amount_limit = questionary.select(
        "Limit the number of tasks:",
        choices=["5", "10", "20", "50"],
        default="20",
    ).ask()
    task_amount_limit = int(task_amount_limit)

    runs_per_configuration = questionary.select(
        "Runs Per Configuration:",
        choices=["1", "2", "3", "5"],
        default="5",
    ).ask()
    runs_per_configuration = int(runs_per_configuration)

    evaluation = Evaluation(
        verbose=verbose,
        task_amount_limit=task_amount_limit,
        runs_per_configuration=runs_per_configuration,
    )

    results = evaluation.evaluate_all(
        # BUG local models follow a different naming convention. try to abstract the exact name of a model. maybe use a dict
        # for instance the same model is called Llama-3.1-8B-Instruct locally but llama-3.3-70b-instruct for GPT@JRC
        models=[
            HuggingfaceModel(f"/mnt/storage2/hf_models/{model}")
            if local_mode
            else GPTJRCModel(model)
        ],
        paradigms=[paradigm],
        environments=[environment],
        tasklist=tasklist,
    )
    print(results)


if __name__ == "__main__":
    main()
