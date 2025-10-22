import json
import os
import re

import pymupdf
import requests

from palace.models.openai_compatible_model import OpenAICompatibleModel
from palace.utils.paths import PROJECT_ROOT


def fetch_pdf_content(url: str, limit_length: int = None):
    try:
        response = requests.get(url)
        response.raise_for_status()

        with pymupdf.open(stream=response.content, filetype="pdf") as pdf:
            # retrieve pdf title from metadata
            title = pdf.metadata.get("title", "No title").strip()

            # retrieve full pdf text
            full_text = ""
            for page in pdf:
                full_text += page.get_text()

            # trim full_text length to `limit_length` if set
            if limit_length is not None and limit_length < len(full_text):
                full_text = full_text[:limit_length] + "..."

            return {"title": title, "full_text": full_text}
    except Exception as e:
        return {"url": url, "error": str(e)}


def main():
    system_prompt_judge = """The user will give you a question, the correct answer to that question, and an answer that was provided by someone.
Your goal is to determine whether the provided answer correctly answers the question, using the correct answer as a reference.
The user will give you this information using this exact format:

```question
The question.
```

```correct_answer
The correct answer to the question, which you have to use as reference to determine whether the provided answer ir correct.
```

```provided_answer
The provided answer, which you have to determine whether it correctly answers the question.
```

Your output must match this exact format:

```reasoning
All your reasoning and observations go here, including your motivations for learning towards correct or incorrect.
```

```verdict
Either Correct or Incorrect. No other character can be here.
```
"""

    system_prompt_tester = """Answer the following question without searching the web and without being too verbose:
    
{question}
"""

    system_prompt_generate_question = """The user will upload a text file. You have to read that text and give him an advanced and difficult question that cannot be answered by an LLM if it doesn't have access to the full text.
The question should have a discursive answer, that is impossible to know without having the reference text.
Then, also provide the correct answer, verbatim references to the portions of text that answer that question, and a difficulty score for the question.

You have to format your output as follows (including the fenced code blocks with language specifier, and don't add any extra formatting):
```question
Place your question here
```

```answer
Place the correct answer to the question here
```

```references
Place the verbatim references to the portions of text that answer the question here
```

```difficulty
Place the difficulty score for the question here, as an integer from 0 to 100
```
"""

    QUESTIONS_PER_FILE = 1
    TASKLIST_NAME = "LegisRetrieval"

    # initialize model
    model = OpenAICompatibleModel("openai/gpt-oss-120b")

    # get list of files
    files = [
        {
            "title": "European AI in Science Strategy",
            "url": "https://research-and-innovation.ec.europa.eu/document/download/c1afd7d0-ff65-4f84-be48-b0e0949596c5_en?filename=COM_2025_724_1_EN_ACT_part1_v8.pdf",
        }
    ]

    tasks_path = PROJECT_ROOT / "tasklists" / "automated" / TASKLIST_NAME / "tasks.json"
    task_files_path = (
        PROJECT_ROOT / "tasklists" / "automated" / TASKLIST_NAME / "task_files"
    )
    metadata_path = (
        PROJECT_ROOT / "tasklists" / "metadata" / TASKLIST_NAME / "task_files"
    )

    tasks = []

    for file in files:
        # extract pdf
        title = file["title"]
        full_text = fetch_pdf_content(file["url"])["full_text"]

        # generate tasks
        for i in range(QUESTIONS_PER_FILE):
            # create task id
            task_id = f"{TASKLIST_NAME}_{title.replace(' ', '_')}_{i + 1}"

            # generate question, complete with answer, references, and difficulty score
            complete_question = model.generate(
                [
                    {"role": "system", "content": system_prompt_generate_question},
                    {
                        "role": "user",
                        "content": f"ATTACHMENT ({title}):\n\n{full_text}",
                    },
                ]
            )
            print(complete_question)

            # use regex to extract question, answer, references, and difficulty score
            pattern = r"```.*?\n(.*?)\n```"
            task = re.findall(pattern, complete_question, re.DOTALL)
            task = {
                "id": task_id,
                "objective": task[0],
                "expected": task[1],
                "references": task[2],
                "difficulty": task[3],
            }

            # the task is registered only if the models fails to generate after this many tries
            MAX_ATTEMPS = 5

            count = 0
            correct = False
            while not correct and count < MAX_ATTEMPS:
                count += 1
                print(f"Attempt #{count}")

                # generate answer to the question without access to the file
                answer = model.generate(
                    [{"role": "user", "content": task["objective"]}]
                )
                print(answer)

                # if judge says it's incorrect (needs access to files in order to be answered), add it to the dataset
                judgement = model.generate(
                    [
                        {"role": "system", "content": system_prompt_judge},
                        {
                            "role": "user",
                            "content": f"QUESTION\n{task['objective']}\n\nCORRECT ANSWER\n{task['expected']}\n\nPROVIDED ANSWER\n{answer}",
                        },
                    ]
                )
                print(judgement)
                try:
                    judgement = re.findall(r"```verdict\n(.*?)\n```", judgement)
                    assert len(judgement) == 1
                    judgement = judgement[0].lower()
                    assert judgement in ["correct", "incorrect"]
                    correct |= judgement == "correct"
                except AssertionError:  # no verdict or incorrect syntax, just redo it
                    count -= 1
                    continue

            if judgement == "incorrect":
                tasks.append(task)

    # save task and task file (pdf)
    os.makedirs(os.path.dirname(tasks_path), exist_ok=True)
    with open(tasks_path, "w", encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=4)


if __name__ == "__main__":
    main()
