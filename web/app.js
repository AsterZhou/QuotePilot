/* QuotePilot 报价室 / Local contest workspace v0.4
   Deterministic API-backed UI. No fake AI model completions.
*/
'use strict';
const $ = (q,root=document)=>root.querySelector(q);
const $$ = (q,root=document)=>[...root.querySelectorAll(q)];
const esc = v => String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => Number(n||0).toLocaleString('zh-CN');
const money = n => {const [whole,fraction='']=String(n??'0').split('.');return '¥ '+whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+fraction.padEnd(2,'0').slice(0,2)};
const state={page:'overview',emails:[],lines:[],allLines:[],selected:new Set(),emailId:'',inboxSearch:'',inboxPage:0,quotePage:0,quoteSearch:'',quoteFilter:'all',quoteEmail:'all',quoteReport:null,quoteReq:null,insight:'每月询价趋势',overview:null,chart:null,filters:{asof:'2026-09-20',method:'markup',rate:20}};
let toastTimer;
function toast(text){const n=$('#toast');n.textContent=text;n.classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>n.classList.remove('show'),3700)}
async function api(path,opts={}){const r=await fetch(path,{cache:'no-store',...opts});if(!r.ok){let d={};try{d=await r.json()}catch{}const fieldNames={source_rfq_no:'来源询价号',part_number:'件号',quantity:'数量',unit:'单位',actor:'复核人',reason:'确认说明',description:'技术描述',condition:'件状',lines:'所选需求行'};
const details=Array.isArray(d.detail)?d.detail.map(issue=>{const field=issue.loc?.at(-1);return (fieldNames[field]||field||'字段')+'：'+(issue.msg||'请检查填写内容');}).join('；'):'';
throw new Error(typeof d.detail==='string'?d.detail:details||'服务错误 '+r.status)}return r.json()}
const post=(path,obj)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(obj)});
const days = x => x ? String(x).slice(0,10) : '—';
function badge(text,variant='neutral'){return `<span class="tag ${variant}">${esc(text)}</span>`}
function nav(page){state.page=page;$$('.nav-link').forEach(b=>b.classList.toggle('active',b.dataset.page===page));$('#crumb').textContent=({overview:'工作台',inbox:'询价来件',quote:'快速核价工具',insight:'业务分析',connect:'平台接入',audit:'操作审计',rules:'规则与资源',history:'报价归档',catalog:'数据明细',query:'AI查询中心',review:'证据与复核',versions:'RFQ版本差异',commercial:'供应商比价与报价',operations:'运行与指标'})[page];$('.sidebar').classList.remove('open');window.scrollTo({top:0,behavior:'instant'});return render().catch(e=>errorPage(e))}
function loading(){return `<section class="page"><div class="overline">LOADING / DATA WORKSPACE</div><div style="padding:40px 0;color:#7b8a82"><span class="spin"></span> 正在读取工作台数据…</div></section>`}
function errorPage(err){$('#main').innerHTML=`<section class="page"><div class="overline">CONNECTION ERROR</div><h1>工作台暂时无法连接</h1><p>${esc(err.message)}</p><p>请重试；会话过期时可重新登录。</p><button class="btn" data-action="reload">重新连接</button></section>`}
function pageHead(code,title,desc,actions=''){return `<div class="page-head"><div><div class="overline">${code}</div><h1>${title}</h1><p>${desc}</p></div>${actions?`<div class="page-head-actions">${actions}</div>`:''}</div>`}
async function render(){const main=$('#main');main.innerHTML=loading();if(state.page==='overview')return renderOverview();if(state.page==='inbox')return renderInbox();if(state.page==='quote')return renderQuote();if(state.page==='insight')return renderInsight();if(state.page==='connect')return renderConnect();if(state.page==='audit')return renderAudit();if(state.page==='rules')return renderRules();if(state.page==='history')return renderHistory();if(state.page==='catalog')return renderCatalog();if(state.page==='query')return window.renderQueryCenter();if(state.page==='review')return window.renderReviewCenter();if(state.page==='versions')return window.renderRFQVersions();if(state.page==='commercial')return window.renderCommercial();if(state.page==='operations')return window.renderOperations()}
async function getEmails(){if(!state.emails.length)state.emails=await api('/api/emails');return state.emails}
async function fetchLinePages(){
 const limit=500, rows=[];
 let offset=0, total;
 do {
  const page=await api('/api/lines?'+new URLSearchParams({limit,offset}));
  total ??= page.total;
  rows.push(...page.rows);
  offset+=page.rows.length;
  if(!page.rows.length)break;
 } while(offset<total);
 return rows;
}
async function getAllLines(){
 if(!state.allLines.length)state.allLines=await fetchLinePages();
 return state.allLines;
}

async function renderOverview(){const [s,offers,quotes,queue]=await Promise.all([
  api('/api/overview'),api('/api/supplier-offers'),api('/api/commercial-quotes'),api('/api/review-queue?limit=1')
 ]);
 if(state.page!=='overview')return;
 state.overview=s;$('#nav-emails').textContent=s.mails;
 const waiting=s.mail_counts.filter(m=>!m.line_count).length;
 const pending=offers.rows.filter(o=>o.review_status==='pending').length;
 const drafts=quotes.rows.filter(q=>q.status==='draft').length;
 const reviewed=quotes.rows.filter(q=>q.status==='business_reviewed').length;
 const approved=quotes.rows.filter(q=>q.status==='approved').length;
 const steps=[
  ['上传客户询价',s.mails+' 封已导入','有新询价时上传 EML、PDF 或 Excel。','inbox','upload-open','上传文件'],
  ['AI 整理需求',waiting+' 封尚无明细 · '+s.pending_ai_suggestions+' 笔建议待采纳 · '+queue.total+' 行待复核','选择邮件，核对建议中的型号和数量。','inbox','','选择来件'],
  ['核对供应商报价',pending+' 份待确认','保存供应商原件并逐项核对报价条件。','commercial','offer-file-form','查看供应商报价'],
  ['计算销售价格',drafts+' 份草稿','选定需求行，填写费用与毛利率，再比较方案。','commercial','commercial-form','开始核价'],
  ['业务审核与管理员审批',drafts+' 份草稿 · '+reviewed+' 份待批准','复核员审核选定方案，管理员打开同一编号批准。','commercial','saved-plans','继续处理'],
  ['下载正式报价',approved+' 份可交付','从已批准的报价中下载 PDF 或 Excel。','history','','查看归档']
 ];
 $('#main').innerHTML=`<section class="page"><div class="hero"><div class="hero-left"><div class="overline">采购工作台</div><h1>从客户询价<br>到正式报价</h1><p>上传客户发来的询价邮件或附件，逐步完成需求确认、供应商比价、成本核算和正式报价。</p><div class="hero-buttons"><button class="btn primary" data-jump="inbox" data-section="upload-open">开始一笔新报价</button><a class="btn" href="/guide/" target="_blank" rel="noopener">图解快速上手 ↗</a></div></div><div class="hero-right"><div class="hero-right-top">已导入询价</div><div class="manifest-num">${s.mails}<sup>封</sup></div></div></div>
 <h2>报价流程</h2><p>下方显示当前共享工作台的记录。报价状态统计最近 100 份方案。</p>
 <ol class="release-path steps-grid">${steps.map(([title,status,action,page,section,link],i)=>`<li><span class="overline">第 ${i+1} 步</span><h3>${title}</h3>${badge(status)}<p>${action}</p><button class="btn small" data-jump="${page}" data-section="${section}">${link} →</button></li>`).join('')}</ol>
 <article class="panel"><div class="panel-body"><h2>最近处理的报价</h2>${recentQuoteLinks(quotes.rows.slice(0,8))}</div></article>
 <details class="panel"><summary class="panel-head">查看邮件、需求与历史资源</summary><div class="metric-row">${metric('询价邮件',s.mails,'查看收件清单','01','inbox')}${metric('物料行',s.mail_lines,'查看全部需求','02','lines')}${metric('历史询价',s.history_lines,'查看历史明细','03','historical')}${metric('参考价格',s.price_records,'查看价格来源','04','prices')}</div></details></section>`;
}
function recentQuoteLinks(rows){
 const labels={draft:'待业务审核',business_reviewed:'待管理员审批',approved:'已批准 · 可下载'};
 return rows.map(q=>`<p><button class="btn small" data-jump="commercial" data-resume="${esc(q.id)}">${esc(q.id)} →</button> v${esc(q.version)} · ${esc(q.customer_name)} · ${esc(schemeNames[q.scheme]||q.scheme)} · ${esc(labels[q.status]||q.status)}</p>`).join('')||'<p>暂无相关报价。</p>';
}
function metric(label,value,note,idx,destination){return `<button type="button" class="metric metric-link" ${destination==='inbox'?'data-go="inbox"':`data-catalog="${destination}"`} aria-label="${esc(label)}，查看明细"><span class="metric-label"><span>${label}</span><span class="metric-index">${idx}</span></span><span class="metric-value">${fmt(value)}</span><span class="metric-note">${esc(note)}</span><span class="metric-open">查看明细 ↗</span></button>`}
function processRow(no,title,desc,end){return `<li class="process-row"><span class="process-no">${no}</span><span><div class="process-title">${title}</div><div class="process-desc">${desc}</div></span><span class="process-end">${end}</span></li>`}

