import os
import sqlite3
import pytest
from orchestrator.state_store import StateStore
from scripts.backup_control_state import backup


def test_backup_includes_wal_and_does_not_replace_existing_file(tmp_path):
    source=tmp_path/'source.db'
    store=StateStore(str(source))
    # Hold a WAL connection so copying just the database file would be unsafe.
    with store.conn() as db:
        store.enqueue('d','test',{'number':80})
        target=backup(source,tmp_path/'backup.db')
    with sqlite3.connect(target) as db:
        assert db.execute('SELECT delivery_id FROM events').fetchone()[0]=='d'
    assert os.stat(target).st_mode & 0o777 == 0o600
    with pytest.raises(ValueError): backup(source,target)
    assert source.exists()


def test_invalid_source_never_creates_successful_backup(tmp_path):
    with pytest.raises(ValueError): backup(tmp_path/'absent',tmp_path/'backup')
    source=tmp_path/'unrelated.db'
    sqlite3.connect(source).close()
    with pytest.raises(RuntimeError,match='complete control-state'):
        backup(source,tmp_path/'backup')
    assert not (tmp_path/'backup').exists()
    assert not list(tmp_path.glob('.control-backup-*'))
