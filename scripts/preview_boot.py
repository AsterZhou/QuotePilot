import sys,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1];os.chdir(root)
deps=root/'tmp/preview-deps'
print('Preparing real Python service:',sys.version.split()[0],flush=True)
if not (deps/'.ready').exists():
 deps.mkdir(parents=True,exist_ok=True)
 env={**os.environ,'PYTHONPATH':str(root/'tmp/pip-bootstrap')}
 subprocess.run([sys.executable,'-m','pip','install','--target',str(deps),'-r','requirements.txt'],env=env,check=True)
 (deps/'.ready').touch()
os.environ['PYTHONPATH']=str(deps);sys.path.insert(0,str(deps))
import runpy
runpy.run_path('scripts/interactive_preview.py',run_name='__main__')
