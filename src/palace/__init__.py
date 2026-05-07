def __getattr__(name):
    if name == "evaluate":
        from .entrypoints.palace_run import evaluate
        return evaluate
    raise AttributeError(f"module 'palace' has no attribute {name!r}")
