import sqlite3
import pytest
from orchestrator.state_store import StateStore


def test_connection_closes_after_success_and_error(tmp_path):
    store=StateStore(str(tmp_path/'db'))
    with store.conn() as db:
        db.execute('SELECT 1')
    with pytest.raises(sqlite3.ProgrammingError,match='closed'):
        db.execute('SELECT 1')
    with pytest.raises(RuntimeError):
        with store.conn() as failed:
            failed.execute('BEGIN IMMEDIATE')
            failed.execute("INSERT INTO issue_intake VALUES('o/r',1,'g','awaiting_planner','{}',NULL,NULL,NULL,'a','a')")
            raise RuntimeError('interrupted transaction')
    with pytest.raises(sqlite3.ProgrammingError,match='closed'):
        failed.execute('SELECT 1')
    # A different process/client can acquire the write lock immediately;
    # the failed transaction did not leave a partial queue item.
    other=StateStore(store.path)
    with other.conn() as db:
        db.execute('BEGIN IMMEDIATE')
        assert db.execute('SELECT COUNT(*) FROM issue_intake').fetchone()[0]==0
