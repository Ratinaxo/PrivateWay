/* Comprobaciones de seguridad estructurales y sintaxis sin red. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.join(__dirname, '..');
function read(file) {return fs.readFileSync(path.join(root, file), 'utf8');}
const config = read('src/lib/auth/config.ts');
const session = read('src/lib/auth/session.ts');
const home = read('src/app/page.tsx');
const perfil = read('src/app/perfil/page.tsx');
const settings = read('src/app/configuracion/page.tsx');
const signin = read('src/app/login/page.tsx');
const chat = read('src/app/api/privateway/chat/route.ts');
const models = read('src/app/api/privateway/models/route.ts');
assert.match(config, /checks:\s*\["pkce", "state", "nonce"\]/);
assert.match(config, /session:\s*\{\s*strategy:\s*"jwt"/);
assert.match(config, /process\.env\.NEXTAUTH_SECRET/);
assert.match(session, /if \(!isAuthConfigured\(\)\) return null/);
for (const text of [home, perfil, settings]) assert.match(text, /await requireSession\(\)/);
for (const text of [chat, models]) {
  assert.match(text, /await currentSession\(\)/);
  assert.match(text, /NO_AUTENTICADO/);
  assert.doesNotMatch(text, /PRIVATEWAY_DEV_(?:CATALOG|CHAT_BRIDGE)/);
}
assert.match(signin, /isAuthConfigured/);
assert.ok(!fs.existsSync(path.join(root, 'src/lib/chat-demo.ts')), 'no mantener datos de demostración');
const src = path.join(root, 'src');
let checked = 0;
function walk(dir) {
  for (const item of fs.readdirSync(dir, {withFileTypes:true})) {
    const file = path.join(dir, item.name);
    if (item.isDirectory()) walk(file);
    else if (/\.tsx?$/.test(item.name) && !item.name.endsWith('.d.ts')) {
      const source = fs.readFileSync(file, 'utf8');
      const {diagnostics = []} = ts.transpileModule(source, {
        fileName: file,
        reportDiagnostics: true,
        compilerOptions: {
          jsx: ts.JsxEmit.ReactJSX,
          module: ts.ModuleKind.ESNext,
          target: ts.ScriptTarget.ES2022,
        },
      });
      const syntax = diagnostics.filter(d => d.category === ts.DiagnosticCategory.Error);
      assert.equal(syntax.length, 0, file + '\n' + syntax.map(d => ts.flattenDiagnosticMessageText(d.messageText, '\n')).join('\n'));
      checked++;
    }
  }
}
walk(src);
console.log(`Auth contract: rutas protegidas y sintaxis de ${checked} archivos comprobadas`);
