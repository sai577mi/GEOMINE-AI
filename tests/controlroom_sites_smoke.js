const { chromium } = require('playwright');
const fs=require('fs'),path=require('path'),http=require('http');
const ROOT=path.resolve(__dirname,'../geomine-ai');
const srv=http.createServer((q,r)=>{let f=path.join(ROOT,q.url.split('?')[0]);if(f.endsWith('/'))f+='index.html';fs.readFile(f,(e,d)=>{if(e){r.writeHead(404);r.end();return;}r.writeHead(200,{'content-type':f.endsWith('.js')?'text/javascript':'text/html'});r.end(d);});}).listen(8124);
(async()=>{
 const b=await chromium.launch();const p=await b.newPage({viewport:{width:1300,height:900}});
 const errs=[];p.on('pageerror',e=>errs.push(e.message));
 await p.route(/^https?:\/\/(?!localhost)/,route=>{const u=route.request().url();const J=o=>route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(o)});
  if(u.includes('geocoding'))return J({results:[{name:'Moanda',latitude:-1.57,longitude:13.2,country:'Gabon',admin1:'Haut-Ogooué'}]});
  if(u.includes('open-meteo')){const lat=+new URL(u).searchParams.get('latitude');return J({daily:{precipitation_sum:[0,0,5,lat<0?80:0,10,0,0,0,0]}});}
  return route.abort();});
 await p.goto('http://localhost:8124/web/index.html?lat=-1.57&lon=13.2&name=Moanda%20%3Cb%3E');
 await p.waitForTimeout(2500);
 console.log('options',await p.$$eval('#mineSel option',o=>o.map(x=>x.textContent)),'sel',await p.inputValue('#mineSel'));
 console.log('strip',(await p.textContent('#strip')).slice(0,100));
 await p.fill('#siteQ','Moan');await p.waitForSelector('#siteRes button');await p.click('#siteRes button');await p.waitForTimeout(1500);
 console.log('after add',await p.$$eval('#mineSel option',o=>o.length));
 await p.reload();await p.waitForTimeout(2000);console.log('persisted',await p.$$eval('#mineSel option',o=>o.length));
 await p.click('#tab-net');console.log('net rows',await p.$$eval('#netTable tbody tr',r=>r.length));
 await p.screenshot({path:'../earth/c1.png'});
 console.log('errors',errs);await b.close();srv.close();})();
