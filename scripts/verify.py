"""One reproducible gate: exit nonzero on failure; unverified != passed."""
import sys,subprocess,json,platform,xml.etree.ElementTree as ET
from pathlib import Path
root=Path(__file__).resolve().parents[1];out=root/'evidence';out.mkdir(exist_ok=True)
result={'python':platform.python_version(),'groups':{},'unverified':['This offline command does not execute Genesis live calls; see evidence/live_20261105 for recorded real calls','MOI workflow / Python service not deployed','RFQ/cost/supplier MatrixOne primary-table migration not implemented; approved snapshot mirror is separate','Agent publication and judge access (not deployed)','General OCR remains unimplemented (targeted scan fixture failed); model extraction quality unverified']}
failed=False
for group in ('official','synthetic'):
    report=out/(group+'_junit.xml')
    p=subprocess.run([sys.executable,'-m','pytest','-q','-m',group,'--junitxml='+str(report)],cwd=root,text=True,capture_output=True)
    (out/(group+'_test_log.txt')).write_text(p.stdout+p.stderr,encoding='utf-8')
    counts={key:0 for key in ('tests','failures','errors','skipped')}
    if report.exists():
        for suite in ET.parse(report).getroot().iter('testsuite'):
            for k in counts:counts[k]+=int(suite.get(k,0))
    counts['passed']=counts['tests']-counts['failures']-counts['errors']-counts['skipped'];counts['exit_code']=p.returncode
    result['groups'][group]=counts;failed|=p.returncode!=0
    print(group,counts)
for item in result['unverified']:print('UNVERIFIED:',item)
# Engineering gate must retain failed format expectations, not just unit successes.
probe_out=out/'format_acceptance.json'
probe=subprocess.run([sys.executable,str(root/'scripts/acceptance_probe.py'),'--project',str(root),'--fixtures',str(root/'tests/acceptance_fixtures'),'--out',str(probe_out)],cwd=root,text=True,capture_output=True)
(out/'format_acceptance.log').write_text(probe.stdout+probe.stderr,encoding='utf-8')
result['unit_regression_passed']=not failed
if probe_out.exists():
    result['format_acceptance']=json.loads(probe_out.read_text())['summary']
else:result['format_acceptance']={'status':'未执行或未产出结果','exit_code':probe.returncode}
failed=failed or probe.returncode!=0
print('FORMAT ACCEPTANCE:',result['format_acceptance'])
print('PUBLIC / PLATFORM: 未验证；不能判定完整参赛验收通过')
result['passed']=not failed
result['competition_ready']=False
(out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
sys.exit(1 if failed else 0)
