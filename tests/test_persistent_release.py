"""Cold start, cutover and verified recovery of an existing business database."""
import hashlib
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest


@pytest.fixture
def original(tmp_path):
    from quotepilot.store import open_db, audit
    from quotepilot.provenance import install

    db = tmp_path / 'archived.sqlite3'
    con = open_db(db)
    try:
        install(con)
        with con:
            audit(con, 'backup_test', 'proof', {'sample': True})
    finally:
        con.close()
    return db


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_protected_cold_start_never_boots_the_seed(tmp_path, monkeypatch):
    import deploy.entrypoint as entry
    from quotepilot.persistent import check_database

    target = tmp_path / 'live.db'
    monkeypatch.setenv('QUOTEPILOT_RELEASE_DEMO', '1')
    monkeypatch.setenv('QUOTEPILOT_PERSISTENT_MOUNT', str(tmp_path))
    monkeypatch.setenv('QUOTEPILOT_DB', str(target))
    import server
    from fastapi.testclient import TestClient
    monkeypatch.setattr(server, 'DB', target)
    def start(*args, **kwargs):
        with TestClient(server.app):
            pass
    with patch('quotepilot.persistent.check_mount'), patch('uvicorn.run', side_effect=start), patch('deploy.release_seed.install_seed') as seed:
        with pytest.raises(ValueError, match='业务库'):
            entry.main()
        seed.assert_not_called()
        assert not target.exists()
        with pytest.raises(ValueError, match='业务库'):
            check_database(target)


def test_asgi_direct_start_checks_before_opening_empty_file(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import server

    target = tmp_path / 'absent.db'
    monkeypatch.setenv('QUOTEPILOT_PERSISTENT_MOUNT', str(tmp_path))
    monkeypatch.setattr(server, 'DB', target)
    with patch('quotepilot.persistent.check_mount'), pytest.raises(ValueError, match='业务库'):
        with TestClient(server.app):
            pass
    assert not target.exists()


def test_mount_check_requires_real_writable_covering_mount(tmp_path):
    from quotepilot.persistent import check_mount

    root = tmp_path / 'with space'
    root.mkdir()
    escaped = str(root).replace(' ', r'\040')
    rows = '1 0 0:1 / / rw - overlay overlay rw\n'
    marker = f'2 1 0:2 / {escaped} rw,relatime - ext4 /dev/test rw\n'
    target = root / 'data.db'
    for dest, mount, listing in [
        (target, root, rows), (target, Path('/'), rows),
        (tmp_path / 'outside.db', root, rows + marker),
        (target, root, rows + marker.replace('rw,relatime', 'ro,relatime')),
        (root / 'sub' / 'data.db', root, rows + marker + f'3 2 0:4 / {escaped}/sub rw - tmpfs tmpfs rw\n'),
    ]:
        with pytest.raises(ValueError):
            check_mount(dest, mount, listing)
    check_mount(target, root, rows + marker)


@pytest.mark.parametrize('damage', ['wrong_hash','corrupt_blob','broken_audit','empty_file','other_schema','active_wal'])
def test_bad_snapshot_never_leaves_a_live_file(tmp_path, original, damage):
    from quotepilot.persistent import install_backup
    if damage == 'corrupt_blob':
        with sqlite3.connect(original) as c:
            c.execute("INSERT INTO source_files(id,filename,sha256,content,kind,dataset) VALUES('s','s.eml',?,?,'eml','test')",('0'*64,b'source'))
    if damage == 'broken_audit':
        with sqlite3.connect(original) as c:
            c.execute('DROP TRIGGER protect_audit_chain_update')
            c.execute("UPDATE audit_chain SET event_hash='bad'")
    if damage == 'empty_file':
        original.write_bytes(b'')
    if damage == 'other_schema':
        original.unlink()
        with sqlite3.connect(original) as c:
            c.execute('CREATE TABLE unrelated(id)')
    if damage == 'active_wal':
        Path(str(original) + '-wal').write_bytes(b'journal')
    target = tmp_path / 'live.sqlite3'
    key = '0'*64 if damage == 'wrong_hash' else digest(original)
    with pytest.raises((ValueError,sqlite3.DatabaseError)):
        install_backup(original, target, key)
    assert not target.exists()
    assert not list(tmp_path.glob('.qp-restore-*'))


def test_parallel_recovery_publishes_exactly_one_complete_copy(tmp_path, original):
    from concurrent.futures import ThreadPoolExecutor
    from quotepilot.persistent import install_backup, check_database
    expected = digest(original)
    target = tmp_path / 'live.db'
    with ThreadPoolExecutor(2) as pool:
        outcomes = [future.exception() for future in [pool.submit(install_backup, original, target, expected) for _ in range(2)]]
    assert sum(x is None for x in outcomes)==1
    assert sum(isinstance(x, FileExistsError) for x in outcomes)==1
    assert digest(target)==expected
    check_database(target)
    assert not list(tmp_path.glob('.qp-restore-*'))


@pytest.mark.parametrize('suffix',['-wal','-shm','-journal'])
def test_orphan_sidecars_are_never_attached_to_restored_database(tmp_path, original, suffix):
    from quotepilot.persistent import install_backup
    target=tmp_path/'new.db'
    Path(str(target)+suffix).write_bytes(b'old')
    with pytest.raises(FileExistsError):
        install_backup(original,target,digest(original))
    assert not target.exists()


def test_existing_free_demo_keeps_the_original_seed_path(tmp_path, monkeypatch):
    import deploy.entrypoint as entry
    target = tmp_path/'demo.db'
    monkeypatch.setenv('QUOTEPILOT_RELEASE_DEMO','1')
    monkeypatch.delenv('QUOTEPILOT_PERSISTENT_MOUNT',raising=False)
    monkeypatch.setenv('QUOTEPILOT_DB',str(target))
    with patch('deploy.release_seed.install_seed') as seed, patch('uvicorn.run') as serve:
        entry.main()
        seed.assert_called_once_with(Path('/app/release-demo.sqlite'),target)
        serve.assert_called_once()


def test_real_asgi_restart_reads_the_same_audit_chain(tmp_path, original, monkeypatch):
    from fastapi.testclient import TestClient
    import server
    from quotepilot.persistent import install_backup
    from quotepilot.store import audit

    target = tmp_path/'live.db'
    install_backup(original,target,digest(original))
    monkeypatch.setenv('QUOTEPILOT_PERSISTENT_MOUNT', str(tmp_path))
    monkeypatch.setenv('QUOTEPILOT_RELEASE_DEMO', '1')
    monkeypatch.setattr(server,'DB',target)
    with patch('quotepilot.persistent.check_mount'):
        with TestClient(server.app) as client:
            assert client.get('/healthz').status_code==200
            with server.database() as con, con:
                audit(con,'persistence_marker','first_start',{'expected':True})
            first=client.get('/api/audit/verify').json()
        with TestClient(server.app) as client:
            assert client.get('/api/audit/verify').json()==first
            assert first['valid'] and first['checked']==2
