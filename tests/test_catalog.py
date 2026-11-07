"""Catalog browsing preserves source data and the existing admin boundary."""
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import server
    original=server.DB
    server.DB=tmp_path_factory.mktemp('catalog')/'test.db'
    try:
        with TestClient(server.app) as c:yield c
    finally:server.DB=original

@pytest.mark.parametrize('kind,total', [('historical',249),('prices',342),('costs',163)])
def test_catalog_matches_overview_and_source_workbook(client,kind,total):
    first=client.get('/api/catalog/'+kind,params={'limit':25}).json()
    second=client.get('/api/catalog/'+kind,params={'limit':25,'offset':25}).json()
    assert first['total']==second['total']==total
    assert len(first['rows'])==len(second['rows'])==25
    assert first['rows']!=second['rows']
    assert first['source_files'][0]['dataset']=='official_sample'
    source=client.get('/api/sources/'+first['source_files'][0]['id']+'/download')
    assert source.status_code==200 and source.content.startswith(b'PK')
    assert all(row['source_row'] for row in first['rows'])

def test_search_is_literal_and_never_changes_data(client):
    found=client.get('/api/catalog/prices',params={'search':'PN-0001'}).json()
    assert found['rows'] and all(row['part_number']=='PN-0001' for row in found['rows'])
    for query in ["' OR 1=1 --",'%', '_', '\\']:
        assert client.get('/api/catalog/prices',params={'search':query}).json()['rows']==[]
    assert client.get('/api/catalog/prices').json()['total']==342
    assert client.get('/api/catalog/source_files').status_code==422
    assert client.get('/api/catalog/prices?limit=101').status_code==422

def test_mail_lineage_and_active_mode(client):
    assert all(row['dataset']=='official_sample' for row in client.get('/api/emails').json())
    r=client.get('/api/integration').json()
    assert r['active_provider']=='mock' and not r['genesis_configured']

def test_new_catalog_requires_admin(client,monkeypatch):
    monkeypatch.setenv('QUOTEPILOT_ENV','production')
    for kind in ['historical','prices','costs']:
        assert client.get('/api/catalog/'+kind).status_code==401

def test_notice_tracks_actual_provider(monkeypatch):
    from quotepilot.security import deployment_notice
    monkeypatch.setenv('QUOTEPILOT_EPHEMERAL_DEMO','1')
    monkeypatch.setenv('QUOTEPILOT_PROVIDER','mock')
    assert 'Mock' in deployment_notice()
    monkeypatch.setenv('QUOTEPILOT_PROVIDER','genesis')
    assert 'Mock' not in deployment_notice() and 'Genesis' in deployment_notice()
