"""Re-analyze saved real SQLite query results, without repeating planning or fabricating rows."""
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from quotepilot.providers import GenesisProvider
from quotepilot.query_center import analyze,Intent

def main():
    root=Path('evidence/batch1');out=root/'closeout';out.mkdir(exist_ok=True)
    def one(name):
        saved=json.loads((root/(name+'.json')).read_text())['result']
        assert saved['status']=='completed'
        intent=Intent(action='query',title=saved['title'],explanation=saved['interpretation'])
        try:
            analysis,receipt=analyze(GenesisProvider(),saved['question'],intent,saved)
            result={'case':name,'status':analysis['status'],'analysis':analysis,'receipt':receipt,'source_query_response_id':saved['response_id']}
        except Exception as error:
            result={'case':name,'status':'failed','failure_type':type(error).__name__,'cause_type':type(error.__cause__).__name__,'receipt':getattr(error,'receipt',{}),'source_query_response_id':saved['response_id']}
        (out/('analysis_'+name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'case':name,'status':result['status'],'response_id':(result.get('receipt') or {}).get('response_id')},ensure_ascii=False),flush=True)
        return result
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(one,['supplier_reference','increasing_parts','followup']))
    return all(r['status']=='generated' for r in results)

if __name__=='__main__':raise SystemExit(0 if main() else 1)
