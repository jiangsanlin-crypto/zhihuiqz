from pathlib import Path


def test_work_gpt6_emergency_marker() -> None:
    marker = Path(__file__).with_name("work_gpt6_emergency_marker.txt")
    assert marker.read_text(encoding="utf-8") == "WORK_GPT6_EMERGENCY_OK\n"
