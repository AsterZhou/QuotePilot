import httpx,pytest
from quotepilot.native_workflow import MOIWorkflowClient

def test_disabled_definition_is_not_a_verified_run(monkeypatch):
 monkeypatch.setenv('MOI_API_KEY','TEST_ONLY');monkeypatch.setenv('MOI_WORKSPACE_ID','TEST_WORKSPACE')
 requests=[]
 def answer(r):
  requests.append(r.method);return httpx.Response(200,json={'code':'OK','data':{'workflow':{'id':'test-wf','status':'disabled','execution_summary':{'total_executions':0}}}})
 c=MOIWorkflowClient(httpx.MockTransport(answer));s=c.status('test-wf')
 assert s['definition_exists'] and not s['native_execution_verified']
 with pytest.raises(ValueError,match='未就绪'):c.start('test-wf','SYNTHETIC-RUN')
 assert requests==['GET','GET']

def test_native_workflow_path_validated(monkeypatch):
 monkeypatch.setenv('MOI_API_KEY','TEST_ONLY');monkeypatch.setenv('MOI_WORKSPACE_ID','TEST_WORKSPACE')
 with pytest.raises(ValueError,match='ID'):MOIWorkflowClient().status('../other')
