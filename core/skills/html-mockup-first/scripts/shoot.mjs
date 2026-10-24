import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
const b = await chromium.launch({executablePath:'/opt/pw-browsers/chromium'}).catch(async()=>chromium.launch());
const p = await b.newPage({viewport:{width:1160,height:1000}});
await p.goto('file://'+process.argv[2]);
await p.waitForTimeout(1500);
for (const id of process.argv.slice(3)) {
  const el = await p.$('#'+id); await el.screenshot({path:`/tmp/shot-${id}.png`});
}
await b.close();
