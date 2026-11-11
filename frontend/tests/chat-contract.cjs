/* Contrato del endpoint de chat: requiere identidad antes de gateway. Sin red. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

function importTs(file, dependencies) {
  const source = fs.readFileSync(file, 'utf8');
  const { outputText } = ts.transpileModule(source, {
    fileName: file,
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true},
  });
  const mod = {exports: {}};
  new Function('require', 'module', 'exports', outputText)(name => {
    if (!(name in dependencies)) throw new Error('Dependencia inesperada: ' + name);
    return dependencies[name];
  }, mod, mod.exports);
  return mod.exports;
}

let configured = true;
let authenticated = true;
let oidcId = '00000000-0000-4000-8000-000000000001';
let calls = 0;
const response = {respuesta: {choices: [{message: {content: 'Respuesta sintética'}}]}, decision: {accion: 'permitir', codigo_motivo: 'TEST', evento: 'evt_00000000000000000000000000000000', mensaje_actual_seudonimizado: false, historial_seudonimizado: false}};
const route = importTs(path.join(__dirname, '../src/app/api/privateway/chat/route.ts'), {
  'next/server': {NextResponse: {json: (body, options = {}) => ({status: options.status ?? 200, body})}},
  '@/lib/auth/config': {isAuthConfigured: () => configured},
  '@/lib/auth/session': {currentSession: async () => authenticated ? {user: {id: oidcId}} : null},
  '@/lib/gateway/server': {
    GatewayBridgeError: class GatewayBridgeError extends Error {
      constructor(code, status) {super(code); this.code=code; this.status=status;}
    },
    sendProtectedChat: async () => {calls++; return response;},
  },
});
function request(body, headers = {}) {
  return new Request('http://localhost:3000/api/privateway/chat', {
    method: 'POST',
    headers: {'host': 'localhost:3000', 'content-type': 'application/json', ...headers},
    body: JSON.stringify(body),
  });
}
const valid = {model:'pw-simulado', messages:[{role:'user', content:'Prueba sintética'}], stream:false};
async function check() {
  configured = false;
  let result = await route.POST(request(valid));
  assert.equal(result.status, 503);
  assert.equal(result.body.error.code, 'AUTENTICACION_NO_CONFIGURADA');
  assert.equal(calls, 0);
  configured = true;

  authenticated = false;
  result = await route.POST(request(valid));
  assert.equal(result.status, 401);
  assert.equal(result.body.error.code, 'NO_AUTENTICADO');
  assert.equal(calls, 0);
  authenticated = true;

  oidcId = 'usuario-ficticio';
  result = await route.POST(request(valid));
  assert.equal(result.status, 403);
  assert.equal(result.body.error.code, 'IDENTIDAD_INVALIDA');
  assert.equal(calls, 0);
  oidcId = '00000000-0000-4000-8000-000000000001';

  result = await route.POST(request(valid, {origin:'https://evil.example'}));
  assert.equal(result.status, 403);
  assert.equal(calls, 0);

  result = await route.POST(request({...valid, messages: []}));
  assert.equal(result.status, 422);
  assert.equal(calls, 0);

  result = await route.POST(request({...valid, stream: true}));
  assert.equal(result.status, 422);
  assert.equal(calls, 0);

  result = await route.POST(request(valid, {origin: 'http://localhost:3000'}));
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, response);
  assert.equal(calls, 1);

  console.log('BFF chat contract: 7 pruebas superadas');
}
check().catch((err) => {console.error(err); process.exitCode = 1;});
