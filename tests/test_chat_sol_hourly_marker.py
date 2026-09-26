from pathlib import Path


def test_chat_sol_hourly_marker_exact_content() -> None:
    marker = Path(__file__).with_name("chat_sol_hourly_marker.txt")
    assert marker.read_text(encoding="utf-8") == "CHAT_SOL_HOURLY_OK\n"
