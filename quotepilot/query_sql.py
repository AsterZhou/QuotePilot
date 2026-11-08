"""Introspected business schema and defense-in-depth SQLite SELECT execution."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3,time
import sqlglot
from sqlglot import exp
from sqlglot.optimizer.qualify import qualify

ALLOWED={
 'emails':{'email_id','filename','subject','sender','mail_date','imported_at'},
 'rfq_lines':{'id','email_id','source_rfq_no','part_number','description','quantity','unit','urgency','part_condition','mpn','deadline','product_scope','customer','source_kind','source_ref'},
 'historical':{'id','inquiry_no','rfq_no','inquiry_date','airline','urgency','line_no','part_number','description','quantity','unit','part_condition','product_scope','deadline','source_row'},
 'costs':{'part_number','description','product_scope','unit','inventory','warehouse','part_condition','standard_cost','avg_cost','last_purchase_price','currency','updated_at','source_row'},
 'prices':{'resource_id','part_number','supplier_code','supplier','condition','unit_price','currency','fx_to_cny','moq','lead_days','in_stock','certificate','quote_date','valid_until','status','source_row'},
 'quotes':{'id','created_at','status','version','rule_version'},
 'quote_items':{'quote_id','line_id','snapshot_json'},
}
GLOSSARY={
 '询价份数':'historical以COUNT(DISTINCT rfq_no)计；邮件需求须结合email_id和source_rfq_no，不能把明细行数当RFQ份数',
 '客户':'历史询价用historical.airline；新邮件需求用rfq_lines.customer，空白显示未提供',
 '紧急':'urgency代码AOG、URGENT、USR、WSP；代码原样保留',
 '正式报价':'quotes.status=approved表示人工确认的报价，不代表成交订单或收入',
 '未完成报价':'rfq_lines未关联任何已approved的quotes；经quote_items.line_id、quote_items.quote_id关联',
 '成交价':'当前没有真实订单、成交价、收款或销售事实表；需追问能否改用已审批报价或供应商参考报价',
 '供应商报价':'prices中的历史供应商资源；缺少单位，不能默认EA；是否有效须核对日期、件状、MOQ',
 '库存成本':'costs；standard_cost、avg_cost、last_purchase_price是不同口径，不是已完成销售价格',
 '截止':'deadline是RFQ截止日期，不是物流交货日期；没有订单截止字段',
 '时间':'historical.inquiry_date是历史询价时间；emails.mail_date是原邮件日期文本；rfq_lines没有created_at字段',
 '数量合计':'按unit分组，EA、IN、FT不得混加；价格按currency分开，不得混合币种求和/平均',
 '报价快照':'quote_items.snapshot_json含$.part_number,$.quantity,$.unit,$.condition,$.unit_quote_cny,$.line_total_cny；数值须CAST，不代表成交',
}
FUNCTIONS={'count','sum','avg','min','max','coalesce','nullif','substr','substring','strftime','date','datetime','julianday','round','abs','cast','json_extract','json_extract_scalar','lower','upper','trim','length','lag','lead','row_number','rank','dense_rank','if','iif','case','total','and','or','exists','like'}

class QueryRejected(ValueError):pass

# SQLGlot's SQLite STRFTIME node includes these normalized internal functions.
# They render back to STRFTIME; SQLite authorizer still checks runtime names.
FUNCTIONS.update({'time_to_str','ts_or_ds_to_timestamp','group_concat'})

@contextmanager
def readonly(db):
    con=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True,timeout=.2)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA query_only=ON')
    con.enable_load_extension(False)
    con.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH,16000)
    con.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,2_000_000)
    try:yield con
    finally:con.close()


def discover(db):
    tables={};relations=[]
    with readonly(db) as con:
        existing={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for table,allowed in ALLOWED.items():
            if table not in existing:continue
            cols=[dict(r) for r in con.execute('PRAGMA table_info("'+table+'")') if r['name'] in allowed]
            tables[table]={r['name']:r['type'] or 'TEXT' for r in cols}
            for r in con.execute('PRAGMA foreign_key_list("'+table+'")'):
                if r['table'] in ALLOWED:relations.append({'table':table,'column':r['from'],'target_table':r['table'],'target_column':r['to']})
    # SQLite's existing quote_items FK doesn't declare line_id; this is the application's documented logical join.
    if 'quote_items' in tables and 'rfq_lines' in tables:relations.append({'table':'quote_items','column':'line_id','target_table':'rfq_lines','target_column':'id','kind':'application_logical_join'})
    return {'tables':tables,'relations':relations,'business_terms':GLOSSARY,'database':'SQLite','orders_table_available':False,
            'allowed_functions':sorted(FUNCTIONS-{'time_to_str','ts_or_ds_to_timestamp','and','or','exists','like'})}


def validate(sql,schema,parameters,max_rows=100):
    if not isinstance(sql,str) or not 1<=len(sql)<=12000:raise QueryRejected('SQL长度无效')
    if len(parameters)>100 or any(isinstance(v,(dict,list)) or (isinstance(v,str) and len(v)>2000) for v in parameters):raise QueryRejected('查询参数超限')
    try:statements=sqlglot.parse(sql,read='sqlite')
    except Exception:raise QueryRejected('SQL语法无法解析')
    if len(statements)!=1 or not isinstance(statements[0],(exp.Select,exp.Union)):raise QueryRejected('只允许单条SELECT查询')
    tree=statements[0]
    if len(list(tree.walk()))>800:raise QueryRejected('SQL结构过于复杂')
    if any(isinstance(n,(exp.DDL,exp.DML,exp.Command,exp.Into,exp.Transaction)) for n in tree.walk()):raise QueryRejected('禁止数据或结构修改')
    if any(n.args.get('recursive') for n in tree.find_all(exp.With)):raise QueryRejected('不允许递归查询')
    if any(n.args.get('locks') for n in tree.find_all(exp.Select)):raise QueryRejected('不允许锁定查询')
    ctes={n.alias_or_name for n in tree.find_all(exp.CTE)}
    if len(ctes)>5 or len(list(tree.find_all(exp.Join)))>6:raise QueryRejected('关联数量超限')
    real_tables=set()
    for node in tree.find_all(exp.Table):
        if node.catalog or node.db:raise QueryRejected('不允许跨数据库访问')
        if node.name in ctes:continue
        if node.name not in schema['tables']:raise QueryRejected('查询表未获授权')
        real_tables.add(node.name)
    if not real_tables:raise QueryRejected('必须查询现有业务数据表')
    for node in tree.find_all(exp.Func):
        name=node.name.lower() if isinstance(node,exp.Anonymous) else node.sql_name().lower()
        if name not in FUNCTIONS:raise QueryRejected('查询函数未获授权：'+name)
    for node in tree.find_all(exp.Placeholder):
        if node.this:raise QueryRejected('仅支持位置参数')
    if len(list(tree.find_all(exp.Placeholder)))!=len(parameters):raise QueryRejected('参数数量不匹配')
    try:
        tree=qualify(tree,dialect='sqlite',schema=schema['tables'],validate_qualify_columns=True,identify=True)
    except Exception:raise QueryRejected('SQL包含不存在或不明确的字段')
    limit=tree.args.get('limit')
    if limit:
        expr=limit.expression
        if not isinstance(expr,exp.Literal) or not expr.is_int:raise QueryRejected('LIMIT须为固定整数')
        requested=int(expr.this)
        if requested<1:raise QueryRejected('返回行数无效')
        maximum=min(requested,max_rows)
    else:maximum=max_rows
    tree=tree.limit(maximum+1)
    return tree.sql(dialect='sqlite'),maximum,sorted(real_tables)


def execute(db,sql,parameters=(),max_rows=100,timeout_seconds=1.0):
    schema=discover(db)
    safe_sql,maximum,tables=validate(sql,schema,parameters,max_rows)
    started=time.monotonic();deadline=started+timeout_seconds
    with readonly(db) as con:
        def authorize(action,one,two,database,trigger):
            if action==sqlite3.SQLITE_SELECT:return sqlite3.SQLITE_OK
            if action==sqlite3.SQLITE_READ:
                return sqlite3.SQLITE_OK if database=='main' and one in schema['tables'] and (not two or two in schema['tables'][one]) else sqlite3.SQLITE_DENY
            if action==sqlite3.SQLITE_FUNCTION:return sqlite3.SQLITE_OK if (two or '').lower() in FUNCTIONS else sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_DENY
        con.set_authorizer(authorize)
        con.set_progress_handler(lambda:1 if time.monotonic()>deadline else 0,1000)
        try:
            cursor=con.execute(safe_sql,tuple(parameters));rows=[dict(r) for r in cursor.fetchmany(maximum+1)]
        except sqlite3.Error:
            raise QueryRejected('查询被只读权限、字段校验或执行时间限制拦截')
    truncated=len(rows)>maximum
    return {'rows':rows[:maximum],'columns':list(rows[0]) if rows else [],'sql':safe_sql,'sql_parameters':list(parameters),
            'source_tables':tables,'returned_records':min(len(rows),maximum),'truncated':truncated,
            'query_ms':round((time.monotonic()-started)*1000,2),'readonly':True,'row_limit':maximum,'timeout_seconds':timeout_seconds}
