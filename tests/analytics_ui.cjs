const assert = require('node:assert/strict');
const fs = require('node:fs');
const {JSDOM} = require('jsdom');

async function run(check) {
  const html = fs.readFileSync('web/index.html', 'utf8');
  const window = new JSDOM(html,{runScripts:'outside-only',url:'https://example.invalid'}).window;
  await new Promise(resolve => window.addEventListener('load', resolve, {once:true}));
  const parts = Array.from({length:1201}, (_, id) => ({id:id+1}));
  window.fetch = async path => {
    const url = new URL(path,window.location.href);
    if (url.pathname === '/api/lines') {
      const start = Number(url.searchParams.get('offset'));
      const count = Number(url.searchParams.get('limit'));
      return {ok:true,json:async () => ({total:parts.length,rows:parts.slice(start,start+count)})};
    }
    const values = {
      '/api/overview':{history_lines:3,history_rfq_groups:2},
      '/api/integration':{active_provider:'mock'},
      '/api/query-center/status':{historical_reference_date:'2026-11-10'},
      '/api/analytics':{question:'每月询价趋势',rows:[{月份:'2026-11',询价份数:2}],dataset_rows:3}
    };
    assert.ok(Object.hasOwn(values,url.pathname),url.pathname);
    return {ok:true,json:async () => values[url.pathname]};
  };
  window.eval(fs.readFileSync('web/app.js','utf8') + '\nwindow.auditUI = {renderInsight,fillInsight,getAllLines}; state.page="insight";');
  if (check==='paging') {
    const rows = await window.auditUI.getAllLines();
    assert.deepEqual(Array.from(rows,r=>r.id),parts.map(r=>r.id));
  } else {
    await window.auditUI.renderInsight();
    assert.equal(window.document.querySelector('.chart-row-value').textContent,'2');
    assert.equal(window.document.querySelectorAll('.query-chip.active').length,1);
    assert.match(window.document.querySelector('#insight-table').textContent,/2026-11/);
    window.auditUI.fillInsight({question:'即将截止的询价',dataset_rows:3,
      rows:[{询价号:'RFQ-QA',航空公司:'合成客户',截止报价日期:'2026-11-15'}]});
    assert.equal(window.document.querySelectorAll('.chart-row-value').length,0);
    assert.match(window.document.querySelector('#chart-area').textContent,/明细/);
    assert.match(window.document.querySelector('#insight-table').textContent,/RFQ-QA/);
  }
  window.close();
}

Promise.allSettled(['analytics','paging'].map(run)).then(results => {
  for (const [i,result] of results.entries()) {
    if (result.status === 'rejected') {
      console.error(['analytics','paging'][i],result.reason.message.slice(0,120));process.exitCode=1;
    } else console.log(['analytics','paging'][i], 'passed');
  }
});
