const fs = require('fs');
const html = fs.readFileSync('Z:/netops-ai/web/templates/index.html','utf8');
const scriptMatch = html.match(/<script[^>]*>([\s\S]*?)<\/script>/g);
if (!scriptMatch) { console.log('No scripts found'); process.exit(0); }
scriptMatch.forEach((block, i) => {
  const code = block.replace(/<\/?script[^>]*>/g, '');
  if (!code.trim()) return;
  try { new Function(code); console.log('Block', i+1, ': OK (' + code.length + ' chars)'); }
  catch(e) { console.log('Block', i+1, ': ERROR -', e.message); }
});
