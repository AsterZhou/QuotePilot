'use strict';

async function openNativeRFQ() {
  const email = state.emailId;
  if (!email) return toast('请选择一封已上传的询价');
  const url = '/api/native-workflow/emails/' + encodeURIComponent(email) + '/runs';
  const panel = $('#drawer-content');
  const phases = {
    preparing:'准备中', preflight_failed:'处理失败，请查看原因', dispatching:'正在提交',
    dispatch_unknown:'等待平台确认受理', submitted:'正在提取', tracking:'正在提取',
    failed:'处理失败，请查看原因', verification_pending:'等待读取结果', review_ready:'处理成功，等待人工确认'
  };
  const wrapper = document.createElement('section');
  panel.replaceChildren(wrapper);
  $('#drawer-backdrop').classList.remove('hidden');
  $('#drawer').classList.remove('hidden');

  function draw(job) {
    const retry = !job || ['preflight_failed', 'preparing'].includes(job.phase);
    const reconcile = job && !job.execution_id && ['dispatch_unknown','dispatching'].includes(job.phase);
    wrapper.innerHTML = `<div class="drawer-top"><h2>AI 自动整理客户询价</h2><button class="drawer-close" data-action="close-drawer">×</button></div>
      <div aria-live="polite" class="job-progress"></div><p>确认使用合成文件，点击启动。稍候点击刷新进度，处理成功后打开建议，对照邮件核实字段并确认写入。</p><small>${esc(email)}</small>${job ? `<p role="status">${esc(phases[job.phase] || job.phase)}</p>
      <p role="alert">${esc(job.error)}</p><details><summary>技术详情 · 执行 ID 与节点</summary><p>询价引用 <code>${esc(job.ref)}</code><br>平台执行 ID <code>${esc(job.execution_id || '尚未取得')}</code></p>
      ${Object.entries(job.receipt.nodes || {}).map(([key,value]) =>
        `<p><code>${esc(key)}</code> · ${esc(value.status)}</p>`).join('')}</details>` : '<p>此询价尚无原生作业。</p>'}
      ${retry ? '<label><input type="checkbox" class="synthetic"> 本次仅使用合成测试文件，提交原文至已配置的 MOI 工作区</label><p><button class="btn primary" data-op="start">启动处理</button></p>' : ''}
      ${job && !job.review_id ? '<button class="btn" data-op="refresh">刷新处理进度</button>' : ''}
      ${reconcile ? '<p>请先按询价引用核对 AI Studio 作业记录。</p><input class="eid" aria-label="待核对的执行 ID"><button class="btn" data-op="reconcile">核对并关联执行 ID</button>' : ''}
      ${job?.review_id ? '<button class="btn primary" data-op="review">查看提取结果并核对原文</button>' : ''}`;
    wrapper.onclick = async (event) => {
      const button = event.target.closest('[data-op]');
      if (!button) return;
      button.disabled = true;
      try {
        const op = button.dataset.op;
        const jobUrl = '/api/native-workflow/runs/' + encodeURIComponent(job?.ref || '');
        if (op === 'start') {
          if (!wrapper.querySelector('.synthetic').checked) return toast('请先确认本次为合成测试文件');
          wrapper.querySelector('.job-progress').textContent='正在准备原文并提交处理，请稍候…';
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
      } catch (error) { wrapper.querySelector('.job-progress').textContent='操作未完成：'+error.message; toast(error.message); }
      finally { button.disabled = false; }
    };
  }
  try { draw((await api(url)).rows[0]); }
  catch (error) { wrapper.textContent = error.message; }
}
