from ai_gateway import _parse_with_repair


def test_parse_with_repair_recovers_from_non_json_provider_output():
    repair_prompts = []

    def generate_repair(prompt: str) -> str:
        repair_prompts.append(prompt)
        return """
        {
          "bullet_replacements": [
            {
              "match_anchor": "Managed supply chain operations",
              "replacement_text": "Led supply chain operations across regions"
            }
          ]
        }
        """

    payload = _parse_with_repair(
        "Original optimization task",
        "I cannot provide that response.",
        generate_repair,
    )

    assert payload["bullet_replacements"][0]["match_anchor"] == "Managed supply chain operations"
    assert len(repair_prompts) == 1
    assert "No JSON block found" in repair_prompts[0]
    assert "Original optimization task" in repair_prompts[0]
