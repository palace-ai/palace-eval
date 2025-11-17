# PALACE

![img](https://img.shields.io/badge/python-3.13.9-orange)

A framework to evaluate the agentic capabilities of LLMs.

## Description

**PALACE** is an evaluation platform that can quantitatively assess the performance of AI agents across several different benchmarks.
It works both for locally-defined and executed agents as well as remote agents deployed via MCP.
The benchmark tasklists evaluate the capability of the agents in tasks requiring the use of tools, mainly web browsing, to gather the required information, as well as reason with that information to reach the user objective.
The framework allows to easily add new tasklists from HuggingFace and align them to the same format.

The framework is composed of two main parts: the evaluation part and agent engine part. In the future, the agent engine part will be detached from this project, and it will focus exclusively on evaluation.

The output of an evaluation run is a JSONL file containing all the collected information. This information can be used to build user-friendly results visualizations. Currently, an interactive web dashboard is available to get insights about the results (not part of this repository but may be added in the future).

![img](assets/readme_images/dashboard.png)

## Installation

**PALACE** is provided as a Python package. It can be downloaded and installed normally (it may be released on PyPI in the future).
After cloning the project with:

```bash
$ git clone https://gitlab.jrc.ec.europa.eu/jrc-projects/jrc-gpt/agents/agents-eval.git palace
```

you may install it with:

```bash
$ python3 -m pip install palace
```

It is recommended to install it into a virtual environment.

When you install it, all required dependencies should be downloaded automatically.

The `tasklist` folder is initially empty. To download the included benchmark tasklists run:

```bash
$ python3 -m palace.data_utils.download
```

You can also add your custom tasklists, by creating a `tasklists/custom/<tasklist_name>/tasks.json` file and a `tasklists/metadata/<tasklist_name>/info.json` file.

## Usage

The main entry point of this package is via its global CLI command `palace-run`. Simply type it in your terminal (be sure to be within the Python environment where the package is installed):

```bash
$ palace-run
```

This command should open up the main CLI, and you should be initially be presented with something like this:
![img](assets/readme_images/cli.png)

Subsequently, you will be prompted with a series of questions where you can configure the evaluation run. Use the up and down arrow keys to navigate the menu options, Space to select an option (for some choice you can select multiple options), and Enter to confirm the selection.
These are the current evaluation parameters:

- Agent type to test (local, remote, or both),
- If remote agents is selected, the URL of the MCP server where the agent is deployed,
- If remote agents is selected, the names of the remote agents to evaluate,
- If local agents is selected, the reasoning paradigms to evaluate,
- If local agents is selected, the LLMs to evaluate,
- If local agents is selected, whether you want to run the LLMs underlying the agents on the local machine (a high-memory GPU is required) or on GPT@JRC,
- If local agents is selected, the environments (set of tools) to evaluate, including remote MCP environments,
- The benchmark tasklists to use for the evaluation,
- Number of tasks to evaluate for each tasklist (this is to prevent extremely long testing times),
- Number of runs to perform for each configuration (it can be useful to lower the variance, since it's not deterministic),
- The name for the evaluation run.

After selecting all parameters, the evaluation run will start, and you will see the first configuration being evaluated:
![img](assets/readme_images/cli2.png)

The outputs of the evaluation are saved to `results/<evaluation_name>.jsonl`.

### MCP Server

The package comes with an MCP server that you can use to debug or test the application in case you don't have a ready MCP server to use. The pre-package MCP server only contains a web search tool and a fetch tool.

To start it, simply run the global command:

```bash
$ palace-mcpstart
```

on another terminal and leave it running.

## Containers

_(This is experimental and not advised.)_

You can build and run the images in the `images` folder as containers.

For example, to build the MCP server image, `cd` into the project root and run:

```bash
$ docker build -t mcp-server:latest -f images/mcp-server/Dockerfile .
```

And then,

```bash
$ docker run -d -p 8080:8080 mcp-server:latest
```

The MCP server will be ready to serve requests on port 8080.

## Support

If you have any issues, you can open an issue on GitLab if they are enabled, or you can contact me at massimiliano.altieri@ec.europa.eu.
