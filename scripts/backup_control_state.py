"""Create a verified SQLite backup without reading configuration or credentials."""
import argparse
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file() or destination.exists() or source == destination:
        raise ValueError('source must exist and destination must be new')
    fd, temporary = tempfile.mkstemp(prefix='.control-backup-', dir=destination.parent)
    os.close(fd)
    try:
        with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)) as original:
            copied = sqlite3.connect(temporary)
            try:
                original.backup(copied)
                if copied.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                    raise RuntimeError('backup integrity check failed')
                required = {'events','operation_claims','recovery_audit','issue_intake','blocker_observations',
                            'planning_publications','timeout_observations','timeout_audit','control_requests'}
                tables = {row[0] for row in copied.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if not required <= tables:
                    raise RuntimeError('not a complete control-state database')
            finally:
                copied.close()
        # Publish without replacing a concurrently created backup. Both paths
        # are on the same filesystem. mkstemp ensures restrictive permissions.
        with open(temporary, 'rb') as stream:
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    finally:
        os.unlink(temporary)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    try:
        backup(args.source, args.destination)
    except (OSError, ValueError, sqlite3.Error, RuntimeError):
        print('BACKUP_FAILED')
        raise SystemExit(1)
    print('BACKUP_VERIFIED')


if __name__ == '__main__':
    main()
