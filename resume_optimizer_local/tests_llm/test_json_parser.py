from json_parser import parse_replacement_payload


def test_parse_replacement_payload_unwraps_common_result_wrapper():
    raw = """
    {
      "result": {
        "summary_replacement": {
          "match_anchor": "Original summary paragraph",
          "replacement_text": "Updated summary paragraph"
        }
      }
    }
    """

    payload = parse_replacement_payload(raw)

    assert payload["summary_replacement"]["match_anchor"] == "Original summary paragraph"
    assert payload["summary_replacement"]["replacement_text"] == "Updated summary paragraph"


def test_parse_replacement_payload_normalizes_optimized_sections_shape():
    raw = """
    {
      "optimized_sections": [
        {
          "section": "bullet",
          "current_text": "Managed supply chain operations",
          "optimized_text": "Led supply chain operations across regions"
        },
        {
          "section": "skills",
          "current_text": "Excel, SQL",
          "optimized_text": "Excel, SQL, Tableau"
        }
      ]
    }
    """

    payload = parse_replacement_payload(raw)

    assert payload["bullet_replacements"] == [
        {
            "match_anchor": "Managed supply chain operations",
            "replacement_text": "Led supply chain operations across regions",
        }
    ]
    assert payload["skills_replacements"] == [
        {
            "match_anchor": "Excel, SQL",
            "replacement_text": "Excel, SQL, Tableau",
        }
    ]
