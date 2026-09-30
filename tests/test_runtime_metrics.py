from backend.app.models.base import process_ram_mb


def test_runtime_ram_metric_is_available_and_positive():
    value = process_ram_mb()
    assert value is not None and value > 0
