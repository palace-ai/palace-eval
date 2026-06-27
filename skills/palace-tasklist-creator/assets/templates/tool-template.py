"""Custom tool template — one tool per file.

Place in environment/tools/ and register in info.json:
  "custom_tools": ["tools/my_tool.py"]
"""

import json

# Required: OpenAI function-calling schema
TOOL = {
    "name": "my_tool",
    "description": "Describe what this tool does — this is shown to the agent.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "The query to look up"}
        },
        "required": ["query"],
    },
}

# Optional: request context values from vivarium's namespaced pool
# Available keys: env.container, env.id, env.task_id, env.group, env.container_id,
#                 run.objective, run.model_url, run.model_key, run.model_name,
#                 run.notifications, run.delegate_fn, server.env_registry, spec.id
CONTEXT = {
    "container": "env.container",
}


async def execute(args, context):
    """Execute the tool. MUST be async.

    Args:
        args: dict of parameter values from the agent's tool call
        context: dict of resolved CONTEXT values. Common entries:
            context["container"]: Container object with async API:
                await container.read(path) → str
                await container.write(path, bytes)
                await container.exec(cmd) → (exit_code, output)

    Returns:
        {"content": "result string"} on success
        {"error": "error message"} on failure
    """
    container = context["container"]
    data = json.loads(await container.read("/data/db.json"))
    result = data.get(args["query"])
    if result is None:
        return {"error": f"Not found: {args['query']}"}
    return {"content": json.dumps(result, indent=2)}
