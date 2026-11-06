"""Deterministic, auditable natural-language query templates (NOT LLM NL2SQL)."""
from __future__ import annotations
import sqlite3

QUESTIONS={
 '每月询价趋势': """SELECT substr(inquiry_date,1,7) AS 月份,
 COUNT(DISTINCT rfq_no) AS 询价份数, COUNT(*) AS 物料行数
 FROM historical GROUP BY 1 ORDER BY 1""",
 '客户紧急询价排名': """SELECT COALESCE(NULLIF(airline,''),'未提供') AS 航空公司,
 COUNT(DISTINCT CASE WHEN urgency IN ('AOG','URGENT','USR','WSP') THEN rfq_no END) AS 紧急询价份数,
 COUNT(CASE WHEN urgency IN ('AOG','URGENT','USR','WSP') THEN 1 END) AS 紧急物料行数
 FROM historical GROUP BY 1 ORDER BY 紧急询价份数 DESC,紧急物料行数 DESC LIMIT 20""",
 '热门询价件号': """SELECT part_number AS 件号,COUNT(*) AS 物料行数,
 COUNT(DISTINCT rfq_no) AS 询价份数 FROM historical GROUP BY part_number
 ORDER BY 物料行数 DESC,件号 LIMIT 20""",
 '即将截止的询价': """SELECT rfq_no AS 询价号,airline AS 航空公司,part_number AS 件号,
 deadline AS 截止报价日期 FROM historical
 WHERE deadline >= ? AND deadline < date(?, '+7 days') ORDER BY deadline LIMIT 30"""
}

def run_query(con:sqlite3.Connection,name:str,asof:str='2026-09-01') -> list[dict]:
    if name not in QUESTIONS:raise ValueError('Only allowlisted queries are supported offline')
    params=(asof,asof) if name=='即将截止的询价' else ()
    return [dict(r) for r in con.execute(QUESTIONS[name],params).fetchall()]


def summary(con:sqlite3.Connection)->dict:
    one=lambda sql:con.execute(sql).fetchone()[0]
    return {'mails':one('SELECT count(*) FROM emails'),
            'mail_lines':one('SELECT count(*) FROM rfq_lines'),
            'history_lines':one('SELECT count(*) FROM historical'),
            'history_rfq_groups':one('SELECT count(DISTINCT rfq_no) FROM historical'),
            'cost_records':one('SELECT count(*) FROM costs'),
            'price_records':one('SELECT count(*) FROM prices')}
