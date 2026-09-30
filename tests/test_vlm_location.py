from backend.app.services.local_vlm import validate_component_location


def test_accepts_normalized_component_box():
    assert validate_component_location({"found": True, "box": [0.1, 0.2, 0.5, 0.7]}) == (0.1, 0.2, 0.5, 0.7)
    assert validate_component_location({"found": True, "box": [464, 270, 660, 591]}) == (0.464, 0.27, 0.66, 0.591)


def test_rejects_missing_or_malformed_location():
    assert validate_component_location({"found": False, "box": None}) is None
    assert validate_component_location({"found": True, "box": [0.4, 0.1, 0.2, 0.8]}) is None
    assert validate_component_location({"found": True, "box": [0, 0, 1, 1]}) is None
    assert validate_component_location({"found": True, "box": [False, 0.1, 0.4, 0.4]}) is None
    assert validate_component_location({"found": True, "box": [0, 0, float("nan"), 0.5]}) is None
    assert validate_component_location({"found": True, "box": [0, 0, 1001, 0.5]}) is None
    assert validate_component_location([0.1, 0.2, 0.3, 0.4]) is None
