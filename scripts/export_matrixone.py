"""Offline migration preparation. Does not connect to a cloud service."""
import sys,csv,json,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quotepilot.store import open_db,seed_official
base=Path(__file__).resolve().parents[1]
con=open_db(base/'workspace/quotepilot.db');seed_official(con,base/'workspace/samples')
out=base/'workspace/matrixone_export';out.mkdir(exist_ok=True)
tables=['emails','rfq_headers','rfq_lines','line_evidence','costs','prices','historical','quotes','quote_items','audit_events','parse_issues','settings']
for table in tables:
    cur=con.execute('SELECT * FROM '+table)
    with (out/(table+'.csv')).open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow([x[0] for x in cur.description]);w.writerows(cur)
source=[]
for row in con.execute('SELECT * FROM source_files'):
    d=dict(row);blob=d.pop('content');(out/(d['id']+'.bin')).write_bytes(blob);source.append(d|{'catalog_file_id':None})
(out/'source_manifest.json').write_text(json.dumps(source,ensure_ascii=False,indent=2))
print('Prepared CSV + source bytes at',out)
print('UNVERIFIED: MatrixOne import; upload each source to MOI volume and fill real catalog_file_id')
con.close()
