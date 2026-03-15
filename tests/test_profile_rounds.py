import triageflow.cli as cli


def test_get_profile_round_fields():
    profile = {
        "rounds": [
            {"id": 0, "fields": ["a", "b"]},
            {"id": 1, "fields": ["c"]},
        ]
    }
    assert cli._get_profile_round_fields(profile, 0) == ["a", "b"]
    assert cli._get_profile_round_fields(profile, 1) == ["c"]
    assert cli._get_profile_round_fields(profile, 2) == []
