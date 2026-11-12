"use strict";
const steps = ["载入询价", "复核需求", "确认供应商", "核算价格", "业务复核", "管理员审批", "正式交付"];
const labels = {lowest_cost:"最低成本", fastest:"最快交付", balanced:"成本与交期均衡"};
const $ = selector => document.querySelector(selector);
const enc = encodeURIComponent;
const esc = value => String(value == null ? "" : value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let state;
try { state=JSON.parse(sessionStorage.getItem("qp-stage-v1") || "null"); } catch {}
state ||= {step:0,offers:[],margin:"20",scheme:"lowest_cost"};
function save(){sessionStorage.setItem("qp-stage-v1",JSON.stringify(state));}
function note(s){$("#notice").textContent=s;}
async function request(path, options={}) {
  const response=await fetch(path,options);
  const body = await response.json().catch(()=>({}));
  if (!response.ok) {
    const detail = body.detail;
    const msg=typeof detail==="string" ? detail : Array.isArray(detail) ? detail.map(x=>x.msg).join("、") : "请求未完成";
    throw Error("HTTP "+response.status+" · "+msg);
  }
  return body;
}
const post=(path,data)=>request(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});
async function loginRole(role){
  const me=await fetch("/api/auth/me");
  if(me.ok && (await me.json()).role===role){state.role=role;save();return;}
  const data=await post("/desk/access/"+role,{});
  await post("/auth/login",data);
  const confirmed=await request("/api/auth/me");
  if(confirmed.role!==role)throw Error("角色校验失败，请重新进入本机演示。");
  state.role=role;save();
}
async function filePost(url,name){
  const sample=await fetch("/desk/sample/"+name);
  if(!sample.ok)throw Error("无法读取本机样例 "+name);
  const form=new FormData();form.append("file",await sample.blob(),name);
  return request(url,{method:"POST",body:form});
}
function go(step){state.step=step;save();draw();window.scrollTo(0,0);}
const head=(h,p)=>'<h1>'+esc(h)+'</h1><p class="intro">'+esc(p)+'</p>';
const box=(v,classes="")=>'<section class="panel '+classes+'">'+v+'</section>';
const button=(id,title,cls="")=>'<button id="'+id+'" class="'+cls+'">'+esc(title)+'</button>';
const link=(url,title,cls="")=>'<a href="'+esc(url)+'" class="'+cls+'" target="_blank" rel="noopener">'+esc(title)+'</a>';
const check=label=>'<label class="check"><input id="accept" type="checkbox"><span>'+esc(label)+'</span></label>';
const item=(k,v)=>'<div class="item"><small>'+esc(k)+'</small><strong>'+esc(v)+'</strong></div>';
const grid=(...items)=>'<div class="data">'+items.join("")+'</div>';
const actions=(...c)=>'<div class="actions">'+c.join("")+'</div>';
const qurl=()=>"/api/commercial-quotes/"+enc(state.quote.id);
function table(heads,rows){return '<div class="tablewrap"><table><thead><tr>'+heads.map(s=>'<th>'+esc(s)+'</th>').join("")+'</tr></thead><tbody>'+rows.map(r=>'<tr>'+r.map(v=>'<td>'+esc(v)+'</td>').join("")+'</tr>').join("")+'</tbody></table></div>';}
function risks(q){
  const issues=[...new Set(q.lines.flatMap(line=>line.selected?.calculation?.risks || []))];
  return issues.length ? box("<h3>待确认风险</h3>"+issues.map(s=>"<p>• "+esc(s)+"</p>").join(""),"warn") : "";
}
function pricingSummary(q){
  const s=q.lines[0]?.selected;
  if(!s)return box("当前方案没有匹配的供应商，请检查核价条件。","warn");
  return box('<small>建议客户总价 · CNY</small><div class="price">¥'+esc(q.suggested_total_cny)+'</div>'+
    grid(item("客户单价","¥"+s.calculation.suggested_unit_price_cny),item("成本","¥"+s.calculation.total_cost_cny),item("供应商",s.offer.supplier),item("交期",s.offer.lead_days+" 天")),"highlight");
}
let busy=false;
function on(id,action){const b=document.getElementById(id);if(!b)return;b.addEventListener("click",async()=>{
  if(busy)return;busy=true;b.disabled=true;note("处理中…");
  try{await action();note("");}catch(error){note(error.message);}
  finally{busy=false;b.disabled=false;}
});}
function requireCheck(){if(!$("#accept")?.checked)throw Error("请先勾选对原件或风险的确认，再继续。");}
function draw(){
  $("#steps").innerHTML=steps.map((s,i)=>'<li class="'+(i===state.step?"active":i<state.step?"done":"")+'" '+(i===state.step?'aria-current="step"':'')+'><span class="number">'+String(i+1).padStart(2,"0")+'</span>'+s+'</li>').join("");
  $("#role").textContent={admin:"管理员",reviewer:"业务复核员"}[state.role]||"尚未登录";
  $("#workbench").hidden=!state.role;note("");
  const view=$("#stage");let html="";
  if(state.step===0){
    html=head("为三只阀件报价","从一份已验证的合成询价开始。核对需求、比较供应商，再把一份获批报价交给客户。")+
      box(grid(item("案例","RFQ-START-003"),item("产品","PN-0001"),item("采购数量","3 EA")))+
      box('<h3>客户来件</h3><div class="document">RFQ-START-003 | Three sample valves\nPart Number: PN-0001\nQuantity: 3\nDescription: Synthetic valve spec A</div>'+
          actions(link("/desk/sample/email.txt","查看合成原件 ↗")))+
      actions(button("next","载入合成询价"))+'<p class="meta">点击后，以业务复核员登录，预览并导入带标签的 EML 文件。</p>';
  } else if(state.step===1){
    const packet=state.packet,line=packet.line;
    const rows=packet.fields.filter(f=>["part_number","quantity","unit","description","part_condition"].includes(f.field)).map(f=>[f.field,f.current_value,f.snippet||"—"]);
    html=head("逐项复核客户需求","对照原件检查型号、数量、单位与规格。确认后，系统会为这条询价记录复核版本。")+
      box('<h3>'+esc(line.source_rfq_no)+'</h3>'+table(["字段","当前值","原件摘录"],rows)+actions(link("/desk/sample/email.txt","查看合成原件 ↗")))+
      box('<label class="ctrl">确认数量（EA）<input id="qty" type="number" min="1" step="1" max="999999" value="'+esc(line.quantity)+'"></label>'+
      check("我已对照客户原件核实需求。数量若被修订，将记入字段修订记录。"))+
      actions(button("next","确认需求，读取三家报价"));
  } else if(state.step===2){
    const ext=state.extraction;
    html=head("供应商给了三个选择","三页供应商 PDF 已经上传。系统从这些原件提取候选值，核对后才把记录加入核价池。")+
      box('<h3>供应商报价 · CNY</h3>'+table(["供应商","单价","数量门槛","交期","原件位置"],ext.candidates.map(c=>[c.values.supplier,"¥"+c.values.unit_price,c.values.moq,c.values.lead_days+" 天",c.field_evidence.part_number?.locator]))+
      actions(link("/desk/sample/suppliers.pdf","打开本次三页供应商 PDF ↗"))+
      '<p class="meta">演练原件日期随启动日更新，价格、交期和规格沿用已核验样例。报价文件由本地规则读取。</p>'+
      check("已对照三页 PDF，确认三家的价格、交期和规格。"))+actions(button("next","确认三家原件"));
  } else if(state.step===3){
    html=head("选择报价目标","改变毛利率或选价策略，可以看到真实计算的建议售价。每次重新核算都会生成独立草稿。")+
      box('<div class="flex"><label class="ctrl">选价策略<select id="scheme">'+Object.entries(labels).map(([v,k])=>'<option value="'+v+'" '+(state.scheme===v?"selected":"")+'>'+k+'</option>').join("")+'</select></label>'+
      '<label class="ctrl">目标毛利率（%）<input id="margin" type="number" min="0" max="99" step="0.1" value="'+esc(state.margin)+'"></label></div><p class="meta">加工费 ¥1 / EA，整行其他成本 ¥2，客户报价有效期 14 天。金额按分舍入。</p>')+actions(button("next","生成报价草稿"));
  } else if(state.step===4){
    html=head("业务复核建议售价","对照成本、数量与客户总价。提交后，本份草稿将进入管理员审批。")+
      pricingSummary(state.quote)+risks(state.quote)+box('<p class="code">'+esc(state.quote.id)+' · v'+esc(state.quote.version)+'</p>'+
      check("我已核对建议售价、供应商交期和本份报价的风险说明。"))+
      actions(button("next","提交业务复核"),button("adjust","调整条件并重新核价","textbtn"));
  } else if(state.step===5){
    html=head("由另一个账户审批","业务复核已经提交。演示者现在可以切换至本机管理员账户，确认风险并决定是否批准。")+
      pricingSummary(state.quote)+risks(state.quote)+box(check("管理员已核实风险，认可本份报价的成本、交期和舍入结果。")+
      '<p class="meta">要展示保护机制，可先留空直接提交。系统会返回真实的阻断原因，随后勾选再试。</p>')+
      actions(button("next","切换管理员并审批"));
  } else if(state.step===6){
    const q=state.quote,a=state.audit;
    html=head("正式报价已就绪","PDF 与 Excel 由同一份已获批版本生成。打开文件核对件号、单价、总价及版本号。")+
      pricingSummary(q)+box('<h3>客户文件</h3><div class="code">'+esc(q.id)+' · v'+esc(q.version)+'</div>'+
      actions(link(qurl()+"/export/pdf","下载 PDF","btn"),link(qurl()+"/export/xlsx","下载 Excel","btn")))+
      box('<h3>审批轨迹</h3>'+table(["记录","执行账户","版本"],(q.approval_history||[]).map(e=>[({draft:"已建草稿",business_reviewed:"已业务复核",approved:"批准交付"}[e.to_status]||e.to_status),e.account||"—",e.version]))+
      (a?'<p class="meta">当前审计链校验 '+esc(a.valid?"通过":"未通过")+'，覆盖 '+esc(a.checked)+' 条记录。</p>':'')+
      actions(button("verify","重新校验审计记录","textbtn"),link("/","打开完整工作台 ↗")))+
      '<p class="meta">重新双击启动文件可开始另一场空白演练。已下载的文件可独立保留。</p>';
  }
  view.innerHTML=html;
  on("next",forward);on("adjust",()=>go(3));on("verify",async()=>{state.audit=await request("/api/audit/verify");save();draw();});
}
async function forward(){
  if(state.step===0){
    await loginRole("reviewer");
    await filePost("/api/emails/preview","structured-backup.eml");
    const imported=await filePost("/api/emails/import","structured-backup.eml");
    const lines=await request("/api/lines?email_id="+enc(imported.email_id));
    if(lines.rows.length!==1)throw Error("本案例应得到一条询价行。请打开完整工作台检查导入记录。");
    state.lineId=lines.rows[0].id;state.packet=await request("/api/lines/"+state.lineId+"/field-evidence");go(1);
  } else if(state.step===1){
    requireCheck();
    const qty=Number($("#qty").value);
    if(!Number.isInteger(qty)||qty<=0||qty>999999)throw Error("请输入 1 至 999999 的整数数量。");
    const base="/api/lines/"+state.lineId;
    const packet=await request(base+"/field-evidence");
    if(packet.review.status!=="confirmed" || Number(packet.line.quantity)!==qty){
      const changes=Number(packet.line.quantity)===qty ? {}:{quantity:qty};
      state.packet=await post(base+"/review-fields",{version:packet.review.version,changes,actor:"现场业务复核员",reason:"对照本机合成询价原件复核数量和规格",confirm_source:true});save();
    }
    if(!state.sourceId){state.sourceId=(await filePost("/api/supplier-offers/sources","suppliers.pdf")).source_id;save();}
    state.extraction=await request("/api/supplier-offers/sources/"+enc(state.sourceId)+"/extract",{method:"POST"});
    if(state.extraction.candidates.length!==3 || state.extraction.candidates.some(c=>c.missing_fields.length))throw Error("供应商候选字段不完整，请核对实际 PDF 和解析版本。");
    go(2);
  } else if(state.step===2){
    requireCheck();
    for(const c of state.extraction.candidates){
      const row=state.offers[c.index]||{};
      const e=c.field_evidence.part_number;
      if(!row.id){
        const offer=await post("/api/supplier-offers",{...c.values,source_id:state.sourceId,source_locator:e.locator,source_excerpt:e.raw_text,
          extraction_run_id:state.extraction.id,extraction_candidate:c.index});
        row.id=offer.id;state.offers[c.index]=row;save();
      }
      if(!row.done){
        await post("/api/supplier-offers/"+enc(row.id)+"/confirm",{version:1,actor:"现场业务复核员",reason:"逐页核实价格、规格与交期"});
        row.done=true;save();
      }
    }
    go(3);
  } else if(state.step===3){
    const margin=Number($("#margin").value);
    if($("#margin").value===""||!Number.isFinite(margin)||margin<0||margin>99)throw Error("毛利率应在 0% 至 99% 之间。");
    state.margin=String(margin);state.scheme=$("#scheme").value;const dates=await request("/desk/dates");
    state.quote=await post("/api/commercial-quotes",{...dates,line_ids:[state.lineId],target_margin:(margin/100).toFixed(5),scheme:state.scheme,
      line_costs:{[state.lineId]:{processing_per_unit_cny:"1",other_total_cny:"2"}},company_name:"合成测试公司",company_contact:"Demo sales",
      customer_name:"合成测试客户",customer_contact:"buyer@example.invalid",delivery_terms:"EXW synthetic",payment_terms:"Net 30",remarks:"SYNTHETIC DEMONSTRATION ONLY"});
    go(4);
  } else if(state.step===4){
    requireCheck();await loginRole("reviewer");const q=await request(qurl());
    if(q.status==="draft")state.quote=await post(qurl()+"/review",{version:q.version,actor:"现场业务复核员",reason:"已核对原件、成本、建议售价及交期",confirm_risks:true});
    else state.quote=q;
    go(5);
  } else if(state.step===5){
    const ack=$("#accept").checked;await loginRole("admin");$("#role").textContent="管理员";
    const q=await request(qurl());
    if(q.status!=="approved")await post(qurl()+"/approve",{version:q.version,actor:"现场管理员",reason:"管理员已审核条款、交期与舍入风险",confirm_risks:ack});
    state.quote=await request(qurl());state.audit=await request("/api/audit/verify");go(6);
  }
}
draw();
