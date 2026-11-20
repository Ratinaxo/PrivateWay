/* Contrato del catálogo: requiere sesión y consulta el backend. Sin red ni secretos reales. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

process.env.GATEWAY_INTERNAL_URL = 'http://backend:8000';
process.env.GATEWAY_CLIENT_TOKEN = 'token-ficticio-de-prueba';

function importTs(file, dependencies) {
  const source = fs.readFileSync(file, 'utf8');
  const {outputText} = ts.transpileModule(source, {
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

let authConfigured = true;
let authenticated = true;
let gatewayCalls = 0;
const server = importTs(path.join(__dirname, '../src/lib/gateway/server.ts'), {});
const route = importTs(path.join(__dirname, '../src/app/api/privateway/models/route.ts'), {
  'next/server': {
    NextResponse: {json: (body, options = {}) => ({status: options.status ?? 200, body})},
  },
  '@/lib/auth/config': {isAuthConfigured: () => authConfigured},
  '@/lib/auth/session': {currentSession: async () => authenticated ? {user: {id: 'usuario-de-prueba'}} : null},
  '@/lib/gateway/server': server,
});

async function check() {
  const data = {providers: [{id: 'simulado', label: 'Simulado', models: [{id: 'pw-simulado', label: 'pw-simulado'}]}]};
  global.fetch = async (url, opts) => {
    gatewayCalls++;
    assert.equal(String(url), 'http://backend:8000/api/v1/models');
    assert.equal(opts.method, 'GET');
    assert.equal(opts.headers.Authorization, 'Bearer token-ficticio-de-prueba');
    return {ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => data};
  };

  // Una configuración OIDC incompleta nunca consulta el gateway.
  authConfigured = false;
  let result = await route.GET();
  assert.equal(result.status, 503);
  assert.equal(result.body.error.code, 'AUTENTICACION_NO_CONFIGURADA');
  assert.equal(gatewayCalls, 0);

  // Un visitante sin sesión tampoco puede consultar el catálogo.
  authConfigured = true;
  authenticated = false;
  result = await route.GET();
  assert.equal(result.status, 401);
  assert.equal(result.body.error.code, 'NO_AUTENTICADO');
  assert.equal(gatewayCalls, 0);

  // Con sesión válida, el catálogo llega del gateway, no de un catálogo ficticio.
  authenticated = true;
  result = await route.GET();
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, data);
  assert.equal(gatewayCalls, 1);

  // Nunca se devuelve el error crudo del transporte al navegador.
  global.fetch = async () => {throw new Error('INTERNAL KEY SECRET');};
  result = await route.GET();
  assert.equal(result.status, 502);
  assert.equal(result.body.error.code, 'GATEWAY_INACCESIBLE');
  assert.ok(!JSON.stringify(result.body).includes('INTERNAL KEY SECRET'));

  // Se rechaza un catálogo JSON con contrato inválido.
  global.fetch = async () => ({ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => ({providers: 'malformed'})});
  result = await route.GET();
  assert.equal(result.status, 502);
  assert.equal(result.body.error.code, 'GATEWAY_RESPUESTA_INVALIDA');

  console.log('BFF catalog contract: 5 offline tests passed');
}

check().catch((err) => {console.error(err); process.exitCode = 1;});
