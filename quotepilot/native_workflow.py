"""Client for MOI AI Studio one-shot workflow deployments."""
import os
import re
from pathlib import Path

import httpx
import yaml

from .moi_sql import BASE


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value):
        raise ValueError('无效 MOI ID')
    return value


class MOIWorkflowClient:
    def __init__(self, transport=None):
        self.key = (os.getenv('MOI_API_KEY') or os.getenv('GENESIS_ACCESS_TOKEN')
                    or os.getenv('GENESIS_API_KEY'))
        self.workspace = os.getenv('MOI_WORKSPACE_ID')
        self.transport = transport
        if not self.key or not self.workspace:
            raise ValueError('MOI工作流需要服务器密钥及工作区ID')

    def request(self, method, path, body=None):
        with httpx.Client(timeout=40, transport=self.transport, follow_redirects=False) as client:
            response = client.request(method, BASE + path, json=body, headers={
                'X-API-Key': self.key, 'X-Workspace-ID': self.workspace,
            })
        try:
            obj = response.json()
        except ValueError:
            obj = {}
        if not isinstance(obj, dict):
            obj = {}
        if response.is_error or obj.get('code') != 'OK':
            # Only expose protocol metadata. Platform messages can echo source text or headers.
            code = str(obj.get('code', 'unknown'))
            trace = response.headers.get('x-request-id', '')
            def safe(s):
                return s if re.fullmatch(r'[\w.-]{1,100}', s) and self.key not in s else 'unknown'
            raise ValueError(f'MOI HTTP {response.status_code} / {safe(code)} / request_id {safe(trace)}')
        return obj['data']

    def workflow_path(self, wid):
        return '/workflow/v2/workflow-apps/' + identifier(wid)

    def definition(self, wid):
        w = self.request('GET', self.workflow_path(wid))['workflow']
        if w.get('id') != wid:
            raise ValueError('工作流回执ID不匹配')
        return w

    def status(self, wid):
        w = self.definition(wid)
        return {'workflow_id': wid, 'status': w['status'], 'available_actions': w.get('available_actions', []),
                'execution_summary': w.get('execution_summary', {}), 'definition_exists': True,
                'native_execution_verified': False, 'note': '定义状态由 MOI 返回；作业另行验收'}

    def prepare(self, wid, run_ref):
        identifier(run_ref)
        w = self.definition(wid)
        if w.get('status') != 'ready':
            raise ValueError('工作流未就绪：' + str(w.get('status')))
        if 'available_actions' in w and 'run' not in w['available_actions']:
            raise ValueError('部署当前未提供 run 操作，请核对启用状态')
        expected = (Path(__file__).resolve().parents[1] / 'integration/rfq_native.yaml').read_text()
        deployed = w.get('dsl_yaml')
        if not isinstance(deployed,str) or len(deployed)>100_000:
            raise ValueError('部署没有返回可核对的 RFQ DSL')
        if w.get('execution_mode') != 'one_shot' or yaml.safe_load(deployed) != yaml.safe_load(expected):
            raise ValueError('部署模式或 DSL 与本地 RFQ 定义不一致，请核对部署版本')
        values = {}
        bound = False
        for f in w.get('runtime_fields', {}).get('fields', []):
            if f.get('bind_to') == 'vars.run_ref':
                values[identifier(f['field_id'])] = run_ref
                bound = True
            elif f.get('field_id') == 'run_ref' and not f.get('bind_to'):
                values['run_ref'] = run_ref
            elif f.get('required'):
                raise ValueError('部署包含未识别的必填运行字段')
        if not bound:
            raise ValueError('运行表单缺少 vars.run_ref 绑定')
        return {'values': values, 'trigger_now': True}

    def submit(self, wid, payload):
        data = self.request('POST', self.workflow_path(wid) + '/executions', payload)
        run = data['workflow_run']
        identifier(run.get('execution_id'))
        if run.get('workflow_id') != wid:
            raise ValueError('启动回执工作流ID不匹配')
        return data

    def start(self, wid, run_ref):
        return self.submit(wid, self.prepare(wid, run_ref))

    def run_path(self, wid, eid):
        return self.workflow_path(wid) + '/executions/' + identifier(eid)

    def execution(self, wid, eid):
        obj = self.request('GET', self.run_path(wid, eid))['execution']
        if obj.get('execution_id') != eid or obj.get('workflow_id') != wid:
            raise ValueError('执行回执ID不匹配')
        return obj

    def result(self, wid, eid):
        data = self.request('GET', self.run_path(wid, eid) + '/result')
        obj = data['result']
        if obj.get('execution_id') != eid or obj.get('workflow_id') != wid:
            raise ValueError('执行结果ID不匹配')
        return data

    def node(self, wid, eid, key):
        data = self.request('GET', self.run_path(wid, eid) + '/nodes/root.' + identifier(key))
        if data['node'].get('node_key') != 'root.' + key:
            raise ValueError('节点回执路径不匹配')
        return data['run']