async function renderInbox(){const identity=await api('/api/auth/me');const integration=identity.role==='reviewer'?{active_provider:'disabled',genesis_configured:false}:await api('/api/integration');const aiReady=integration.active_provider==='genesis'&&integration.genesis_configured;const emails=await getEmails();if(state.page!=='inbox')return;if(!state.emailId||!emails.some(e=>e.email_id===state.emailId))state.emailId=emails[0]?.email_id||'';
 $('#main').innerHTML=`<section class="page">
 ${pageHead('01 / INCOMING', '第一步：上传客户询价','客户通常会通过邮件发送物料型号、数量、技术规格及相关附件。请上传原始询价文件，系统会保留原件并整理可识别的需求信息。',`<button class="btn" data-action="upload-open">＋ 上传询价文件</button><button class="btn primary" data-go="review">复核需求与证据 ↗</button>`)}
 <div class="inbox-layout"><article class="panel"><div class="panel-head"><div><h2>收件清单</h2><div class="panel-sub">当前来件 · ${emails.length} 封邮件</div></div>${badge('SOURCES','neutral')}</div><div id="email-list" class="mail-list">${emails.map(e=>mailItem(e)).join('')}</div></article>
 <article class="panel"><div class="panel-head"><div><h2 id="mail-title">已提取的物料行</h2><div class="panel-sub" id="mail-subtitle">从左侧选择邮件查看内容</div></div><span class="tag strong" id="mail-count">—</span></div>
 <div class="panel-body"><h3>第二步：让 AI 读懂客户需求</h3><p>先选中一封来件。系统整理型号、数量、单位和件状，并保留原文。技术描述需要对照邮件核实。已有完整明细时可直接核对。</p></div><div class="filter-bar"><div class="search"><input id="inbox-search" aria-label="筛选询价件号" placeholder="搜索件号 / 描述 / 询价号…" value="${esc(state.inboxSearch)}" /></div><button class="btn small" data-action="clear-inbox-search">清除</button>${integration.native_rfq_enabled?'<button class="btn primary" data-action="native-rfq">AI 自动整理客户询价</button>':''}<button class="btn small" data-action="manual-intake">人工补录</button>${identity.role==='reviewer'?'<span>需要运行 AI 时，请切换管理员账户。</span>':`<details><summary>${integration.native_rfq_enabled?'备用提取方式':'其他提取方式'}</summary><p>原生处理不可用时可单独使用 Genesis，同一邮件只需选择一种方式。</p><button class="btn small" ${aiReady?'data-action="ai-extract-email"':'data-go="connect"'}>${aiReady?'Genesis 补充提取':'查看平台配置'}</button></details>`}<button class="btn small" data-action="saved-ai-extraction">已保存AI回执</button></div>
 <div id="inbox-table"><div class="table-empty">正在读取来件明细…</div></div>
 </article></div>
 <article class="panel" id="upload-panel" style="display:none;margin-top:20px"><div class="panel-head"><div><h2>上传询价文件</h2><div class="panel-sub">上传客户发给你的询价。点「检查文件内容」预览，再点「确认写入系统」保存。</div></div><button class="btn plain" data-action="upload-close">关闭 ×</button></div>
 <div class="panel-body"><div class="upload-zone"><div class="overline">RFQ / 文件</div><p>第一次体验？<a href="/guide/samples/01_customer_inquiry.eml" download>下载第一步客户询价邮件</a>，选中后可预览 PN-0001，3 件。</p><p>也可上传自备的合成询价：客户原始邮件 EML、询价 PDF 或物料清单 XLSX。单份上限 10 MB，独立附件需填写客户邮箱。</p><p>手里是供应商的单价和交期？请在<button type="button" class="btn small" data-jump="commercial" data-section="offer-file-form">第三步 · 供应商比价与报价</button>上传。</p><input id="eml-file" type="file" accept=".eml,.pdf,.xlsx"/><label id="file-customer-field" class="field" hidden>客户邮箱<input type="email" id="rfq-customer" placeholder="buyer@example.invalid"></label><div style="margin-top:12px"><button class="btn" data-action="preview-eml">检查文件内容</button></div></div><div id="upload-preview"></div></div></article>
 </section>`;
 await loadInboxLines();
}
function mailItem(e){let kind=(e.kinds||'').includes('Excel')?'EXCEL / 附件':(e.kinds||'').includes('PDF')?'PDF / 附件':'HTML / 正文';return `<button class="mail-item ${state.emailId===e.email_id?'active':''}" data-email="${esc(e.email_id)}"><div class="mail-item-label"><span>${kind}</span><span>#${String(e.line_count).padStart(3,'0')}</span></div><div class="mail-item-title">${esc(e.subject||e.filename)}</div><div class="mail-item-bottom"><span>${e.dataset==='official_sample'?'赛事示例':'后续导入'} · ${e.line_count} 行</span><span>查看 →</span></div></button>`}
async function loadInboxLines(){const e=state.emails.find(x=>x.email_id===state.emailId);if(!e){const table=$('#inbox-table');if(table)table.innerHTML='<div class="table-empty">上传一份询价文件后，需求明细会出现在这里。</div>';return}const query=new URLSearchParams({email_id:state.emailId,search:state.inboxSearch,limit:'20',offset:String(state.inboxPage*20)});const res=await api('/api/lines?'+query.toString());if(state.page!=='inbox'||state.emailId!==e.email_id||!$('#mail-title'))return;$('#mail-title').textContent=e.subject||e.filename;$('#mail-subtitle').textContent=`源文件 ${e.filename} · 来源表格与附件位置可查看`;$('#mail-count').textContent=res.total+' 行';if(state.inboxPage>0&&res.total<=state.inboxPage*20){state.inboxPage=0;return loadInboxLines()}$('#inbox-table').innerHTML=makeLinesTable(res.rows,false,res.total,state.inboxPage*20,'inbox');$$('.mail-item').forEach(b=>b.classList.toggle('active',b.dataset.email===state.emailId))}
function makeLinesTable(rows,checkable=false,total=rows.length,start=0,place='quote'){if(!rows.length)return `<div class="table-empty">暂无符合条件的明细。可清除筛选，或选中邮件后使用 AI 整理或人工补录。</div>`;const head=checkable?'<th style="width:35px"><input type="checkbox" id="select-visible" aria-label="全选当前显示行"></th>':'';
 const body=rows.map((r,i)=>`<tr>${checkable?`<td><input type="checkbox" class="line-checkbox" data-id="${r.id}" aria-label="选择${esc(r.part_number)}" ${state.selected.has(r.id)?'checked':''}></td>`:''}<td class="mono subtle">${String(i+start+1).padStart(2,'0')}</td><td class="part">${esc(r.part_number)}</td><td class="cell-desc" title="${esc(r.description)}">${esc(r.description||'—')}</td><td><b>${fmt(r.quantity)}</b> <span class="fineprint">${esc(r.unit)}</span></td><td>${esc(r.part_condition||'—')}</td><td><span class="tag neutral">${esc(r.source_kind)}</span></td><td><button class="row-action" data-line="${r.id}">来源 ↗</button>${place==='inbox'?` <button class="row-action" data-jump="review" data-open-line="${r.id}">核对这行需求</button>`:''}</td></tr>`).join('');
 return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}<th>行</th><th>物料件号</th><th>描述</th><th>需求数量</th><th>件状</th><th>提取路径</th><th>操作</th></tr></thead><tbody>${body}</tbody></table></div><div class="table-foot"><span>显示 ${start+1}–${start+rows.length} / ${total} 条</span><div><button class="btn small" data-action="${place}-prev" ${start===0?'disabled':''}>上一页</button> <button class="btn small" data-action="${place}-next" ${start+rows.length>=total?'disabled':''}>下一页</button></div></div>`}

async function renderQuote(){if(!state.rulesLoaded){state.filters=await api('/api/rules');state.rulesLoaded=true}await getEmails();await getAllLines();if(state.page!=='quote')return;const count=state.selected.size;
 $('#main').innerHTML=`<section class="page">
 ${pageHead('02 / DECISION DESK','核价之前，先核证据。','查得到，说明白；查不到，就保留待核价。所有计算遵守可审计的业务规则。',`<button class="btn" data-action="preset-good">载入可核价样例</button><button class="btn" data-action="preset-mixed">载入缺价对照</button>`)}
 <div class="workbench">
 <div><article class="panel"><div class="panel-head"><div><h2>选择询价明细</h2><div class="panel-sub">参考核价每批 100 行，单次最多 300 行。正式报价按原询价分别生成。</div></div><span class="tag">SOURCE FIRST</span></div>
 <div class="filter-bar"><div class="search"><input id="quote-search" placeholder="搜索件号 / 询价号 / 描述…" value="${esc(state.quoteSearch)}"></div><select id="quote-email" class="btn" style="max-width:175px"><option value="all">全部来件</option>${state.emails.map((e,i)=>`<option value="${esc(e.email_id)}" ${state.quoteEmail===e.email_id?'selected':''}>第${i+1}封 · ${e.line_count}行</option>`).join('')}</select></div>
 <div id="quote-lines"></div><div class="selection-bar"><span><b id="selected-count">${count}</b> 条已选择</span><div><button class="btn small ghost" data-action="clear-selection">清空</button> <button class="btn small dark" data-action="pick-visible">选择当前前 10 条</button> <button class="btn small" data-action="pick-email">选择整封来件</button></div></div></article>
 <article id="quote-result" class="panel" style="margin-top:20px">${state.quoteReport?reportHtml(state.quoteReport):`<div class="blank"><div class="blank-illustration">≋</div><h3>报价草案将在这里生成</h3><p>先选一条询价，右侧设置核价日期和计算规则。执行后可查看每条价格的来源与拦截原因。</p></div>`}</article></div>
 <aside><article class="panel sticky-panel"><div class="panel-head"><div><h2>核价规则</h2><div class="panel-sub">财务计算由确定性代码完成，非模型猜测</div></div></div>
 <div class="rule-form"><div class="field full"><label for="quote-date">报价基准日期</label><input id="quote-date" type="date" value="${esc(state.filters.asof)}"><small>使用官方历史样例日期，避免把已过期的报价当作当前价格。</small></div>
 <div class="field full"><label>计算方式</label><div class="radio-tabs"><button class="radio-tab ${state.filters.method==='markup'?'active':''}" data-method="markup">成本加价率</button><button class="radio-tab ${state.filters.method==='margin'?'active':''}" data-method="margin">目标毛利率</button></div></div>
 <div class="field full"><label for="quote-rate">比例 <strong id="rate-label">${state.filters.rate}%</strong></label><input id="quote-rate" type="range" min="0" max="70" step="5" value="${state.filters.rate}"><small id="rate-example">${state.filters.method==='markup'?'100 成本 + 20% 加价 = 120':'100 成本 / (1-20%) = 125'}</small></div>
 <div class="info-strip full">每条候选价格会核对件状、有效日期、起订量和汇率。供应商的计量单位与证书仍需人工复核。</div></div>
 <button class="btn primary big-submit" data-action="run-quote">执行核价 <span aria-hidden>↗</span></button>
 </article><div class="alert-strip" style="margin-top:14px">【 草案状态 】系统只生成用于复核的报价草案，不会自动给客户发送邮件，也不会把缺失价格补成虚构金额。</div></aside>
 </div></section>`;renderQuoteLines();
}
function quoteVisible(){let ls=state.allLines;if(state.quoteEmail!=='all')ls=ls.filter(r=>r.email_id===state.quoteEmail);const k=state.quoteSearch.trim().toLowerCase();if(k)ls=ls.filter(r=>[r.part_number,r.description,r.source_rfq_no].some(x=>String(x||'').toLowerCase().includes(k)));return ls}
function renderQuoteLines(){const filtered=quoteVisible();if(state.quotePage*15>=filtered.length)state.quotePage=0;const start=state.quotePage*15;const slice=filtered.slice(start,start+15);$('#quote-lines').innerHTML=makeLinesTable(slice,true,filtered.length,start,'quote');const el=$('#selected-count');if(el)el.textContent=state.selected.size;const all= $('#select-visible');if(all)all.checked=slice.every(r=>state.selected.has(r.id))}
function reportHtml(report){const priority={'待核价':0,'待人工确认':1,'可报价':2,'已人工确认':3};let items=[...report.lines].sort((a,b)=>(priority[a.decision_state]??2)-(priority[b.decision_state]??2));const good=items.filter(x=>x.status.startsWith('可报价'));return `<div class="panel-head"><div><h2>核价结果 <span class="tag warn">${report.review_status==='approved'?'REVIEWED / 已确认':'DRAFT / 待审批'}</span></h2><div class="panel-sub">${esc(report.quote_id||'')} v${report.version||1} · 基准日 ${esc(report.asof)} · ${report.method==='markup'?'成本加价':'目标毛利率'} ${Number(report.rate)*100}% · 全部基于实际查询结果</div></div>${badge(report.review_status==='approved'?'已人工确认':'已保存草案','strong')}</div>
 ${report.approval_blockers?.length?`<div class="alert-strip">不可确认：${report.approval_blockers.map(esc).join('；')}</div>`:''}<div class="quote-summary"><div class="quote-sum-item"><label>已计算建议价行</label><strong>${report.quoted_count}</strong></div><div class="quote-sum-item"><label>待核价行</label><strong style="color:var(--rust)">${report.pending_count}</strong></div><div class="quote-sum-item"><label>草案小计 / CNY</label><strong class="money">${money(report.total_cny)}</strong></div></div>
 <div class="data-explainer">异常优先：待核价 → 待人工确认 → 可报价。请按每行原因处理；源数据顺序仍保留在归档与导出中。</div><div class="quote-detail">${items.map(x=>`<article class="quote-line"><div class="quote-line-top"><div class="quote-line-head"><span class="line-name">${esc(x.part_number)}</span>${badge(x.decision_state||x.status,x.decision_state==='可报价'||x.decision_state==='已人工确认'?'strong':'warn')}</div><span class="mono" style="font-size:11px">${esc(x.source_rfq_no||'未标询价号')}</span></div><div class="quote-line-middle"><div><small>报价数量</small><b>${fmt(x.quantity)} ${esc(x.unit)}</b></div><div><small>建议单价 / CNY</small><b>${x.unit_quote_cny?money(x.unit_quote_cny):'—'}</b></div><div><small>行金额 / CNY</small><b>${x.line_total_cny?money(x.line_total_cny):'待确认'}</b></div></div><div class="quote-line-bottom">${x.review_flags?.length?`<div class="issue"><b>${report.review_status==='approved'?'已确认事项：':'需人工确认：'}</b>${x.review_flags.map(esc).join('；')}</div>`:''}<div style="margin:8px 0"><button class="row-action" data-edit-quote-line="${x.line_id}" ${report.review_status==='approved'?'disabled':''}>修改价格 / 件状 / 交期 ↗</button></div>${x.audit?.length?`<ul class="audit-list">${x.audit.map(a=>`<li>${esc(a)}</li>`).join('')}</ul>`:''}${x.issues?.length?`<div class="issue"><b>${x.status.startsWith('可报价')?'其他候选的未通过原因：':'待核事项：'}</b>${x.issues.map(esc).join('；')}</div>`:''}<div style="margin-top:8px;display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap"><span>依据：${esc(x.price_ref||'未找到匹配价格')} ${x.price_basis?.record?.source_row?' / 原表行 '+esc(x.price_basis.record.source_row):''}</span>${x.price_basis?.source_file?`<a class="row-action" href="/api/sources/${x.price_basis.source_file.id}/download" download="${esc(x.price_basis.source_file.filename)}">下载价格依据原表 ↗</a>`:''}<button class="row-action" data-line="${x.line_id}">核对原始记录 ↗</button></div></div></article>`).join('')}</div>
 <div class="data-explainer">只对通过核价规则的行计算小计。供应商单位/证书、税费、运费与最终交期仍需人工确认。草案不得直接作为正式对外报价。</div><div id="review-controls" class="panel-body" style="display:${report.review_status==='approved'?'none':'block'}"><div class="field"><label>复核人</label><input id="review-actor" placeholder="填写姓名或工号"></div><div class="field"><label>复核说明</label><input id="review-reason" placeholder="记录确认依据与业务条件"></div><label style="display:block;margin:14px 0"><input id="review-confirm" type="checkbox"> 已核对单位、件状、证书、交期、税费和来源</label><button class="btn primary" data-action="approve-quote">确认整份报价</button></div><div class="export-bar"><button class="btn dark" data-export="xlsx">下载报价单 XLSX ↗</button><button class="btn" data-export="csv">核价明细 CSV</button><button class="btn" data-export="json">审计记录 JSON</button>${report.review_status==='approved'?'<button class="btn" data-action="sync-cloud-quote">同步 MOI 云端快照 ↗</button>':''}</div>`}

async function renderInsight(){const [s,integration,dates]=await Promise.all([api('/api/overview'),api('/api/integration'),api('/api/query-center/status')]);const aiReady=integration.active_provider==='genesis'&&integration.genesis_configured;state.analysisAsOf ||= dates.historical_reference_date || dates.default_reference_date;$('#main').innerHTML=`<section class="page">
 ${pageHead('03 / INQUIRY INTELLIGENCE','让数据回答问题。','在确定的数据范围内查询询价趋势、客户紧急度、热门件号与截止期。',`<span class="summary-badge">${s.history_lines} 行历史明细 / ${s.history_rfq_groups} 组 RFQ</span>`)}
 <div class="panel"><div class="panel-head"><div><h2>提一个具体的业务问题</h2><div class="panel-sub">${aiReady?'Genesis 理解问题与筛选条件，再查询实际业务数据库':'AI 尚未启用；可使用上方四项快捷统计'}</div></div><span class="tag ${aiReady?'strong':'warn'}">${aiReady?'GENESIS / AI 查询':'快捷统计'}</span></div>
 <div class="panel-body"><div class="analysis-queries" id="analysis-queries">${['每月询价趋势','客户紧急询价排名','热门询价件号','即将截止的询价'].map(x=>`<button class="query-chip ${state.insight===x?'active':''}" data-insight="${x}">${x}</button>`).join('')}</div>
 <div class="field" style="margin-top:16px"><label for="analysis-asof">相对日期基准日</label><input type="date" id="analysis-asof" value="${esc(state.analysisAsOf)}"><small>相对时间按所选日期解释。初始日期取最近一条历史询价的日期；历史表为空时取今天。</small></div><div class="nl-search"><input id="nl-question" aria-label="业务问题" placeholder="例如：按客户统计历史询价份数，列出前五名" maxlength="300"><button class="btn dark" data-action="ask-insight">查询数据 ↗</button></div>
 <div id="analysis-answer" class="info-strip" role="status" style="margin-bottom:4px">可查询：历史询价、导入需求、供应商价格和内部成本。可组合时间、客户、件号与分组统计；此处不提供机票或实时航班搜索。${aiReady?'提交问题会调用 Genesis，消耗模型额度；四个快捷统计按钮直接查数据库。':'当前自由提问尚未启用。'}</div></div></div>
 <div class="section-grid" style="margin-top:20px;grid-template-columns:minmax(0,1.35fr) minmax(260px,1fr)">
 <article class="panel"><div class="panel-head"><div><h2 id="chart-title">查询结果</h2><div class="panel-sub" id="chart-caption">来源：历史询价表</div></div><span class="tag strong" id="chart-total">已验证</span></div><div id="chart-area" class="chart-area"></div><div class="data-explainer" id="chart-explainer">按照明确的统计口径计数，避免把物料明细行误当成询价份数。</div></article>
 <article class="panel"><div class="panel-head"><div><h2>查询依据</h2><div class="panel-sub">规则清楚、计算可重复</div></div></div><div class="panel-body"><div class="process-list">
 ${processRow('01','确定统计对象','询价份数与物料明细行数分开计算','RFQ No')}
 ${processRow('02','理解统计口径','AI解析数据范围、分组、指标与筛选条件','Genesis')}
 ${processRow('03','执行数据库查询','由校验后的查询计划生成参数化 SQL','实际数据')}
 </div><div class="note-card"><strong>没有“AI 说了算”的数字。</strong>图表和明细使用同一条查询结果；AI负责理解问题，数字由数据库返回。不在数据范围内的问题会直接说明。</div></div></article></div>
 <article class="panel" style="margin-top:20px"><div class="panel-head"><div><h2>明细数据</h2><div class="panel-sub">可以与图表逐行对照，核验统计口径</div></div><button class="btn small" data-action="toggle-sql">显示 SQL</button></div><div id="insight-table"></div><pre id="sql-box" class="sql-box hidden"></pre></article></section>`;await loadInsight(state.insight)}
let insightRequest=0;
async function loadInsight(q,asof=state.analysisAsOf){const request=++insightRequest;state.insight=q;const r=await api('/api/analytics?'+new URLSearchParams({q,asof}));if(state.page==='insight'&&request===insightRequest)fillInsight(r)}
function clearInsight(message){$('#chart-title').textContent='尚无本次查询结果';$('#chart-caption').textContent='图表和明细将随本次查询更新';$('#chart-total').textContent='未查询';$('#chart-area').innerHTML='<div class="table-empty">'+esc(message)+'</div>';$('#insight-table').innerHTML='<div class="table-empty">'+esc(message)+'</div>';$('#sql-box').textContent='';$('#chart-explainer').textContent='';$$('.query-chip').forEach(b=>b.classList.remove('active'))}
function fillInsight(r){const rows=r.rows||[];if(!r.model_connected)state.insight=r.question;$$('.query-chip').forEach(b=>b.classList.toggle('active',b.dataset.insight===r.question));$('#chart-title').textContent=r.question;$('#chart-caption').textContent=`实际查询 ${rows.length} 组 · ${r.dataset_rows} 条${r.dataset_label||'历史明细'} · 图表最多显示前 12 组`;
 const keys=rows[0]?Object.keys(rows[0]):[];const dimensions=r.group_labels?.length?r.group_labels:[keys[0]];const value=r.metric_labels?.[0]||keys[1];const hasMeasure=rows.some(row=>row[value]!=null && row[value]!=='' && Number.isFinite(Number(row[value])));const graph=hasMeasure?rows.slice(0,12):[];const label=x=>dimensions.map(k=>x[k]??'未提供').join(' / ');const max=Math.max(1,...graph.map(x=>Number(x[value])||0));
 $('#chart-area').innerHTML=graph.length?`<div class="chart-grid">${graph.map(x=>`<div class="chart-row"><div class="chart-row-label" title="${esc(label(x))}">${esc(label(x))}</div><div class="chart-row-track"><div class="chart-row-fill" style="width:${Math.max(0,100*(Number(x[value])||0)/max)}%"></div></div><div class="chart-row-value">${fmt(x[value])}</div></div>`).join('')}</div>`:'<div class="table-empty">'+(rows.length?'本次结果为明细列表，请查看下方表格。':r.dataset_rows===0?'当前查询使用的数据表为空。四项快捷统计读取历史询价表；新上传的来件保存在导入需求中。':'所选条件下没有记录，请检查基准日和关键词。')+'</div>';
 $('#chart-total').textContent=r.model_connected?'Genesis + 数据库':'快捷统计';$('#chart-explainer').textContent=r.scope_note||(r.question==='即将截止的询价'?'截止日期以所选基准日计算，不代表今天的真实待办。':'询价份数按 RFQ No 分组，明细行数分别统计。');
 $('#insight-table').innerHTML=rows.length?`<div class="table-wrap"><table class="data-table"><thead><tr>${keys.map(k=>`<th>${esc(k)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${keys.map(k=>`<td>${esc(row[k]??'—')}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="table-foot"><span>显示 ${rows.length} 组 · 与上方图表同源；统计结果可能按所请求的前 N 项截取</span></div>`:'<div class="table-empty">没有符合条件的数据</div>';
 $('#sql-box').textContent=(r.sql||'')+(r.sql_parameters?'\n参数：'+JSON.stringify(r.sql_parameters):'');
 $('#analysis-answer').className='info-strip';$('#analysis-answer').textContent=r.model_connected?`理解为：${r.interpreted_as}。来源：${r.dataset_label}。真实模型：${r.model} · 调用 ID：${r.response_id}`:'已执行「'+r.question+'」快捷统计。自由提问可组合时间、客户、件号和统计指标。';
}

async function renderConnect(){const s=await api('/api/integration');const live=s.active_provider==='genesis'&&s.genesis_configured;$('#main').innerHTML=`<section class="page">${pageHead('PLATFORM / STATUS','平台服务与业务回执','这里展示当前服务的配置和本数据库保存的成功记录。历史开发环境的成功不计作本服务成功。')}
 <article class="panel"><div class="panel-head"><h2>AI 提取 · Genesis</h2>${badge(live?'真实模式已配置':'Mock 模拟 / 未启用','warn')}</div><div class="panel-body"><p>${live?'已配置真实模型。进入询价来件，主动点击「Genesis 补充提取」后才发送文本、消耗模型额度；结果须人工复核。':'当前不会向 Genesis 发送请求。邮件解析、核价、审批和导出仍由实际代码执行。启用真实提取需要在服务器配置现有 Genesis 凭据与模型。'}</p><p>本数据库最近真实调用：${s.last_successful_genesis_call?esc(s.last_successful_genesis_call.model)+' / '+esc(s.last_successful_genesis_call.response_id):'暂无成功记录'}</p><button class="btn" data-go="inbox">进入询价来件 →</button></div></article>
 <article class="panel" style="margin-top:20px"><div class="panel-head"><h2>文件与业务数据</h2>${badge(s.ephemeral_storage?'临时存储 · 会丢失':'SQLite 存储','warn')}</div><div class="panel-body"><p>${s.ephemeral_storage?'当前免费演示使用临时磁盘。上传、报价和审计记录可能在休眠、重启或重新部署后丢失；请及时下载报价及审计记录。免费部署仍可修改代码，数据持久保存需要另行接入外部存储。':'当前业务主库为 SQLite；存储是否持久取决于服务器挂载配置。'}</p><p>初始数据来自赛事官方模拟素材；后续上传单独记录。供应商表和历史表用于演示，不代表实时行情、实际订单或收入。</p><button class="btn" data-catalog="historical">查看历史示例</button> <button class="btn" data-catalog="prices">查看供应商示例</button></div></article>
 <article class="panel" style="margin-top:20px"><div class="panel-head"><h2>MOI 云端快照与原生工作流</h2></div><div class="panel-body"><p>报价快照同步：${s.moi_sql_configured?'已配置':'未配置'}。本数据库最近读回校验：${s.last_verified_cloud_snapshot?esc(s.last_verified_cloud_snapshot.quote_id):'暂无成功记录'}。</p><p>云端快照只镜像已确认报价；邮件、附件、成本和供应商数据仍在业务主库。${s.last_native_execution_id?'已核对原生节点及读回记录，执行 ID '+esc(s.last_native_execution_id):'本工作区尚无已核对的原生执行记录。'}</p><button class="btn" data-action="native-workflow-status">查询原生工作流状态</button> <button class="btn" data-go="commercial">查看报价与回执</button></div></article>
 <p class="worknote">评委可使用管理员或业务复核员访问码登录。配置状态不等于持续在线探测；模型或云端失败不会伪装成功。</p></section>`}

async function openLine(id){const r=await api('/api/lines/'+id);const asof=state.filters.asof;const qs=new URLSearchParams({part_number:r.part_number,quantity:String(r.quantity),condition:r.part_condition||'',asof});const sources=await api('/api/price/candidates?'+qs);$('#drawer-content').innerHTML=`<div class="drawer-top"><div class="overline">LINE EVIDENCE / #${r.id}</div><button class="drawer-close" data-action="close-drawer" aria-label="关闭">×</button></div><h2 class="drawer-title">${esc(r.part_number)}</h2><div class="tag strong">原始记录可追溯</div>
 <dl>${[['询价单号',r.source_rfq_no],['件号描述',r.description],['需求数量',r.quantity+' '+r.unit],['件状',r.part_condition||'待核对'],['来源类型',r.source_kind],['具体位置',r.source_ref],['邮件主题',r.email_subject],['邮件文件',r.filename||r.email_filename],['来源客户',r.customer||'—'],['询价优先级',r.urgency||'未提供'],['截单日期',r.deadline||'未提供']].map(k=>`<div class="kv"><dt>${k[0]}</dt><dd>${esc(k[1]||'—')}</dd></div>`).join('')}</dl>
 <div class="drawer-divider"></div><h3>原始文件 · SHA256</h3>${[...(r.files||[]),...(r.pricing_workbooks||[]).map(f=>({...f,kind:'价格/成本/历史原表',dataset:'official_sample'}))].map(f=>`<p class="fineprint"><a href="/api/sources/${f.id}/download" download="${esc(f.filename)}">${esc(f.filename)}</a><br>${esc(f.kind)} / ${esc(f.dataset)}<br><span style="word-break:break-all">${esc(f.sha256)}</span></p>`).join('')}<h3>原始字段证据</h3><pre style="white-space:pre-wrap;word-break:break-word">${esc(r.evidence?.raw_json||'旧数据无字段快照，请重新导入')}</pre><div class="drawer-divider"></div><div class="overline">PRICE RESOURCE MATCH</div><h3>候选价格 · ${sources.count} 条</h3>
 ${sources.candidates.length?sources.candidates.slice(0,15).map(c=>`<div style="border-bottom:1px solid #e8ece6;padding:13px 0"><div style="display:flex;justify-content:space-between;gap:8px"><b>${esc(c.resource_id)}</b>${badge(c.status,c.status==='有效候选'?'strong':'warn')}</div><div class="fineprint">${esc(c.supplier)} · ${esc(c.currency)} ${esc(c.unit_price)} · 有效至 ${esc(c.valid_until)}</div><div class="fineprint" style="margin-top:4px;color:${c.issues.length?'#b55b3e':'#456b57'}">${c.issues.length?esc(c.issues.join('；')):'符合已验证的价格筛选条件；单位及证书仍需复核'}</div></div>`).join(''):'<p class="muted">没有匹配件号的供应商价格记录。</p>'}
 <div class="alert-strip" style="margin-top:20px">价格候选的“有效”只表示通过当前可核对的日期、件状、价格及 MOQ 规则；不代表正式业务审批完成。</div>
 <button class="btn dark block" style="margin-top:19px" data-action="send-line-to-quote" data-id="${r.id}">把这行加入核价工作台 ↗</button>`;
 $('#drawer-backdrop').classList.remove('hidden');$('#drawer').classList.remove('hidden');$('#drawer').setAttribute('aria-hidden','false')}
function closeDrawer(){$('#drawer-backdrop').classList.add('hidden');$('#drawer').classList.add('hidden');$('#drawer').setAttribute('aria-hidden','true')}
async function runQuote(){if(!state.selected.size){toast('请先选择一条询价明细');return}const ids=[...state.selected];if(ids.length>300){toast('每次最多核价300行，请缩小选择范围');return}
 state.filters.asof=$('#quote-date').value;state.filters.rate=Number($('#quote-rate').value);const req={line_ids:ids,asof:state.filters.asof,rate:state.filters.rate,method:state.filters.method};try{const btn=$('[data-action="run-quote"]');btn.disabled=true;btn.textContent='正在核对…';const report=await post('/api/quote',req);state.quoteReq=req;state.quoteReport=report;$('#quote-result').innerHTML=reportHtml(report);$('#quote-result').scrollIntoView({behavior:'smooth',block:'start'});toast(`核价完成：${report.quoted_count} 行可报价，${report.pending_count} 行待核价`)}catch(e){toast('核价失败：'+e.message)}finally{const btn=$('[data-action="run-quote"]');if(btn){btn.disabled=false;btn.innerHTML='执行核价 <span aria-hidden>↗</span>'}}}
async function exportQuote(kind){if(!state.quoteReport?.quote_id){toast('请先生成或打开报价');return}try{const r=await fetch('/api/quotes/'+state.quoteReport.quote_id+'/export/'+kind);if(!r.ok)throw new Error('导出失败');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=state.quoteReport.quote_id+'.'+kind;a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);toast('已导出数据库保存版本 v'+state.quoteReport.version)}catch(e){toast(e.message)}}
async function preset(type){await getAllLines();let set;if(type==='good')set=state.allLines.filter(r=>r.part_number==='PN-0001'&&r.quantity===8&&r.unit==='EA').slice(0,1);else{const a=state.allLines.find(r=>r.part_number==='PN-0001'&&r.quantity===8);const b=state.allLines.find(r=>r.part_number==='GSK-001');set=[a,b].filter(Boolean)}if(!set.length){toast('未找到对应的官方样例');return}state.selected=new Set(set.map(r=>r.id));state.quoteSearch='';state.quoteEmail='all';renderQuoteLines();toast('已载入 '+set.length+' 条真实样例，可直接执行核价')}
async function previewEML(){const inp=$('#eml-file');if(!inp.files?.length){toast('请先选择询价文件');return}const fd=new FormData();fd.append('file',inp.files[0]);fd.append('customer_email', $('#rfq-customer')?.value || '');const n=$('#upload-preview');n.innerHTML='<p class="muted"><span class="spin"></span> 正在检查邮件…</p>';
 try{const r=await api('/api/emails/preview',{method:'POST',body:fd});n.innerHTML=`<div class="info-strip">主题：${esc(r.subject)}<br>预览 ${r.count} 行 · ${r.attachments.length} 个附件<br>${r.count ? r.sample_lines.slice(0,3).map(line=>esc(line.part_number)+' · '+esc(line.quantity)+' '+esc(line.unit)).join('<br>') : '请先保存原件。普通邮件正文可由管理员启动「AI 自动整理客户询价」；扫描件请对照原件人工补录。'}${r.notes.length?`<details><summary>查看解析说明</summary>${esc(r.notes.join('；'))}</details>`:''}</div><div style="margin-top:13px"><button class="btn primary" data-action="import-eml">确认写入系统</button></div>`;toast('邮件预览完成，可以确认导入')}catch(e){n.innerHTML=`<div class="alert-strip">${esc(e.message)}</div>`}}
async function importEML(){const inp=$('#eml-file');if(!inp.files?.length)return;const fd=new FormData();fd.append('file',inp.files[0]);fd.append('customer_email', $('#rfq-customer')?.value || '');try{const r=await api('/api/emails/import',{method:'POST',body:fd});state.emails=[];state.allLines=[];state.emailId=r.email_id||'';state.inboxSearch='';state.inboxPage=0;toast(r.already_imported?'这份原件已导入，已打开原记录。':r.status==='needs_review'?`已保留原文件，需人工核对：${r.notes.join('；')}`:`导入完成：新增 ${r.new_lines} 行，重复 ${r.duplicate_lines} 行`);renderInbox()}catch(e){toast('导入失败：'+e.message)}}

// Delegated controls: rerendering never leaks listeners.
document.addEventListener('click',async e=>{
 const target=e.target.closest('button');if(!target)return;
 if(target.dataset.catalog){state.catalog={kind:target.dataset.catalog,search:'',page:0};nav('catalog');return}
 if(target.dataset.catalogAction){const action=target.dataset.catalogAction;if(action==='search'){state.catalog.search=$('#catalog-search').value.trim();state.catalog.page=0}if(action==='prev')state.catalog.page=Math.max(0,state.catalog.page-1);if(action==='next')state.catalog.page++;try{await loadCatalog()}catch(err){toast(err.message)}return}
 if(target.dataset.catalogRecord){openCatalogRecord(Number(target.dataset.catalogRecord));return}
 if(target.dataset.jump){
  const page=target.dataset.jump;
  await nav(page);
  if(state.page!==page)return;
  if(target.dataset.resume){commercialShow(await api('/api/commercial-quotes/'+encodeURIComponent(target.dataset.resume)));$('#commercial-draft')?.scrollIntoView();}
  else if(target.dataset.openLine){await openReview(Number(target.dataset.openLine));$('#review-detail')?.scrollIntoView();}
  else if(target.dataset.section==='upload-open'){$('[data-action="upload-open"]')?.click();}
  else if(target.dataset.section){document.getElementById(target.dataset.section)?.scrollIntoView();}
  return;
 }
 if(target.dataset.go){nav(target.dataset.go);return}
 if(target.dataset.page){nav(target.dataset.page);return}
 if(target.dataset.email){state.emailId=target.dataset.email;state.inboxPage=0;try{await loadInboxLines()}catch(err){toast(err.message)}return}
 if(target.dataset.line){try{await openLine(Number(target.dataset.line))}catch(err){toast(err.message)}return}
 if(target.dataset.method){state.filters.method=target.dataset.method;$$('[data-method]').forEach(x=>x.classList.toggle('active',x.dataset.method===state.filters.method));$('#rate-example').textContent=state.filters.method==='markup'?'100 成本 × (1 + 加价率)':'100 成本 / (1 - 目标毛利率)';return}
 if(target.dataset.insight){try{await loadInsight(target.dataset.insight)}catch(err){toast(err.message)}return}
 if(target.dataset.savedQuote){state.quoteReport=await api('/api/quotes/'+target.dataset.savedQuote);nav('quote');return}
 if(target.dataset.editQuoteLine){await editQuoteLine(Number(target.dataset.editQuoteLine));return}
 if(target.dataset.export){await exportQuote(target.dataset.export);return}
 const action=target.dataset.action;
 if(action==='reload')enterWorkspace().catch(errorPage);
 if(action==='upload-open'){const n=$('#upload-panel');n.style.display='block';n.scrollIntoView({behavior:'smooth'})}
 if(action==='upload-close')$('#upload-panel').style.display='none';
 if(action==='clear-inbox-search'){state.inboxSearch='';state.inboxPage=0;$('#inbox-search').value='';loadInboxLines()}
 if(action==='preview-eml')previewEML();if(action==='import-eml')importEML();
 if(action==='preset-good')preset('good');if(action==='preset-mixed')preset('mixed');
 if(action==='run-quote')runQuote();
 if(action==='native-rfq')openNativeRFQ();
 if(action==='ai-extract-email')aiExtractEmail(target);if(action==='saved-ai-extraction')savedAIExtraction();
 if(action==='manual-intake')openManualIntake();
 if(action==='save-manual-intake')saveManualIntake();
 if(action==='native-workflow-status'){try{const r=await api('/api/native-workflow/status');toast(r.workflow_id+' / '+r.status+' / 成功运行须另行验收')}catch(e){toast(e.message)}}

 if(action==='approve-quote')approveQuote();
 if(action==='sync-cloud-quote')syncCloudQuote(target);
 if(action==='save-line-edit')saveLineEdit();
 if(action==='save-rules')saveRules();
 if(action==='clear-selection'){state.selected.clear();renderQuoteLines()}
 if(action==='pick-email'){
   if(state.quoteEmail==='all'){toast('请先选择一封来件');return}
   try{
     const query=new URLSearchParams({email_id:state.quoteEmail,limit:300});
     const result=await api('/api/lines?'+query);
     if(result.total>300){toast('该来件超过300行，请按询价号选择');return}
     state.selected=new Set(result.rows.map(r=>r.id));
     renderQuoteLines();
   }catch(error){toast(error.message)}
 }
 if(action==='pick-visible'){quoteVisible().slice(state.quotePage*15,state.quotePage*15+10).forEach(r=>state.selected.add(r.id));renderQuoteLines()}
 if(action==='inbox-prev'){state.inboxPage=Math.max(0,state.inboxPage-1);await loadInboxLines()}
 if(action==='inbox-next'){state.inboxPage++;await loadInboxLines()}
 if(action==='quote-prev'){state.quotePage=Math.max(0,state.quotePage-1);renderQuoteLines()}
 if(action==='quote-next'){state.quotePage++;renderQuoteLines()}
 if(action==='close-drawer')closeDrawer();
 if(action==='send-line-to-quote'){state.selected.add(Number(target.dataset.id));closeDrawer();nav('quote')}
 if(action==='toggle-sql')$('#sql-box').classList.toggle('hidden');
 if(action==='ask-insight'){
  const text=$('#nl-question').value.trim();if(text.length<2){toast('请填写至少两个字的业务问题');return}
  const request=++insightRequest;const button=target;state.analysisAsOf=$('#analysis-asof').value;if(!state.analysisAsOf){toast('请选择相对日期基准日');return}
  button.disabled=true;button.textContent='正在理解与查询…';clearInsight('正在理解问题并查询业务数据…');$('#analysis-answer').className='info-strip';$('#analysis-answer').textContent='正在处理本次问题，请稍候…';
  try{const r=await post('/api/analytics/ask',{question:text,asof:state.analysisAsOf});if(request!==insightRequest||state.page!=='insight')return;if(!r.supported){clearInsight('此问题超出当前数据或统计能力范围');$('#analysis-answer').className='alert-strip';$('#analysis-answer').textContent=r.message+' 可试：按客户统计历史询价份数、按产品范围统计需求数量。'}else fillInsight(r)}catch(err){if(request===insightRequest&&state.page==='insight'){clearInsight('本次查询未完成');$('#analysis-answer').className='alert-strip';$('#analysis-answer').textContent=err.message}}finally{button.disabled=false;button.textContent='查询数据 ↗'}
 }
});
document.addEventListener('change',e=>{
 if(e.target.id==='analysis-asof')state.analysisAsOf=e.target.value;
 if(e.target.matches('.line-checkbox')){const id=Number(e.target.dataset.id);if(e.target.checked)state.selected.add(id);else state.selected.delete(id);$('#selected-count').textContent=state.selected.size;const visible=quoteVisible().slice(state.quotePage*15,state.quotePage*15+15);if($('#select-visible'))$('#select-visible').checked=visible.every(r=>state.selected.has(r.id));return}
 if(e.target.id==='select-visible'){quoteVisible().slice(state.quotePage*15,state.quotePage*15+15).forEach(r=>e.target.checked?state.selected.add(r.id):state.selected.delete(r.id));renderQuoteLines();return}
 if(e.target.id==='quote-email'){state.quoteEmail=e.target.value;state.quotePage=0;renderQuoteLines()}
 if(e.target.id==='quote-date')state.filters.asof=e.target.value;
});
let typingTimeout;document.addEventListener('input',e=>{
 if(e.target.id==='inbox-search'){state.inboxSearch=e.target.value;state.inboxPage=0;clearTimeout(typingTimeout);typingTimeout=setTimeout(()=>loadInboxLines().catch(e=>toast(e.message)),220)}
 if(e.target.id==='quote-search'){state.quoteSearch=e.target.value;state.quotePage=0;renderQuoteLines()}
 if(e.target.id==='quote-rate'){state.filters.rate=Number(e.target.value);$('#rate-label').textContent=state.filters.rate+'%';$('#rate-example').textContent=state.filters.method==='markup'?`100 成本 × (1 + ${state.filters.rate}%) = ${(100*(1+state.filters.rate/100)).toFixed(2)}`:`100 成本 / (1 - ${state.filters.rate}%) = ${(100/(1-state.filters.rate/100)).toFixed(2)}`}
});
$('#drawer-backdrop').addEventListener('click',closeDrawer);
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeDrawer();if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();nav('inbox');setTimeout(()=>$('#inbox-search')?.focus(),100)}});
$('#menu-toggle').addEventListener('click',()=>$('.sidebar').classList.toggle('open'));
// Start
async function enterWorkspace(){
 const identity=await api('/api/auth/me');
 document.querySelector('#session-role').textContent=identity.role==='reviewer'?'业务复核员':'管理员';
 if(identity.role==='reviewer')$$('.nav-link').forEach(b=>{if(['query','operations','audit','rules','connect','insight','quote'].includes(b.dataset.page))b.hidden=true});
 await render();
 document.querySelector('#nav').inert=false;
}
document.addEventListener('change', e=>{
 if(e.target.id==='eml-file') {
  const f=e.target.files?.[0]; $('#file-customer-field').hidden=!f || /\.eml$/i.test(f.name);
  $('#upload-preview').replaceChildren();
 }
});
document.querySelector('#sign-out').addEventListener('click', async()=>{try{await post('/auth/logout',{});location.assign('/login')}catch(e){toast(e.message)}});
document.addEventListener('DOMContentLoaded',()=>enterWorkspace().catch(errorPage),{once:true});

async function renderAudit(){const rows=await api('/api/audit');const ex=await api('/api/exceptions');$('#main').innerHTML=`<section class="page">${pageHead('AUDIT TRAIL','每次决策，留下记录。','按时间查看原件导入、字段修订、报价签核和文件导出，展开记录可核对操作依据。')}<article class="panel"><div class="panel-head"><h2>解析异常 / ${ex.parse_issues.length}</h2></div><div class="panel-body">${ex.parse_issues.map(x=>`<p class="issue">${esc(x.source_ref)}：${esc(x.reason)}</p>`).join('')||'当前没有记录的解析异常'}</div></article><article class="panel" style="margin-top:20px"><div class="panel-head"><h2>最近 ${rows.length} 条操作</h2></div><div class="panel-body">${rows.map(x=>`<details style="padding:12px;border-bottom:1px solid #ddd"><summary>${esc(x.at)} · ${esc(x.action)} · ${esc(x.actor)} · ${esc(x.entity_id)}</summary><pre style="max-height:350px;overflow:auto;white-space:pre-wrap;word-break:break-all">${esc(x.detail_json)}</pre></details>`).join('')}</div></article></section>`}
async function renderHistory(){const [rows,commercial]=await Promise.all([api('/api/quotes'),api('/api/commercial-quotes')]);if(state.page!=='history')return;$('#main').innerHTML=`<section class="page">${pageHead('QUOTE ARCHIVE','第六步：下载正式报价','打开已批准报价，核对客户、版本和金额后下载 PDF 或 Excel。')}<article class="panel"><div class="panel-body"><h2>已批准的商业报价</h2>${recentQuoteLinks(commercial.rows.filter(q=>q.status==='approved'))}</div></article><h2>快速核价工具记录</h2><article class="panel"><div class="panel-body">${rows.map(x=>`<div class="filter-bar"><span class="mono">${esc(x.id)} / v${x.version}</span><span>${esc(x.created_at)} · ${esc(x.status)}</span><button class="btn small" data-saved-quote="${esc(x.id)}">打开复核 ↗</button></div>`).join('')||'尚无保存报价，请在核价工作台执行一次核价。'}</div></article></section>`}
async function renderRules(){const r=await api('/api/rules');const m=await api('/api/analytics/metrics');$('#main').innerHTML=`<section class="page">${pageHead('PRICING RULES','规则透明，金额确定。','当前报价币种 CNY；价格资源表汇率是唯一外币换算依据。')}<article class="panel"><div class="panel-body"><div class="field"><label>默认报价基准日</label><input id="rule-asof" type="date" value="${esc(r.asof)}"></div><div class="field"><label>方法</label><select id="rule-method"><option value="markup" ${r.method==='markup'?'selected':''}>成本加价率</option><option value="margin" ${r.method==='margin'?'selected':''}>目标毛利率</option></select></div><div class="field"><label>比例 %</label><input id="rule-rate" type="number" min="0" max="99" step="0.01" value="${esc(r.rate)}"></div><p>100 成本：20% 加价 = 120；20% 目标毛利 = 125。单价先按 HALF_UP 保留两位，再乘数量。</p><button class="btn primary" data-action="save-rules">保存默认规则</button><p class="issue">不会修改已归档报价。库存为单份草案可用量检查；跨报价库存预留尚未实现。</p></div></article><article class="panel" style="margin-top:20px"><div class="panel-body"><h3>统计口径</h3><p>RFQ ${m.rfq_count} 份 / 明细 ${m.line_count} 行 / 独立件号 ${m.part_count} 个</p><p>${esc(m.amount_note)}</p><p>历史询价金额：未提供。已保存报价建议金额合计 CNY ${esc(m.quote_draft_amount_cny)}（可包含多个方案，不代表收入）。</p></div></article></section>`}
async function saveRules(){try{await api('/api/rules',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({asof:$('#rule-asof').value,method:$('#rule-method').value,rate:$('#rule-rate').value})});state.rulesLoaded=false;toast('默认规则已保存')}catch(e){toast(e.message)}}
async function approveQuote(){try{const r=state.quoteReport;if(!r) return;state.quoteReport=await api('/api/quotes/'+r.quote_id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:r.version,actor:$('#review-actor').value.trim(),reason:$('#review-reason').value.trim(),approve:true,confirm_constraints:$('#review-confirm').checked})});$('#quote-result').innerHTML=reportHtml(state.quoteReport);toast('人工确认已保存，报价版本已锁定')}catch(e){toast('未确认：'+e.message)}}
async function editQuoteLine(id){const r=state.quoteReport.lines.find(x=>x.line_id===id);$('#drawer-content').innerHTML=`<div class="drawer-top"><h2>人工复核 / ${esc(r.part_number)}</h2><button class="drawer-close" data-action="close-drawer">×</button></div><div class="field"><label>单价 CNY（留空保留计算价格）</label><input id="edit-price" type="number" min="0.01" step="0.01" placeholder="${esc(r.unit_quote_cny||'待核价')}"></div><div class="field"><label>价格凭据（调整单价必填）</label><input id="edit-evidence" placeholder="供应商报价编号 / 文件位置"></div><div class="field"><label>件状</label><input id="edit-condition" value="${esc(r.condition)}"></div><div class="field"><label>交期</label><input id="edit-lead" value="${esc(r.lead_days)}"></div><div class="field"><label>操作人</label><input id="edit-actor"></div><div class="field"><label>修改原因</label><input id="edit-reason"></div><input id="edit-line" type="hidden" value="${id}"><p class="issue">调整会保存原始计算、价格凭据和原因。已确认报价不能修改。</p><button class="btn primary" data-action="save-line-edit">保存复核修改</button>`;$('#drawer-backdrop').classList.remove('hidden');$('#drawer').classList.remove('hidden')}
async function saveLineEdit(){try{const r=state.quoteReport;const patch={line_id:Number($('#edit-line').value),condition:$('#edit-condition').value,lead_days:$('#edit-lead').value};if($('#edit-price').value){patch.unit_price_cny=$('#edit-price').value;patch.evidence_ref=$('#edit-evidence').value}state.quoteReport=await api('/api/quotes/'+r.quote_id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:r.version,actor:$('#edit-actor').value.trim(),reason:$('#edit-reason').value.trim(),patches:[patch]})});closeDrawer();$('#quote-result').innerHTML=reportHtml(state.quoteReport);toast('修改已保存，原始询价保持可追溯')}catch(e){toast(e.message)}}

async function aiExtractEmail(button){if(!state.emailId){toast('先选择一封来件');return}button.disabled=true;button.textContent='Genesis正在提取…';try{showAIExtraction(await post('/api/emails/'+encodeURIComponent(state.emailId)+'/extract',{}))}catch(e){toast('提取未完成：'+e.message)}finally{button.disabled=false;button.textContent='Genesis 补充提取 ↗'}}
async function savedAIExtraction(){try{const r=await api('/api/emails/'+encodeURIComponent(state.emailId)+'/extractions');if(!r.rows.length){toast('当前邮件尚无AI提取记录');return}showAIExtraction(await api('/api/extractions/'+r.rows[0].id))}catch(e){toast(e.message)}}
function reviewSource(run) {
  const mail = state.emails.find(item => item.email_id === run.email_id);
  const subject = mail?.subject || '';
  const text = String(run.input_text || '');
  const ids = [...new Set(subject.match(/\bRFQ[-_][A-Z0-9]+(?:[-_.][A-Z0-9]+)*/gi) || [])];
  return {subject, text, rfq:ids.length === 1 ? ids[0] : ''};
}

function reviewDescription(run, line, text, offers) {
  if (run.lines.length !== 1) return '';
  const paragraphs = text.split(/\r?\n/).filter(s => s.trim() && !/^FILE /.test(s));
  const labeled = paragraphs.map(s => s.match(/^\s*(?:技术描述|规格|规格型号|description|specification)\s*[:：]\s*(.+?)\s*$/i)).filter(Boolean);
  if (labeled.length === 1 && labeled[0][1].length <= 1000) return labeled[0][1];
  if (paragraphs.length === 1 && line.evidence && paragraphs[0].includes(line.evidence)) {
    const explicit=paragraphs[0].match(/(?:[，,；;。]\s*)规格(?:为|是|[:：])\s*([^，,；;。！？\n]{1,200})[。；;，,]?/g);
    if(explicit?.length===1)return explicit[0].replace(/^[，,；;。]\s*规格(?:为|是|[:：])\s*/,'').replace(/[。；;，,]$/,'').trim();
  }
  if (paragraphs.length !== 1 || !line.part_number || !line.evidence || !paragraphs[0].includes(line.evidence)) return '';
  // Only propose a complete clause in a one-line inquiry. Keep model numbers and units case-sensitive.
  const clauses = paragraphs[0].split(/[,，;；。]/).map(s => s.trim().replace(/\.$/, ''));
  const specs = new Set(offers.filter(o => o.review_status === 'confirmed' && o.part_number === line.part_number)
    .map(o => o.specification).filter(s => s && clauses.some(c => c === s ||
      (/^[A-Z][a-z]{3,}\s/.test(s) && c === s[0].toLowerCase()+s.slice(1)))));
  return specs.size === 1 ? [...specs][0] : '';
}

function reviewField(label, cls, value, attrs='') {
  return `<label class="field">${label}<input class="${cls}" value="${esc(value ?? '')}" ${attrs}></label>`;
}

function savedReview(receipt) {
  const ids = receipt.line_ids || [];
  state.selected = new Set(ids);
  $('#drawer-content').innerHTML = `<div class="drawer-top"><h2>客户需求已保存</h2><button class="drawer-close" data-action="close-drawer" aria-label="关闭">×</button></div>
    <p role="status" class="info-strip" id="ai-saved-summary">已保存 ${ids.length} 行需求，可继续核对供应商报价。</p>
    <button class="btn primary" id="ai-next-supplier">下一步：核对供应商报价 →</button>`;
  $('#ai-next-supplier').onclick = async () => { closeDrawer(); await nav('commercial'); };
  return $('#ai-saved-summary');
}

async function showSavedReview(receipt) {
  const summary = savedReview(receipt);
  const ids = new Set(receipt.line_ids || []);
  if (!ids.size) return;
  try {
    const rows = await Promise.all([...ids].slice(0,3).map(id => api('/api/lines/'+encodeURIComponent(id))));
    if (summary.isConnected) {
      const labels = rows.map(l => l.part_number+' × '+l.quantity+' '+l.unit);
      summary.textContent = '已保存 '+labels.join('、')+(ids.size>3?' 等 '+ids.size+' 行需求。':'。');
    }
  } catch { /* The confirmation receipt already establishes the saved rows. */ }
}

function showAIExtraction(run) {
  state.aiRun=run;
  $('#drawer-backdrop').classList.remove('hidden');
  $('#drawer').classList.remove('hidden');
  $('#drawer').setAttribute('aria-hidden','false');
  if (run.status === 'confirmed' && run.confirmed) {showSavedReview(run.confirmed);return;}
  const source=reviewSource(run);
  const role=$('#session-role')?.textContent.trim() || '';
  const actor=['管理员','业务复核员'].includes(role)?role:'';
  const candidates=run.lines.map((line,i)=>`<fieldset class="panel ai-candidate" data-index="${i}" style="padding:12px;margin:12px 0">
    <legend><label><input type="checkbox" class="ai-selected" checked> 采用需求 ${i+1}</label></legend>
    <blockquote>原文证据：${esc(line.evidence||'请在原文中核对')}</blockquote>
    ${reviewField('件号（必填）','ai-part',line.part_number,'maxlength="150"')}
    ${reviewField('数量（必填）','ai-qty',line.quantity,'type="number" min="1" step="1"')}
    ${reviewField('单位（必填）','ai-unit',line.unit,'maxlength="30"')}
    ${reviewField('技术描述（供应商比价时使用）','ai-description',reviewDescription(run,line,source.text,[]),'maxlength="1000"')}
    <small class="ai-desc-note"></small>
    ${reviewField('件状','ai-condition',line.condition,'maxlength="30"')}
    </fieldset>`).join('');
  $('#drawer-content').innerHTML=`<div class="drawer-top"><h2>核对客户询价</h2><button class="drawer-close" data-action="close-drawer" aria-label="关闭">×</button></div>
    <section class="info-strip"><strong>邮件主题</strong><p>${esc(source.subject||'原邮件未提供主题')}</p><strong>核对原文</strong>
      <pre style="white-space:pre-wrap;overflow:auto;max-height:240px">${esc(source.text||'请打开原件核对')}</pre></section>
    <details><summary>模型与执行详情</summary><p>${esc(run.provider)} · ${esc(run.model)} · ${esc(run.run_id)}<br>${esc(run.execution_id||run.response_id||'')}<br>输入 SHA256：${esc(run.input_sha256||'')}</p></details>
    <form id="ai-review-form" novalidate>
      <label class="field">来源询价号（必填）<input id="ai-rfq" maxlength="100" value="${esc(source.rfq)}" placeholder="填写客户邮件或附件中的询价号"></label>
      <div id="ai-lines">${candidates||'<p>没有可确认的建议行，请核对原件后补录。</p>'}</div>
      <label class="field">复核人（必填）<input id="ai-actor" maxlength="100" value="${esc(actor)}"></label>
      <label><input type="checkbox" id="ai-source-confirm"> 已逐项对照原文，确认以上内容一致</label>
      <label class="field">修改说明<input id="ai-reason" maxlength="1000" placeholder="修改已有建议或补充其他依据时填写"></label>
      <p id="ai-review-error" class="issue" role="alert"></p>
      <button type="submit" class="btn primary block" data-action="confirm-ai-extraction" ${run.simulated||!run.lines.length?'disabled':''}>确认选中行入库</button>
    </form>`;
  const form=$('#ai-review-form');
  form.onsubmit=e=>{e.preventDefault();confirmAIExtraction(form,run);};
  form.oninput=e=>{e.target.removeAttribute('aria-invalid');$('#ai-review-error').textContent='';if(e.target.matches('.ai-description'))e.target.dataset.edited='true';};
  if(run.lines.length===1 && !$('.ai-description',form).value) {
    const input=$('.ai-description',form);
    api('/api/supplier-offers').then(({rows})=>{
      if(!form.isConnected||input.dataset.edited||input.value)return;
      const spec=reviewDescription(run,run.lines[0],source.text,rows);
      if(spec){input.defaultValue=spec;input.value=spec;$('.ai-desc-note',form).textContent='已对照邮件片段带出供应商原件中的规格写法，请核实。';}
    }).catch(()=>{});
  }
}

async function confirmAIExtraction(form,run) {
  const button=$('button[type="submit"]',form);
  if(button.disabled)return;
  const val=(s,n=form)=>$(s,n).value.trim();
  const error=$('#ai-review-error',form);
  function invalid(input,message){
    error.textContent=message;
    input.setAttribute('aria-invalid','true');input.focus();return false;
  }
  const selected=$$('.ai-candidate',form).filter(n=>$('.ai-selected',n).checked);
  if(!selected.length)return invalid($('.ai-selected',form)||button,'请至少选择一行需求。');
  if(!val('#ai-rfq'))return invalid($('#ai-rfq',form),'请填写来源询价号，可在上方邮件主题或原文中查找。');
  const lines=[];let changed=false;
  for(const row of selected){
    const index=Number(row.dataset.index),orig=run.lines[index];
    const part=val('.ai-part',row),unit=val('.ai-unit',row),condition=val('.ai-condition',row),qty=Number(val('.ai-qty',row));
    if(!part)return invalid($('.ai-part',row),'请填写所选行的件号。');
    if(!Number.isSafeInteger(qty)||qty<1)return invalid($('.ai-qty',row),'请填写大于零的整数数量。');
    if(!unit)return invalid($('.ai-unit',row),'请填写数量单位，例如 EA。');
    changed ||= Boolean(orig.part_number && part!==orig.part_number || orig.quantity!=null && qty!==orig.quantity ||
      orig.unit && unit!==orig.unit || orig.condition && condition!==orig.condition);
    for(const field of ['.ai-description','.ai-condition','.ai-part','.ai-unit']){
      const input=$(field,row);
      if(input.defaultValue.trim() && input.value.trim()!==input.defaultValue.trim())changed=true;
    }
    lines.push({source_index:index,part_number:part,quantity:qty,unit,condition,description:val('.ai-description',row),source_rfq_no:val('#ai-rfq')});
  }
  if(!val('#ai-actor'))return invalid($('#ai-actor',form),'请填写复核人。');
  if(!$('#ai-source-confirm',form).checked)return invalid($('#ai-source-confirm',form),'请先对照原文，并勾选核对确认。');
  changed ||= Boolean($('#ai-rfq',form).defaultValue && val('#ai-rfq')!==$('#ai-rfq',form).defaultValue);
  const note=val('#ai-reason');
  if((changed||note)&&note.length<3)return invalid($('#ai-reason',form),'请用至少三个字说明核对或修改依据。');
  error.textContent='';button.disabled=true;button.textContent='正在保存…';
  try{
    const receipt=await post('/api/extractions/'+encodeURIComponent(run.run_id)+'/confirm',{
      actor:val('#ai-actor'),reason:note||'逐项核对邮件原文，确认所选字段一致',confirm_source:true,lines});
    state.emails=[];state.allLines=[];
    if(!form.isConnected||state.aiRun!==run)return;
    state.emailId=run.email_id;state.inboxSearch='';state.inboxPage=0;
    showSavedReview(receipt);
    if(state.page==='inbox')renderInbox().catch(e=>toast(e.message));
  }catch(e){if(form.isConnected){error.textContent='保存未完成：'+e.message;error.scrollIntoView({block:'nearest'});}}
  finally{if(form.isConnected){button.disabled=false;button.textContent='确认选中行入库';}}
}

async function syncCloudQuote(button){if(!state.quoteReport?.quote_id)return;button.disabled=true;const old=button.textContent;button.textContent='写入并读回校验…';try{const r=await post('/api/quotes/'+state.quoteReport.quote_id+'/sync-matrixone',{});toast('云端快照已读回校验：'+r.payload_sha256.slice(0,12))}catch(e){toast('同步未确认成功：'+e.message)}finally{button.disabled=false;button.textContent=old}}

const catalogSpecs={
 lines:{title:'全部询价需求',note:'包含官方模拟邮件和后续导入邮件提取的需求。点击「来源」可核对原文件，并将需求加入核价。',columns:[['source_rfq_no','询价号'],['part_number','件号'],['quantity','数量'],['unit','单位'],['part_condition','件状'],['email_filename','来源邮件']]},
 historical:{title:'历史询价明细',note:'赛事官方历史询价模拟表，用于统计与参考；每条记录是物料明细，不等于一份订单。',columns:[['rfq_no','RFQ No'],['inquiry_date','询价日期'],['airline','客户'],['part_number','件号'],['quantity','数量'],['unit','单位'],['source_row','原表位置']]},
 prices:{title:'供应商价格资源',note:'赛事官方供应商模拟报价。显示原始价格，不代表今天仍可使用；有效期、件状、起订量和汇率须在核价时检查。',columns:[['resource_id','资源编号'],['part_number','件号'],['supplier','供应商'],['unit_price','原币单价'],['currency','币种'],['condition','件状'],['moq','起订量'],['valid_until','有效期至']]},
 costs:{title:'内部物料成本',note:'赛事官方内部成本模拟表，为规则核价提供成本依据，不代表实时库存或真实采购承诺。',columns:[['part_number','件号'],['description','描述'],['standard_cost','标准成本'],['currency','币种'],['inventory','库存'],['part_condition','件状'],['source_row','原表位置']]}
};
async function renderCatalog(){state.catalog ||= {kind:'lines',search:'',page:0};const spec=catalogSpecs[state.catalog.kind];$('#main').innerHTML=`<section class="page">${pageHead('DATA / DETAILS',spec.title,spec.note,`<button class="btn" data-go="overview">返回总览</button>`)}<div class="catalog-tabs">${Object.entries(catalogSpecs).map(([kind,s])=>`<button class="query-chip ${kind===state.catalog.kind?'active':''}" data-catalog="${kind}">${s.title}</button>`).join('')}</div><article class="panel"><div class="filter-bar"><input class="catalog-search" id="catalog-search" aria-label="搜索数据明细" placeholder="搜索件号、询价号或供应商…" value="${esc(state.catalog.search)}"><button class="btn" data-catalog-action="search">搜索</button></div><div id="catalog-result" aria-live="polite">正在读取明细…</div></article></section>`;await loadCatalog()}
let catalogRequest=0;
async function loadCatalog(){const request=++catalogRequest;const {kind,search,page}=state.catalog;const spec=catalogSpecs[kind];const params=new URLSearchParams({search,limit:'25',offset:String(page*25)});const r=await api((kind==='lines'?'/api/lines':'/api/catalog/'+kind)+'?'+params);if(request!==catalogRequest||state.page!=='catalog'||kind!==state.catalog.kind)return;if(page>0&&page*25>=r.total){state.catalog.page=0;return loadCatalog()}state.catalogRows=r.rows;state.catalogFiles=r.source_files||[];
 $('#catalog-result').innerHTML=`${kind!=='lines'?`<div class="catalog-source"><span class="tag">赛事模拟数据</span> 来源原表：${state.catalogFiles.map(f=>`<a href="/api/sources/${esc(f.id)}/download" download="${esc(f.filename)}">${esc(f.filename)}</a>`).join('、')||'暂无原文件记录'}。可下载对照「原表位置」。${kind==='prices'?state.catalogFiles.map(f=>`<button class="btn small" data-resource-review="${esc(f.id)}">将原表转入供应商复核</button>`).join(''):''}</div>`:''}${r.rows.length?`<div class="table-wrap"><table class="data-table catalog-table"><thead><tr>${spec.columns.map(([,label])=>`<th>${label}</th>`).join('')}<th>操作</th></tr></thead><tbody>${r.rows.map((row,i)=>`<tr>${spec.columns.map(([key])=>`<td>${esc(row[key]??'—')}</td>`).join('')}<td><button class="row-action" ${kind==='lines'?`data-line="${row.id}"`:`data-catalog-record="${i+1}"`}>${kind==='lines'?'来源 ↗':'详情 ↗'}</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="table-empty">没有符合条件的记录，请更换关键词。</div>'}<div class="table-foot"><span>显示 ${r.total?page*25+1:0}–${page*25+r.rows.length} / ${r.total} 条</span><div><button class="btn small" data-catalog-action="prev" ${page===0?'disabled':''}>上一页</button> <button class="btn small" data-catalog-action="next" ${(page+1)*25>=r.total?'disabled':''}>下一页</button></div></div>`;
}
function openCatalogRecord(index){const row=state.catalogRows[index-1];if(!row)return;const labels=Object.fromEntries(Object.values(catalogSpecs).flatMap(s=>s.columns));Object.assign(labels,{description:'描述',inquiry_no:'询价单号',urgency:'紧急程度',line_no:'行号',part_condition:'件状',product_scope:'产品范围',deadline:'截止日期',source_row:'原表位置',supplier_code:'供应商编码',fx_to_cny:'换算 CNY 汇率',lead_days:'交期天数',in_stock:'是否现货',certificate:'证书',quote_date:'报价日期',status:'原表价格状态',warehouse:'仓库',avg_cost:'平均成本',last_purchase_price:'最近采购价',updated_at:'成本更新日期'});$('#drawer-content').innerHTML=`<div class="drawer-top"><h2>${esc(row.part_number||'记录详情')}</h2><button class="drawer-close" data-action="close-drawer" aria-label="关闭">×</button></div><p class="info-strip">赛事官方模拟数据 · 原始字段。价格是否可用须结合具体需求执行核价。</p><dl>${Object.entries(row).filter(([key])=>key!=='id').map(([key,value])=>`<div class="kv"><dt>${esc(labels[key]||key)}</dt><dd>${esc(value??'—')}</dd></div>`).join('')}</dl><h3>来源原表</h3>${state.catalogFiles.map(f=>`<p><a href="/api/sources/${esc(f.id)}/download" download="${esc(f.filename)}">${esc(f.filename)}</a></p>`).join('')}</div>`;$('#drawer-backdrop').classList.remove('hidden');$('#drawer').classList.remove('hidden');$('#drawer').setAttribute('aria-hidden','false')}
document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.id==='catalog-search')$('[data-catalog-action="search"]').click()});

