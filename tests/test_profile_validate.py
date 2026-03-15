import triageflow.cli as cli


def test_validate_profile_catches_round_fields_type():
    prof = {"profile_id": "x", "rounds": [{"id": 0, "fields": "bad"}]}
    errs = cli._validate_profile(prof)
    assert any("rounds[0].fields" in e for e in errs)


def test_validate_profile_requires_rounds():
    prof = {"profile_id": "x"}
    errs = cli._validate_profile(prof)
    assert any(e.startswith("rounds:") for e in errs)
