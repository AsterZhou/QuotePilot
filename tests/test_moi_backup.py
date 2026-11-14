import hashlib
import json

import httpx
import pytest

from quotepilot.store import open_db
from quotepilot.provenance import install


@pytest.fixture
def backup(tmp_path):
    path = tmp_path / 'private.sqlite3'
    con = open_db(path)
    install(con)
    con.close()
    return path


@pytest.mark.parametrize('fault',[None,'upload_error','attach_error','wrong_bytes','redirect','http200_error'])
def test_catalog_archive_needs_attached_verified_bytes(tmp_path, backup, fault):
    from quotepilot.moi_backup import archive, download

    calls = []
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    def handle(request):
        action = request.url.path.split('/')[-1]
        calls.append(action)
        if action == 'upload':
            assert backup.read_bytes() in request.content
            if fault=='upload_error':
                return httpx.Response(200,json={'code':'Err','data':{}})
            return httpx.Response(200,json={'code':'OK','data':{'file_id':'id-archive'}})
        if action=='create':
            assert json.loads(request.content)=={'volume_id':42,'file_ids':['id-archive']}
            return httpx.Response(200,json={'code':'Err' if fault=='attach_error' else 'OK','data':None})
        assert action=='download' and json.loads(request.content)=={'file_id':'id-archive'}
        if fault=='redirect':
            return httpx.Response(302,headers={'Location':'https://another-host.example'})
        if fault=='http200_error':
            return httpx.Response(200,json={'code':'Err'})
        return httpx.Response(200,content=b'corrupt' if fault=='wrong_bytes' else backup.read_bytes())
    with httpx.Client(transport=httpx.MockTransport(handle),base_url='https://api.moi.matrixorigin.cn/v5/') as c:
        if fault:
            with pytest.raises((ValueError,httpx.HTTPError)):
                archive(c,backup,digest,42)
            assert calls==({'upload_error':['upload'],'attach_error':['upload','create']}.get(fault,['upload','create','download']))
        else:
            receipt=archive(c,backup,digest,42)
            assert calls==['upload','create','download']
            assert receipt=={'file_id':'id-archive','volume_id':42,'sha256':digest,'bytes':backup.stat().st_size}
            target=tmp_path/'restored.db'
            download(c,receipt['file_id'],digest,target)
            assert target.read_bytes()==backup.read_bytes()
            with pytest.raises(FileExistsError):
                download(c,receipt['file_id'],digest,target)


def test_download_mismatch_never_exposes_partial_database(backup,tmp_path):
    from quotepilot.moi_backup import download
    target=tmp_path/'restored.db'
    with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,content=b'bad data')),base_url='https://api.moi.matrixorigin.cn/v5/') as c:
        with pytest.raises(ValueError):
            download(c,'id-archive',hashlib.sha256(backup.read_bytes()).hexdigest(),target)
    assert not target.exists()
    assert not list(tmp_path.glob('.qp-*'))


def test_wrong_archive_hash_fails_before_network_call(backup):
    from quotepilot.moi_backup import archive
    def no_network(request):
        pytest.fail('unexpected remote request')
    with httpx.Client(transport=httpx.MockTransport(no_network)) as c:
        with pytest.raises(ValueError):
            archive(c,backup,'0'*64,42)
