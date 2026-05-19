const fs = require('fs');
const html = fs.readFileSync('Z:/netops-ai/web/templates/index.html', 'utf8');
const m = html.match(/<script[^>]*>([\s\S]*?)<\/script>/);
const code = m[1];
const lines = code.split('\n');
let bc = 0;
for (let i = lines.length - 1; i >= 0; i--) {
  let lineBc = 0;
  for (const c of lines[i]) {
    if (c === '{') lineBc++;
    if (c === '}') lineBc--;
  }
  if (lineBc !== 0) {
    bc += lineBc;
    if (bc !== 0) {
      console.log((i + 1) + ': cumBc=' + bc + ' lineBc=' + lineBc + ' | ' + lines[i].substring(0, 120));
    }
    if (bc >= 1 && i < lines.length - 50) break;
  }
}
