from triageflow.profile import get_round_fields


def test_get_profile_round_fields():
    profile = {
        "rounds": [
            {"id": 0, "fields": ["a", "b"]},
            {"id": 1, "fields": ["c"]},
        ]
    }
    assert get_round_fields(profile, 0) == ["a", "b"]
    assert get_round_fields(profile, 1) == ["c"]
    assert get_round_fields(profile, 2) == []
