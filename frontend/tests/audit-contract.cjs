/* Auditoría administrativa: solo servidor, token separado y estructura validada. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.join(__dirname, '..');
const server = fs.readFileSync(path.join(root,'src/lib/gateway/audit.ts'), 'utf8');
const page = fs.readFileSync(path.join(root,'src/app/admin/auditoria/page.tsx'), 'utf8');
const profile = fs.readFileSync(path.join(root,'src/components/profile-menu.tsx'), 'utf8');
const admin = fs.readFileSync(path.join(root,'src/app/admin/page.tsx'), 'utf8');
assert.match(server, /import "server-only"/);
assert.match(page, /await requireAdminSession\(\)/);
assert.match(page, /getAuditSnapshot\(\)/);
assert.match(profile, /isAdmin && .*\/admin\/auditoria/);
assert.match(admin, /href="\/admin\/auditoria"/);
process.env.GATEWAY_INTERNAL_URL = 'http://backend:8000';
process.env.GATEWAY_AUDIT_READ_TOKEN = 'TOKEN-SOLO-AUDITORIA';
const {outputText} = ts.transpileModule(server, {
  fileName:'audit.ts', compilerOptions:{module:ts.ModuleKind.CommonJS, target:ts.ScriptTarget.ES2022},
});
const mod = {exports:{}};
new Function('require','module','exports',outputText)(
  (name) => {assert.equal(name,'server-only'); return {};}, mod,mod.exports,
);
let called = 0;
global.fetch = async (url, options) => {
  called++;
  assert.equal(String(url), 'http://backend:8000/api/v1/audit/events?limit=200');
  assert.equal(options.headers.Authorization, 'Bearer TOKEN-SOLO-AUDITORIA');
  assert.equal(options.cache,'no-store');
  return {ok:true,headers:{get:()=> 'application/json'}, json:async()=>({
    integridad:'verificada',total:1,registros:[{evento:'evt_' + 'a'.repeat(32),accion:'permitir',fase:'completada'}]
  })};
};
(async()=>{
  const result = await mod.exports.getAuditSnapshot();
  assert.equal(result.total,1);
  assert.equal(called,1);
  process.env.GATEWAY_AUDIT_READ_TOKEN = '';
  await assert.rejects(mod.exports.getAuditSnapshot(),/AUDITORIA_NO_CONFIGURADA/);
  assert.equal(called,1);
  console.log('Audit contract: acceso administrativo, secreto y validación correctos');
})().catch(err=>{console.error(err);process.exitCode=1;});
