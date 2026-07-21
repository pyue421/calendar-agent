import json
from pathlib import Path

from .bayesian_value_model import VALUE_IDS


PATH = Path(__file__).resolve().parents[1] / "data" / "calibration_questions.json"


class CalibrationService:
    def __init__(self):
        self.questions = json.loads(PATH.read_text(encoding="utf-8"))

    def participant_questions(self) -> list[dict]:
        return [{"question_id": q["question_id"], "prompt": q["prompt"],
                 "options": [{"id": o["id"], "label": o["label"]} for o in q["options"]]} for q in self.questions]

    def features(self, question_id: str) -> dict[str, list[float]]:
        question = next((q for q in self.questions if q["question_id"] == question_id), None)
        if not question:
            raise ValueError("Unknown calibration question")
        return {o["id"]: [o["features"].get(v, 0.0) for v in VALUE_IDS] for o in question["options"]}


CALIBRATION = CalibrationService()
