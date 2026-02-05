import csv
import json
from pathlib import Path
from typing import Any

from palace.utils.paths import PROJECT_ROOT


def load_multiline_csv(file_path: str) -> list[dict[str, Any]]:
    """
    Load the responses CSV file with robust handling of multiline entries.

    Args:
        file_path: Path to the CSV file

    Returns:
        List of dictionaries containing the parsed data
    """
    data = []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            # Use csv.DictReader with proper quoting handling
            csv_reader = csv.DictReader(file, quoting=csv.QUOTE_ALL)

            for row_num, row in enumerate(csv_reader, 1):
                # Clean up any potential issues with the data
                cleaned_row = {}
                for key, value in row.items():
                    if value is not None:
                        # Remove any leading/trailing whitespace and handle encoding
                        cleaned_row[key.strip()] = value.strip()
                    else:
                        cleaned_row[key.strip()] = ""

                data.append(cleaned_row)

                # Print progress for large files
                if row_num % 100 == 0:
                    print(f"Processed {row_num} rows...")

    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return []

    print(f"Successfully loaded {len(data)} rows from {file_path}")
    return data


def main():
    DATA_FILE = (
        Path(__file__).parent / "responses_OpenAI-DeepResearch_vs_ARI_2025-05-15.csv"
    )

    tasks: list[dict] = []

    # load csv file with multiline entries
    data = load_multiline_csv(str(DATA_FILE))

    for i, item in enumerate(data):
        question, baseline_answer = item["question"], item["baseline_answer"]
        tasks.append(
            {
                "id": f"DeepConsult-{i}",
                "objective": question,
                "expected": baseline_answer,
            }
        )

    # save tasks and metadata
    tasklist_path = PROJECT_ROOT / "tasklists" / "DeepConsult"
    tasklist_path.mkdir(parents=True, exist_ok=True)
    json.dump(tasks, open(tasklist_path / "tasks.json", "w"), indent=2)
    print(f"Saved {len(tasks)} tasks to {tasklist_path / 'tasks.json'}")
    json.dump(
        {
            "name": "DeepConsult",
            "id": "PALACE/DeepConsult",
            "[deprecating in favor of 'original'] type": "[deprecating in favor of 'original'] custom",
            "original": True,
            "config": None,
            "split": None,
            "category": "Report Generation",
        },
        open(tasklist_path / "info.json", "w"),
        indent=2,
    )
    print(f"Saved metadata to {tasklist_path / 'info.json'}")


if __name__ == "__main__":
    main()
