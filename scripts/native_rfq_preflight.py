"""Read-only MOI diagnostics. Emits only allowlisted fields; never creates resources."""
import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from quotepilot.moi_sql import BASE
from quotepilot.native_workflow import identifier


def inspect(workspace, workflow, key):
    root = '/workflow/v2/workflow-apps/' + identifier(workflow)
    headers = {'X-Workspace-ID': identifier(workspace)}
    if key:
        headers['X-API-Key'] = key
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'workspace_id': workspace,
              'workflow_id': workflow, 'credential_present': bool(key), 'requests': []}
    for path in (root, root + '/executions', '/compute-resources', '/compute-resource-specs/management-permission'):
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            r = client.get(BASE + path, headers=headers)
        try:
            envelope = r.json()
        except ValueError:
            envelope = {}
        entry = {'method':'GET', 'path':path, 'http':r.status_code, 'code':envelope.get('code'),
                 'request_id':r.headers.get('x-request-id'), 'trace_id':r.headers.get('x-trace-id')}
        report['requests'].append(entry)
        if not r.is_success:
            if r.status_code in (401,403):
                break
            continue
        data = envelope.get('data')
        if path == root:
            w = data['workflow']
            entry['workflow'] = {k:w[k] for k in ('id','status','execution_mode','available_actions',
                'latest_workflow_version_id','latest_version','trigger_summary','compute_resource_bindings')
                if k in w}
            entry['field_ids'] = [f.get('field_id') for f in w.get('runtime_fields',{}).get('fields',[])]
        elif path.endswith('/executions'):
            entry['total'] = data.get('total')
        elif path == '/compute-resources' and isinstance(data,list):
            entry['visible_resources'] = [{k:x[k] for k in ('id','status','type') if k in x} for x in data]
        elif isinstance(data,dict):
            entry['can_manage_specs'] = data.get('can_manage_specs')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--workspace',required=True)
    p.add_argument('--workflow',required=True)
    p.add_argument('--prompt',action='store_true')
    a = p.parse_args()
    key = (getpass.getpass('MOI PAT: ') if a.prompt else
           (os.getenv('MOI_API_KEY') or os.getenv('GENESIS_ACCESS_TOKEN') or os.getenv('GENESIS_API_KEY')))
    result = inspect(a.workspace,a.workflow,key)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if all(r['http']==200 and r['code']=='OK' for r in result['requests']) else 1)
