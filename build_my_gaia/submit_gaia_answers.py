import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()


API_URL = "https://agents-course-unit4-scoring.hf.space"
USERNAME = "shabriri615"
ANSWERS_PATH = Path("gaia_answers.json")


def load_answers() -> list[dict]:
    """Load local answers and keep only fields required by the scoring API."""
    raw_answers = json.loads(ANSWERS_PATH.read_text(encoding="utf-8"))
    return [
        {
            "task_id": item["task_id"],
            "submitted_answer": item["submitted_answer"],
        }
        for item in raw_answers
    ]


def main() -> None:
    agent_code = os.getenv("GAIA_AGENT_CODE_URL", "").strip()
    if not agent_code:
        raise SystemExit(
            "Missing GAIA_AGENT_CODE_URL. Set it to your public Hugging Face Space code URL, "
            "for example: https://huggingface.co/spaces/shabriri615/your-space/tree/main"
        )

    payload = {
        "username": USERNAME,
        "agent_code": agent_code,
        "answers": load_answers(),
    }

    print(f"Submitting {len(payload['answers'])} answers for {USERNAME}")
    response = requests.post(f"{API_URL}/submit", json=payload, timeout=60)
    print("Status:", response.status_code)
    response.raise_for_status()
    print(json.dumps(response.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
