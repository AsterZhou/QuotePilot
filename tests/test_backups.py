import hashlib,sqlite3
import pytest
from quotepilot.backups import snapshot,restore,inspect


def test_snapshot_restores_wal_rows_and_original_bytes(tmp_path):
    source=tmp_path/'source.db';backup=tmp_path/'backup.db';target=tmp_path/'restored.db'
    con=sqlite3.connect(source)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('CREATE TABLE source_files(id INTEGER PRIMARY KEY,content BLOB)')
    payload=b'%PDF original\x00\xff bytes'
    con.execute('INSERT INTO source_files VALUES(1,?)',(payload,));con.commit()
    meta=snapshot(source,backup)
    assert meta['tables']=={'source_files':1} and meta['integrity']=='ok'
    assert meta['sha256']==hashlib.sha256(backup.read_bytes()).hexdigest()
    restored=restore(backup,target,meta['sha256'])
    assert restored['tables']==meta['tables']
    with sqlite3.connect(target) as copy:assert copy.execute('SELECT content FROM source_files').fetchone()[0]==payload
    assert con.execute('SELECT COUNT(*) FROM source_files').fetchone()[0]==1
    with pytest.raises(FileExistsError):restore(backup,target,meta['sha256'])
    with pytest.raises(ValueError,match='SHA256'):restore(backup,tmp_path/'bad.db','0'*64)
    assert not (tmp_path/'bad.db').exists()
    con.close()


def test_non_sqlite_source_does_not_leave_incomplete_backup(tmp_path):
    source=tmp_path/'source.db';source.write_bytes(b'invalid sqlite')
    target=tmp_path/'backup.db'
    with pytest.raises(sqlite3.DatabaseError):snapshot(source,target)
    assert not target.exists()


def test_backup_api_production_requires_admin_and_contains_no_environment(tmp_path,monkeypatch):
    import server
    from fastapi.testclient import TestClient
    monkeypatch.setattr(server,'DB',tmp_path/'source.db')
    monkeypatch.setenv('QUOTEPILOT_ENV','production')
    monkeypatch.setenv('QUOTEPILOT_LOGIN_PASSWORD','test-password-long')
    monkeypatch.setenv('QUOTEPILOT_SESSION_SECRET','s'*40)
    monkeypatch.setenv('QUOTEPILOT_PUBLIC_URL','https://testserver')
    monkeypatch.setenv('QUOTEPILOT_PROVIDER','mock')
    with TestClient(server.app,base_url='https://testserver',client=('backup-test',51000)) as c:
        assert c.get('/api/admin/backup/download').status_code==401
        assert c.post('/auth/login',json={'password':'test-password-long'},headers={'origin':'https://testserver'}).status_code==200
        r=c.get('/api/admin/backup/download');assert r.status_code==200
        assert hashlib.sha256(r.content).hexdigest()==r.headers['X-Backup-SHA256']
        assert r.headers['X-Backup-Integrity']=='ok' and r.headers['Cache-Control']=='no-store'
        copy=tmp_path/'downloaded.db';copy.write_bytes(r.content)
        assert inspect(copy)['tables']['historical']>0
        assert b'test-password-long' not in r.content
