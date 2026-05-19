const fs = require('fs');
const html = fs.readFileSync('Z:/netops-ai/web/templates/index.html', 'utf8');
const m = html.match(/<script[^>]*>([\s\S]*?)<\/script>/);
const code = m[1];
const lines = code.split('\n');
let bc = 0, pc = 0;
for (let i = 0; i < lines.length; i++) {
  const prevPc = pc;
  for (const c of lines[i]) {
    if (c === '{') bc++;
    if (c === '}') bc--;
    if (c === '(') pc++;
    if (c === ')') pc--;
  }
  if (pc !== prevPc && i < 600) {
    console.log((i + 1) + ': bc=' + bc + ' pc=' + pc + ' | ' + lines[i].substring(0, 120));
  }
}
