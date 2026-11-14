"""Archive a sealed SQLite backup in an existing MOI Catalog volume and verify readback."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import httpx

from .moi_sql import BASE
from .persistent import install_backup


def api_data(response):
    response.raise_for_status()
    obj = response.json()
    if obj.get('code') not in (200, 'OK'):
        raise ValueError('MOI 未确认文件操作成功')
    return obj.get('data')


def readback(client, file_id, expected_hash, output=None, expected_size=None):
    digest = hashlib.sha256()
    received = 0
    with client.stream('POST', 'catalog/file/download', json={'file_id': file_id}, follow_redirects=False) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=1024 * 1024):
            received += len(chunk)
            if expected_size is not None and received > expected_size:
                raise ValueError('云端文件超出原备份长度')
            digest.update(chunk)
            if output is not None:
                output.write(chunk)
    if digest.hexdigest() != expected_hash or (expected_size is not None and received != expected_size):
        raise ValueError('云端备份字节未通过 SHA-256 和长度校验')


def archive(client, source, expected_hash, volume_id):
    if type(volume_id) is not int or volume_id <= 0:
        raise ValueError('需要有效的既有 MOI 卷 ID')
    with tempfile.TemporaryDirectory() as directory:
        sealed = Path(directory) / 'checked.sqlite3'
        install_backup(source, sealed, expected_hash)
        with sealed.open('rb') as data:
            files = {'file': (f'quotepilot-{expected_hash}.sqlite3', data, 'application/octet-stream')}
            result = api_data(client.post('catalog/file/upload', files=files, follow_redirects=False))
        file_id = (result or {}).get('file_id')
        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError('MOI 没有返回有效文件 ID')
        api_data(client.post('catalog/file/create', json={'volume_id': volume_id, 'file_ids': [file_id]}, follow_redirects=False))
        size = sealed.stat().st_size
        readback(client, file_id, expected_hash, expected_size=size)
    return {'file_id': file_id, 'volume_id': volume_id, 'sha256': expected_hash, 'bytes': size}


def download(client, file_id, expected_hash, destination):
    target = Path(destination)
    if os.path.lexists(target):
        raise FileExistsError('恢复目标已存在')
    with tempfile.TemporaryDirectory(dir=target.parent) as directory:
        raw = Path(directory) / 'download.sqlite3'
        with raw.open('xb') as data:
            readback(client, file_id, expected_hash, output=data)
        install_backup(raw, target, expected_hash)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    save = actions.add_parser('archive')
    save.add_argument('source', type=Path)
    save.add_argument('--sha256', required=True)
    save.add_argument('--volume-id', type=int, required=True)
    restore = actions.add_parser('restore')
    restore.add_argument('file_id')
    restore.add_argument('destination', type=Path)
    restore.add_argument('--sha256', required=True)
    args = parser.parse_args()
    key = os.getenv('MOI_API_KEY') or os.getenv('GENESIS_ACCESS_TOKEN') or os.getenv('GENESIS_API_KEY')
    workspace = os.getenv('MOI_WORKSPACE_ID')
    if not workspace or not key:
        parser.error('需要既有 MOI 工作区和服务端凭据')
    headers = {'X-Workspace-ID': workspace, 'X-API-Key': key}
    with httpx.Client(base_url=BASE + '/', headers=headers, timeout=60, follow_redirects=False) as client:
        if args.action == 'archive':
            print(json.dumps(archive(client, args.source, args.sha256, args.volume_id)))
        else:
            download(client, args.file_id, args.sha256, args.destination)
            print('整库已下载并校验，已恢复至新路径')


if __name__ == '__main__':
    main()
