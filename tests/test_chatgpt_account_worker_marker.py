from pathlib import Path


def test_chatgpt_account_worker_marker_is_exact():
    marker = Path(__file__).with_name("chatgpt_account_worker_marker.txt")
    assert marker.read_text(encoding="utf-8") == "CHATGPT_ACCOUNT_WORKER_OK\n"