async function openManualIntake(){if(!state.emailId){toast('先选择需要补录的邮件');return}try{const sources=await api('/api/emails/'+encodeURIComponent(state.emailId)+'/sources');state.manualEntryKey=crypto.randomUUID();$('#drawer-content').innerHTML=`<div class="drawer-top"><h2>人工补录 · 保留原始来源</h2><button class="drawer-close" data-action="close-drawer">×</button></div><p class="issue">适用于扫描件或无法解析的版式。请下载并核对原文件；手填定位由复核人负责，系统不会将其冒充自动识别结果。此处不填写价格。</p><div class="field"><label>下载核对原文件</label>${sources.map(x=>`<p><a href="/api/sources/${esc(x.id)}/download" download="${esc(x.filename)}">${esc(x.filename)}</a></p>`).join('')}</div><div class="field"><label>来源文件</label><select id="manual-source">${sources.map(x=>`<option value="${esc(x.id)}">${esc(x.filename)} / ${esc(x.kind)}</option>`).join('')}</select></div><div class="field"><label>来源定位（页码 / 工作表 / 单元格）</label><input id="manual-locator"></div>${[['rfq','询价单号'],['part','件号'],['qty','数量（正整数）'],['unit','单位'],['condition','件状（未知可留空）'],['actor','复核人'],['reason','补录原因']].map(([id,label])=>`<div class="field"><label>${label}</label><input id="manual-${id}"></div>`).join('')}<label><input id="manual-confirm" type="checkbox"> 已逐项对照原文件核对</label><button class="btn primary" data-action="save-manual-intake">保存需求并核价</button>`;$('#drawer-backdrop').classList.remove('hidden');$('#drawer').classList.remove('hidden')}catch(e){toast(e.message)}}
async function saveManualIntake(){try{const r=await post('/api/emails/'+encodeURIComponent(state.emailId)+'/manual-lines',{entry_key:state.manualEntryKey,source_id:$('#manual-source').value,source_locator:$('#manual-locator').value,source_rfq_no:$('#manual-rfq').value,part_number:$('#manual-part').value,quantity:Number($('#manual-qty').value),unit:$('#manual-unit').value,condition:$('#manual-condition').value,actor:$('#manual-actor').value,reason:$('#manual-reason').value,confirm_source:$('#manual-confirm').checked});state.emails=[];state.allLines=[];state.selected=new Set(r.line_ids);closeDrawer();nav('quote');toast('人工补录已保存，来源可追溯')}catch(e){toast('未保存：'+e.message)}}


document.addEventListener('keydown',e=>{if(e.key==='Enter'&&e.target.id==='nl-question'&&!$('[data-action="ask-insight"]').disabled)$('[data-action="ask-insight"]').click()});
