from pathlib import Path


def test_chatgpt_work_auto_marker():
    marker = Path(__file__).with_name("chatgpt_work_auto_marker.txt")
    assert marker.read_text(encoding="utf-8") == "CHATGPT_WORK_AUTO_OK\n"
