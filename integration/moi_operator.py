"""MOI ordinary Python operator entry; local contract tested, cloud unverified.
Deploy quotepilot/ alongside this module, or package it as an operator dependency.
"""
import sqlite3
from quotepilot.store import SCHEMA
from quotepilot.pricing import batch_quote

def handle(workspace_id,sdk,input):
    # SDK deliberately unused: upstream MOI table nodes supply rows explicitly.
    con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row;con.executescript(SCHEMA)
    try:
        for table in ('costs','prices'):
            allowed={r[1] for r in con.execute('PRAGMA table_info('+table+')')}
            for row in input.get(table,[]):
                if set(row)-allowed:raise ValueError('未知字段：'+str(set(row)-allowed))
                keys=list(row)
                con.execute('INSERT INTO '+table+'('+','.join('"'+k+'"' for k in keys)+') VALUES('+','.join('?' for _ in keys)+')',tuple(row[k] for k in keys))
        return {'report':batch_quote(con,input['lines'],input['asof'],input.get('rate','0.20'),input.get('method','markup')),'runtime':'python_operator_contract','platform_verified':False}
    finally:con.close()
