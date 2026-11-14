"""Offline installation of a sealed QuotePilot backup and guarded production startup."""
import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import re
import sqlite3
import tempfile

from .provenance import verify_audit


def check_mount(database, mount, mountinfo=None):
    root = Path(mount).resolve(strict=True)
    db = Path(database).resolve()
    if root == Path('/') or not root.is_dir() or not db.is_relative_to(root) or db == root:
        raise ValueError('业务库必须位于指定持久盘目录内')
    if mountinfo is None:
        mountinfo = Path('/proc/self/mountinfo').read_text()
    covering = []
    for line in mountinfo.splitlines():
        mount_data, fs_data = line.split(' - ', 1)
        fields = mount_data.split()
        path = Path(re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), fields[4]))
        if db.is_relative_to(path):
            covering.append((path, fields[5].split(','), fs_data.split()[0]))
    if covering:
        path, options, fs_type = max(covering, key=lambda row: len(row[0].parts))
        if path == root and 'rw' in options and fs_type not in ('overlay', 'tmpfs', 'ramfs') and os.access(db.parent, os.W_OK):
            return
    raise ValueError('业务库访问路径缺少指定的可写持久盘挂载')


def check_database(database):
    database = Path(database)
    if not database.is_file() or database.stat().st_size == 0:
        raise ValueError('业务库缺失或为空，请向新路径恢复已核验的完整备份')
    with closing(sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)) as con:
        con.row_factory = sqlite3.Row
        con.execute('BEGIN')
        names = {row[0] for row in con.execute("SELECT name FROM sqlite_schema WHERE type='table'")}
        required = {'emails', 'rfq_lines', 'source_files', 'audit_events', 'audit_chain'}
        if not required <= names:
            raise ValueError('缺少 QuotePilot 业务库结构')
        if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or con.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('业务库完整性或外键校验失败')
        audit = verify_audit(con)
        if not audit['valid']:
            raise ValueError('业务库审计链校验失败')
        for row in con.execute('SELECT sha256,content FROM source_files'):
            if hashlib.sha256(row['content']).hexdigest() != row['sha256']:
                raise ValueError('业务库原件摘要不一致')


def check_configured_database(database):
    mount = os.environ.get('QUOTEPILOT_PERSISTENT_MOUNT')
    if mount:
        check_mount(database, mount)
        check_database(database)


def sidecars(path):
    return [Path(str(path) + suffix) for suffix in ('-wal', '-shm', '-journal')]


def install_backup(source, destination, expected_sha256):
    """Publish a *standalone* backup at a new path. The running DB is never replaced."""
    source, destination = Path(source), Path(destination)
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('备份 SHA-256 无效')
    if any(os.path.lexists(path) for path in sidecars(source)):
        raise ValueError('请使用独立整库备份，源文件存在 SQLite 辅助文件')
    target_files = [destination, *sidecars(destination)]
    if any(os.path.lexists(path) for path in target_files):
        raise FileExistsError('目标位置已有数据库或 SQLite 辅助文件')
    with tempfile.NamedTemporaryFile(prefix='.qp-restore-', dir=destination.parent, delete=False) as stage:
        temporary = Path(stage.name)
    try:
        digest = hashlib.sha256()
        with source.open('rb') as backup, temporary.open('wb') as stage:
            for chunk in iter(lambda: backup.read(1024 * 1024), b''):
                digest.update(chunk)
                stage.write(chunk)
            stage.flush()
            os.fsync(stage.fileno())
        if digest.hexdigest() != expected_sha256:
            raise ValueError('备份 SHA-256 不匹配')
        check_database(temporary)
        if any(os.path.lexists(path) for path in sidecars(destination)):
            raise FileExistsError('目标位置已有 SQLite 辅助文件')
        os.link(temporary, destination)
        directory = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        temporary.unlink(missing_ok=True)
        for path in sidecars(temporary):
            path.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='将已校验的 QuotePilot 整库备份恢复至全新路径')
    parser.add_argument('source')
    parser.add_argument('destination')
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    install_backup(args.source, args.destination, args.sha256)
    print('恢复完成，SHA-256、原件、外键及审计链已核对')
