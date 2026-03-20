import json
import os

from mcp.types import TextContent

from palace.mcp_utils.mcp_client import call_tool
from palace.models.api_model import APIModel
from palace.utils.constants import OPENAI_LIKE_API_BASE_URL
from palace.utils.paths import PACKAGE_ROOT, TASKLISTS_PATH
from palace.utils.printing import loading
from palace.utils.secrets import ALOHA_STAGING_TOKEN, OPENAI_LIKE_API_KEY

SCOPUS_MCP_URL = "http://localhost:8000/sse"

# load research topics from json file
with open(
    PACKAGE_ROOT / "data_utils" / "scopus_dataset" / "research_topics_small.json"
) as f:
    research_topics = json.load(f)

# initialize papers as an empty dict
papers = {
    subject: {field: [] for field in fields}
    for subject, fields in research_topics.items()
}

# retrieve field-related papers and populate the dict
with loading() as ld:
    for subject, fields in research_topics.items():
        ld.status(f"Retrieving {subject}-related papers...")
        for field in fields:
            response = call_tool(
                SCOPUS_MCP_URL,
                "scopus_search_query",
                {
                    "api_query": f"KEY({field}) AND PUBYEAR > 2020 AND OPENACCESS(0) AND PUBLISHER(Elsevier)",
                    "return_fields": ["title", "doi", "date", "authors"],
                },
                ALOHA_STAGING_TOKEN,
            )
            content = response.content[0]
            if isinstance(content, TextContent) and content.text:
                for paper in json.loads(content.text):
                    papers[subject][field].append(paper)

# initialize model for question-answer pair generation
assert OPENAI_LIKE_API_BASE_URL is not None, (
    "OPENAI_LIKE_API_BASE_URL is not set in the environment variables."
)
model = APIModel("gpt-4o", OPENAI_LIKE_API_BASE_URL, OPENAI_LIKE_API_KEY)

# for each paper, generate the question-answer pair and put it in the dict
count = 0
with loading() as ld:
    for subject, subject_papers in papers.items():
        for field, field_papers in subject_papers.items():
            for p, paper in enumerate(field_papers):
                count += 1
                try:
                    response = call_tool(
                        SCOPUS_MCP_URL,
                        "get_paper_text_from_doi",
                        {"doi": paper["doi"]},
                        ALOHA_STAGING_TOKEN,
                    )
                    content = response.content[0]
                    if not isinstance(content, TextContent) or not content.text:
                        continue
                    full_text = content.text[:300000]
                    generated_text = model.generate(
                        [
                            {
                                "role": "system",
                                "content": """You will be given the full text of a scientific paper (in XML format but try to extract the relevant text parts), and will be prompted to generate a question pair that requires the knowledge of that paper in order to be answered. The generated question must be such that it cannot be answered without knowing the content of the provided paper, but it should also be general and self-contained enough on its own, without making references to the paper. For instance, it can't contain stuff like 'how do the authors ...'. For instance, this question would not be allowed: 'What specific technique do the authors suggest could enable quantum advantage in genetic merit prediction beyond raw matrix acceleration?'. An example of allowed question is: 'What are three distinct contributions that Hamiltonian simulation could make to improving membrane-based resource recovery from agricultural waste streams?' or 'Which quantum algorithm is considered suitable for solving low-rank linear systems specifically in the context of estimating genetic merits in large-scale animal breeding?'. After the question, also include the answer to that question. Make the answer as tight and blunt as possible. If possible, generate questions that have a definitive and blunt answer. For instance, for question 'Which quantum algorithm is considered suitable for solving low-rank linear systems specifically in the context of estimating genetic merits in large-scale animal breeding?', the answer should be something like 'HHL algorithm'. Try to avoid verbose answers. Your response must consist of exactly two lines of text: one with the question, and one with the answer, such as:
```<question here>
<answer here>```
Nothing else can be in your response.""",
                            },
                            {
                                "role": "user",
                                "content": f"Write a question-answer pair that requires information contained in the following paper in order to be answered.\n\n\n{full_text}",
                            },
                        ]
                    )
                    ld.status(
                        f"Generating question-answer pairs ({count}/{len(field_papers) * len(subject_papers) * len(papers)})"
                    )
                    question, answer = generated_text.split("\n")
                    papers[subject][field][p]["question"] = question
                    papers[subject][field][p]["answer"] = answer

                except Exception as e:
                    print(f"There was an error for paper {paper}:\n{e}")
                    continue


# save the dataset to file
with open(
    PACKAGE_ROOT / "data_utils" / "scopus_dataset" / "scopus_dataset.json", "w"
) as f:
    json.dump(papers, f, indent=4)

# then, convert the created dataset to the usual tasklist format
tasks = []
for subject, subject_papers in papers.items():
    for field, field_papers in subject_papers.items():
        for p, paper in enumerate(field_papers):
            task = {
                "id": f"Scopus_{p}",
                "objective": paper["question"],
                "expected": paper["answer"],
                "difficulty": "",
                "attachment": "",
            }
            tasks.append(task)

# save the tasklist
tasklist_path = TASKLISTS_PATH / "Scopus"
os.makedirs(tasklist_path, exist_ok=True)

with open(tasklist_path / "tasks.json", "w") as f:
    json.dump(tasks, f, indent=4)
with open(tasklist_path / "info.json", "w") as f:
    json.dump({"name": "Scopus", "task_type": "QA"}, f, indent=4)
