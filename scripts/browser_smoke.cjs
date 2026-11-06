// Optional: npm install playwright && npx playwright install chromium
const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto((process.env.QUOTEPILOT_URL||'http://127.0.0.1:8765'));if(process.env.QA_FONT_CSS){await page.addStyleTag({content:fs.readFileSync(process.env.QA_FONT_CSS,'utf8')});await page.evaluate(()=>document.fonts.ready)}
 await page.getByRole('heading',{name:'每份报价，'}).waitFor().catch(()=>page.waitForSelector('.hero'));
 await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:'evidence/overview.png',fullPage:true});
 await page.locator('[data-page="quote"]').click();await page.locator('[data-action="preset-good"]').click();
 await page.locator('[data-action="run-quote"]').click();await page.locator('#quote-result .quote-detail').waitFor();
 const quoteText=await page.locator('#quote-result').innerText();
 if(!quoteText.includes('133.04'))throw Error('Expected official 133.04 total missing');
 await page.locator('[data-edit-quote-line]').first().click();
 await page.locator('#edit-actor').fill('Browser QA');await page.locator('#edit-reason').fill('核对官方示例来源和交期');
 await page.locator('[data-action="save-line-edit"]').click();await page.locator('#drawer').waitFor({state:'hidden'});
 await page.locator('#review-actor').fill('Browser QA');await page.locator('#review-reason').fill('已核对官方样例单位件状与全部约束');
 await page.locator('#review-confirm').check();await page.locator('[data-action="approve-quote"]').click();
 await page.waitForFunction(()=>document.querySelector('#quote-result').textContent.includes('REVIEWED'));
 await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:'evidence/quote_review.png',fullPage:true});
 const download=page.waitForEvent('download');await page.locator('[data-export="xlsx"]').click();const d=await download;await d.saveAs('evidence/browser_quote.xlsx');
 for(const nav of ['inbox','insight','rules','history','audit','connect']){
  await page.locator(`[data-page="${nav}"]`).click();await page.waitForSelector('.page-head');
  if(nav==='inbox'){await page.locator('[data-line]').first().click();await page.locator('#drawer a[download]').first().waitFor();await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:'evidence/source_trace.png',fullPage:true});await page.locator('[data-action="close-drawer"]').click()}
 }
 await page.setViewportSize({width:390,height:844});await page.goto((process.env.QUOTEPILOT_URL||'http://127.0.0.1:8765'));if(process.env.QA_FONT_CSS){await page.addStyleTag({content:fs.readFileSync(process.env.QA_FONT_CSS,'utf8')});await page.evaluate(()=>document.fonts.ready)}await page.waitForSelector('.hero');
 if(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth+2))throw Error('Mobile horizontal overflow');
 await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:'evidence/mobile.png',fullPage:true});
 await browser.close();
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync('evidence/browser_result.json',JSON.stringify({passed:true,checks:['desktop navigation','official quote 133.04','manual review','approval','xlsx download','source drawer','mobile no overflow'],page_errors:errors},null,2));
 console.log('Browser smoke passed');
})().catch(e=>{console.error(e);process.exit(1)});
