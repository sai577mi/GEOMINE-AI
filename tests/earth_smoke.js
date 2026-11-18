const { chromium } = require('playwright');
const fs=require('fs'), path=require('path'), http=require('http');
const ROOT=path.resolve(__dirname,'../geomine-ai');
const png=fs.readFileSync('/tmp/t.png');
const srv=http.createServer((q,r)=>{let f=path.join(ROOT,q.url.split('?')[0]);if(f.endsWith('/'))f+='index.html';
 fs.readFile(f,(e,d)=>{if(e){r.writeHead(404);r.end();return;}const t=f.endsWith('.js')?'text/javascript':f.endsWith('.css')?'text/css':'text/html';r.writeHead(200,{'content-type':t});r.end(d);});}).listen(8123);
(async()=>{
 const b=await chromium.launch({args:['--use-gl=swiftshader','--enable-webgl','--ignore-gpu-blocklist','--use-angle=swiftshader']});
 const p=await b.newPage({viewport:{width:1400,height:850}});
 const errs=[];p.on('pageerror',e=>errs.push('PAGEERR '+e.message));p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
 const days=[...Array(10)].map((_,i)=>new Date(Date.now()+(i-2)*864e5).toISOString().slice(0,10));
 await p.route(/^https?:\/\/(?!localhost)/,route=>{const u=route.request().url();
  const J=(o)=>route.fulfill({status:200,contentType:'application/json',headers:{'access-control-allow-origin':'*'},body:JSON.stringify(o)});
  if(u.includes('earthquake.usgs'))return J({features:[{geometry:{type:'Point',coordinates:[79,21]},properties:{mag:5.2,place:'Test quake',time:Date.now()}},{geometry:{type:'Point',coordinates:[140,36]},properties:{mag:3.1,place:'Japan',time:Date.now()}}]});
  if(u.includes('eonet'))return J({events:[{title:'Wildfire X',categories:[{id:'wildfires',title:'Wildfires'}],geometry:[{type:'Point',date:'2026-11-17T00:00:00Z',coordinates:[-120,38]}]}]});
  if(u.includes('rainviewer.com/public'))return J({host:'https://tilecache.rainviewer.com',radar:{past:[{time:1,path:'/v2/radar/1'},{time:2,path:'/v2/radar/2'}]}});
  if(u.includes('geocoding'))return J({results:[{name:'Nagpur',latitude:21.15,longitude:79.09,country:'India',admin1:'Maharashtra'}]});
  if(u.includes('api.open-meteo'))return J({current:{temperature_2m:31,weather_code:3,wind_speed_10m:12,relative_humidity_2m:55},daily:{time:days,weather_code:days.map((_,i)=>i%3?61:0),temperature_2m_max:days.map(()=>33),temperature_2m_min:days.map(()=>22),precipitation_sum:[0,2,5,30,60,8,0,0,45,3],wind_speed_10m_max:days.map(()=>20)}});
  if(u.includes('nominatim'))return J({name:'Testville'});
  return route.fulfill({status:200,contentType:'image/png',headers:{'access-control-allow-origin':'*'},body:png});});
 await p.goto('http://localhost:8123/web/earth.html');
 await p.waitForFunction(()=>window.__map&&window.__map.loaded(),null,{timeout:30000}).catch(()=>{});
 await p.waitForTimeout(2500);
 await p.screenshot({path:'../earth/s1.png'});
 // search
 await p.fill('#q','Nagp');await p.waitForSelector('#res button:not([disabled])');await p.click('#res button');
 await p.waitForSelector('#right .risk',{timeout:8000});await p.waitForTimeout(3500);
 await p.screenshot({path:'../earth/s2.png'});
 console.log('risk bars',await p.$$eval('#right .risk div',e=>e.map(x=>x.firstChild.textContent+':'+x.className)));
 // toggles
 await p.click('[data-l=radar]');await p.click('[data-l=fires]');await p.click('#dPrev');
 await p.check('#terrain');await p.waitForTimeout(2500);
 console.log('terrain',await p.evaluate(()=>!!window.__map.getTerrain()), 'date',await p.inputValue('#date'));
 await p.screenshot({path:'../earth/s3.png'});
 // click select on map
 await p.mouse.click(300,400);await p.waitForTimeout(1500);
 console.log('panel',await p.textContent('#right').then(t=>t.slice(0,90)));
 // mobile
 await p.setViewportSize({width:390,height:800});await p.waitForTimeout(800);await p.screenshot({path:'../earth/s4.png'});
 console.log('overflow',await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
 console.log('errors',errs.slice(0,8));
 await b.close();srv.close();
})();
