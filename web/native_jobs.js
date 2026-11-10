'use strict';

async function openNativeRFQ() {
  const email = state.emailId;
  if (!email) return toast('请选择一封已上传的询价');
  const url = '/api/native-workflow/emails/' + encodeURIComponent(email) + '/runs';
  const panel = $('#drawer-content');
  const phases = {
    preparing: '准备原件', preflight_failed: '启动前检查未通过', dispatching: '已发起提交，等待回执',
    dispatch_unknown: '平台受理情况待核对', submitted: '已取得执行 ID', tracking: '跟踪平台状态',
    failed: '平台执行失败', verification_pending: '结果待验证', review_ready: '已验证，等待人工复核'
  };
  const wrapper = document.createElement('section');
  panel.replaceChildren(wrapper);
  $('#drawer-backdrop').classList.remove('hidden');
  $('#drawer').classList.remove('hidden');

  function draw(job) {
    const retry = !job || ['preflight_failed', 'preparing'].includes(job.phase);
    const reconcile = job && !job.execution_id && ['dispatch_unknown','dispatching'].includes(job.phase);
    wrapper.innerHTML = `<div class="drawer-top"><h2>MOI 原生作业</h2><button class="drawer-close" data-action="close-drawer">×</button></div>
      <p>${esc(email)}</p>${job ? `<p role="status">${esc(phases[job.phase] || job.phase)} · ${esc(job.receipt.platform_status || '')}</p>
      <p>询价引用 <code>${esc(job.ref)}</code><br>平台执行 ID <code>${esc(job.execution_id || '尚未取得')}</code></p>
      <p>${esc(job.error)}</p>${Object.entries(job.receipt.nodes || {}).map(([key,value]) =>
        `<p><code>${esc(key)}</code> · ${esc(value.status)}</p>`).join('')}` : '<p>此询价尚无原生作业。</p>'}
      ${retry ? '<label><input type="checkbox" class="synthetic"> 本次仅使用合成测试文件，提交原文至已配置的 MOI 工作区</label><p><button class="btn primary" data-op="start">启动原生提取</button></p>' : ''}
      ${job && !job.review_id ? '<button class="btn" data-op="refresh">刷新作业状态</button>' : ''}
      ${reconcile ? '<p>请先按询价引用核对 AI Studio 作业记录。</p><input class="eid" aria-label="待核对的执行 ID"><button class="btn" data-op="reconcile">核对并关联执行 ID</button>' : ''}
      ${job?.review_id ? '<button class="btn primary" data-op="review">打开建议与原文，人工复核</button>' : ''}`;
    wrapper.onclick = async (event) => {
      const button = event.target.closest('[data-op]');
      if (!button) return;
      button.disabled = true;
      try {
        const op = button.dataset.op;
        const jobUrl = '/api/native-workflow/runs/' + encodeURIComponent(job?.ref || '');
        if (op === 'start') {
          if (!wrapper.querySelector('.synthetic').checked) return toast('请先确认本次为合成测试文件');
          draw(await post(url, {synthetic_confirmed:true}));
        } else if (op === 'review') {
          const review = await api('/api/extractions/' + encodeURIComponent(job.review_id));
          if (wrapper.isConnected) showAIExtraction(review);
        } else if (op === 'reconcile') {
          draw(await post(jobUrl + '/reconcile', {execution_id:wrapper.querySelector('.eid').value.trim()}));
        } else if (job.execution_id) {
          draw(await post(jobUrl + '/refresh', {}));
        } else {
          draw((await api(url)).rows[0]);
        }
      } catch (error) { toast(error.message); }
      finally { button.disabled = false; }
    };
  }
  try { draw((await api(url)).rows[0]); }
  catch (error) { wrapper.textContent = error.message; }
}
