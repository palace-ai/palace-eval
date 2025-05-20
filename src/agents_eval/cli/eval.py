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
from agents_eval.paradigms import (
    ActParadigm,
    PlanAndExecuteParadigm,
    ReActParadigm,
    ReflectionParadigm,
)


def main():
    print("""
          
--<>--<>--<>--<>--<>--<>--<>--<>--<>--<>-- ┏━━━━━━━━━━━▲━━━━━━━━━━━┓ --<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--
--<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--           ▗           ▜   --<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--
--<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--   ▀▌▛▌█▌▛▌▜▘▛▘▄▖█▌▌▌▀▌▐   --<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--
--<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--   █▌▙▌▙▖▌▌▐▖▄▌  ▙▖▚▘█▌▐▖  --<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--
--<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--     ▄▌                    --<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--
--<>--<>--<>--<>--<>--<>--<>--<>--<>--<>-- ┗━━━━━━━━━━━▼━━━━━━━━━━━┛ --<>--<>--<>--<>--<>--<>--<>--<>--<>--<>--

╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│  Welcome to the Agents Evaluation CLI!                                                                       │
│  This is a simple evaluation script for the Agents Evaluation framework.                                     │
│  It will evaluate the performance of different models and paradigms on various environments.                 │
│  Please make sure you have the required dependencies installed.                                              │
│  You can find the documentation at https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/agents/agents-eval.  │
│  If you have any questions, please contact us at massimiliano.altieri@ec.europa.eu.                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
""")

    _PARADIGMS = [
        ActParadigm(),
        ReActParadigm(),
        PlanAndExecuteParadigm(),
        ReflectionParadigm(),
    ]
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
    _TASKLISTS = ["AssistantBench", "Fever", "GAIA", "HLE", "HotpotQA", "SimpleQA"]

    default_paradigms = [ReActParadigm().name]
    paradigm = questionary.checkbox(
        "Select Reasoning Paradigm:",
        choices=[
            questionary.Choice(p.name, checked=p.name in default_paradigms)
            for p in _PARADIGMS
        ],
        # default=ReActParadigm().name,
    ).ask()
    paradigms = [p for p in _PARADIGMS if p.name in paradigm]
    if len(paradigms) == 0:
        raise ValueError("No paradigms selected")

    models = questionary.checkbox(
        "Select Model:",
        choices=_MODELS,
        # default="llama-3.3-70b-instruct",
    ).ask()
    if len(models) == 0:
        raise ValueError("No models selected")

    local_mode = questionary.select(
        "Local Mode:",
        choices=["True", "False"],
        default="False",
    ).ask()
    local_mode = True if local_mode == "True" else False

    # use questionary to select one or multiple environments to evaluate (checkboxes)
    environments = questionary.checkbox(
        "Select Environments:",
        choices=[e.name for e in _ENVIRONMENTS],
    ).ask()
    environments = [e for e in _ENVIRONMENTS if e.name in environments]
    if len(environments) == 0:
        raise ValueError("No environments selected")

    tasklists = questionary.checkbox(
        "Select Tasklist:",
        choices=_TASKLISTS,
    ).ask()
    if len(tasklists) == 0:
        raise ValueError("No tasklists selected")

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

    name = questionary.text(
        "Name of the evaluation run:",
        default="eval",
    ).ask()

    evaluation = Evaluation(
        name=name,
        verbose=verbose,
        task_amount_limit=task_amount_limit,
        runs_per_configuration=runs_per_configuration,
    )

    evaluation.evaluate_all(
        # BUG local models follow a different naming convention. try to abstract the exact name of a model. maybe use a dict
        # for instance the same model is called Llama-3.1-8B-Instruct locally but llama-3.3-70b-instruct for GPT@JRC
        models=[
            HuggingfaceModel(f"/mnt/storage2/hf_models/{model}")
            if local_mode
            else GPTJRCModel(model)
            for model in models
        ],
        paradigms=paradigms,
        environments=environments,
        tasklists=tasklists,
    )


if __name__ == "__main__":
    main()
