def __getattr__(name):
    if name == "Evaluation":
        from .evaluation.orchestrator import Evaluation
        return Evaluation
    if name == "evaluate":
        from .evaluation.orchestrator import evaluate
        return evaluate
    raise AttributeError(f"module 'palace' has no attribute {name!r}")
