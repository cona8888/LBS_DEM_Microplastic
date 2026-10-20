"""Role adapter for the frozen Stage26d v1 evaluator and legacy YADE runner schema."""

import evaluate_stage26d_adaptive_prefilter_v1 as implementation


ORIGINAL_LOAD_JSON = implementation.load_json


def load_json_with_stage26d_role(path):
    payload = ORIGINAL_LOAD_JSON(path)
    if isinstance(payload, dict) and "trials" in payload:
        payload = dict(payload)
        payload["trials"] = [dict(row, record_type=row.get("stage26d_role", row["record_type"])) for row in payload["trials"]]
    return payload


def main():
    implementation.load_json = load_json_with_stage26d_role
    implementation.main()


if __name__ == "__main__":
    main()
