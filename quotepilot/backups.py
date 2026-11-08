"""Consistent SQLite snapshots, including source-file BLOBs; never seed/overwrite on restore."""
import hashlib,os,sqlite3,time
from datetime import datetime,timezone
from pathlib import Path


def inspect(path):
    with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as con:
        if con.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('SQLite完整性检查失败')
        names=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        tables={name:con.execute('SELECT COUNT(*) FROM "'+name.replace('"','""')+'"').fetchone()[0] for name in names}
        fk_errors=len(con.execute('PRAGMA foreign_key_check').fetchall())
    return {'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'bytes':Path(path).stat().st_size,
            'tables':tables,'foreign_key_errors':fk_errors,'integrity':'ok','created_at':datetime.now(timezone.utc).isoformat()}


def snapshot(source,destination):
    target=Path(destination)
    # Exclusively reserve the destination; never overwrite an existing backup.
    fd=os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    started=time.monotonic()
    def progress(status,remaining,total):
        if time.monotonic()-started>15:raise TimeoutError('备份超时，原数据库保持不变')
    try:
        with sqlite3.connect(Path(source).resolve().as_uri()+'?mode=ro',uri=True,timeout=1) as src:
            with sqlite3.connect(target) as dst:src.backup(dst,pages=64,progress=progress,sleep=.01)
        return inspect(target)
    except BaseException:
        target.unlink(missing_ok=True);raise


def restore(source,destination,expected_sha256):
    """Restore to a NEW path only. Caller stops service and selects that path separately."""
    meta=inspect(source)
    if meta['sha256']!=expected_sha256:raise ValueError('备份SHA256不匹配，拒绝恢复')
    if meta['foreign_key_errors']:raise ValueError('备份存在外键错误，需要人工检查')
    return snapshot(source,destination)
