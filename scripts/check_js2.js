const fs = require('fs');
const html = fs.readFileSync('Z:/netops-ai/web/templates/index.html','utf8');
const scriptMatch = html.match(/<script[^>]*>([\s\S]*?)<\/script>/g);
if (!scriptMatch) { console.log('No scripts'); process.exit(0); }
const code = scriptMatch[0].replace(/<\/?script[^>]*>/g, '');
try { 
  new Function(code); 
  console.log('OK'); 
} catch(e) {
  const lines = code.split('\n');
  // Try to find approximate location from error
  console.log('Error:', e.message);
  // Search for common issues
  let braceCount = 0;
  let parenCount = 0;
  for (let i = 0; i < lines.length; i++) {
    for (const ch of lines[i]) {
      if (ch === '{') braceCount++;
      if (ch === '}') braceCount--;
      if (ch === '(') parenCount++;
      if (ch === ')') parenCount--;
    }
    if (i > 0 && i % 200 === 0) {
      console.log('Line ' + (i+1) + ': braces=' + braceCount + ' parens=' + parenCount);
    }
  }
  console.log('Final: braces=' + braceCount + ' parens=' + parenCount);
}
