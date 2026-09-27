// Browser regression test: requires Playwright and an installed Brave browser.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
(async()=>{
 const root=process.argv[2]||__dirname;
 const browser=await chromium.launch({executablePath:'C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe',headless:true});
 try {
  const page=await browser.newPage({viewport:{width:1280,height:720}});
  await page.setContent(`<style>body{background:#222}video{width:400px;height:220px;background:#444}#container{background:#333}button{padding:10px}</style><button id="videoFull">Video fullscreen</button><button id="containerFull">Container fullscreen</button><div id="container"><video id="video" muted></video></div><iframe id="embedded" allowfullscreen srcdoc='<video id="inside" muted style="width:300px;height:160px" onclick="this.requestFullscreen()"></video>'></iframe>`);
  const embedded=await (await page.$('#embedded')).contentFrame();
  async function inject(frame){
   await frame.evaluate(async()=>{
    window.chrome={runtime:{onMessage:{addListener(fn){window.testMessage=fn;}}},storage:{local:{get(k,fn){fn({});}}}};
    const canvas=document.createElement('canvas'); canvas.width=640;canvas.height=360;
    const ctx=canvas.getContext('2d');ctx.fillStyle='#304050';ctx.fillRect(0,0,640,360);
    const video=document.querySelector('video');video.srcObject=canvas.captureStream(5);await video.play();
    window.testCanvas=canvas;window.paintTimer=setInterval(()=>ctx.fillRect(0,0,640,360),200);
   });
   await frame.addStyleTag({path:path.join(root,'content.css')});
   await frame.addScriptTag({path:path.join(root,'content.js')});
  }
  await inject(page);await inject(embedded);
  await page.evaluate(()=>{
   document.querySelector('#videoFull').onclick=()=>document.querySelector('#video').requestFullscreen();
   document.querySelector('#containerFull').onclick=()=>document.querySelector('#container').requestFullscreen();
  });
  const caption='English subtitles above the fullscreen video.';
  async function send(frame,type,extra={}){await frame.evaluate(({type,extra})=>testMessage({type,...extra},null,()=>{}),{type,extra});}
  async function broadcast(type,extra={}){await send(page,type,extra);await send(embedded,type,extra);}
  await broadcast('overlay:mount',{settings:{targetLang:'en'}});
  await broadcast('overlay:text',{text:caption});
  assert.equal(await embedded.locator('#kami-subs-overlay').count(),0);
  async function nativeShown(frame){
   await frame.waitForFunction(()=>Array.from(document.querySelector('video').textTracks).some(t=>t.label==='Kami Subs'&&t.mode==='showing'&&t.activeCues?.length===1));
   const txt=await frame.evaluate(()=>Array.from(document.querySelector('video').textTracks).find(t=>t.label==='Kami Subs').activeCues[0].text);
   assert.equal(txt,caption);
  }
  async function overlayOnTop(){
   await page.waitForFunction(()=>document.querySelector('#kami-subs-overlay').matches(':popover-open'));
   const state=await page.evaluate(()=>{
    const el=document.querySelector('#kami-subs-overlay'),r=el.getBoundingClientRect();el.style.pointerEvents='auto';
    const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);el.style.pointerEvents='';
    return {top:hit===el||el.contains(hit),fits:r.width>0&&r.y>=0&&r.bottom<=innerHeight,dir:getComputedStyle(el).direction};
   });assert.equal(state.top,true,JSON.stringify(state));assert.equal(state.fits,true);assert.equal(state.dir,'ltr');
  }
  await page.click('#videoFull');await nativeShown(page);
  await page.evaluate(()=>document.exitFullscreen());await page.waitForFunction(()=>!document.fullscreenElement);
  assert.equal(await page.evaluate(()=>Array.from(document.querySelector('video').textTracks).find(t=>t.label==='Kami Subs').mode),'disabled');
  console.log('PASS native video fullscreen: active native subtitle, cleanup on exit');
  await broadcast('overlay:text',{text:caption});
  await page.click('#containerFull');await overlayOnTop();
  await page.evaluate(()=>document.exitFullscreen());await page.waitForFunction(()=>!document.fullscreenElement);
  console.log('PASS container fullscreen: DOM overlay in front, position, direction, exit');
  await broadcast('overlay:text',{text:caption});
  await embedded.click('#inside');await nativeShown(embedded);
  assert.equal(await page.locator('#kami-subs-overlay').evaluate(el=>getComputedStyle(el).visibility),'hidden');
  await broadcast('overlay:unmount');
  assert.equal(await embedded.evaluate(()=>Array.from(document.querySelector('video').textTracks).find(t=>t.label==='Kami Subs').mode),'disabled');
  assert.equal(await page.locator('#kami-subs-overlay').count(),0);
  console.log('PASS embedded video fullscreen: native subtitles in iframe, no duplicate main overlay, unmount');
  await broadcast('overlay:mount',{settings:{position:'top'}});await broadcast('overlay:text',{text:caption});await nativeShown(embedded);
  assert.equal(await embedded.evaluate(()=>Array.from(document.querySelector('video').textTracks).find(t=>t.label==='Kami Subs').activeCues[0].line),1);
  assert.equal(await embedded.evaluate(()=>Array.from(document.querySelector('video').textTracks).filter(t=>t.label==='Kami Subs').length),1);
  await page.evaluate(()=>document.exitFullscreen());await page.waitForFunction(()=>!document.fullscreenElement);
  await page.waitForFunction(()=>getComputedStyle(document.querySelector('#kami-subs-overlay')).visibility==='visible');
  console.log('PASS remount while fullscreen, top cue, track reuse, normal overlay restored');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
