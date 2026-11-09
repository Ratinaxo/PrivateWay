/* Offline contract smoke tests. No network or secrets. Run: pnpm test:contracts */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

process.env.NODE_ENV = 'development';
process.env.PRIVATEWAY_DEV_CATALOG = '1';
process.env.GATEWAY_INTERNAL_URL = 'http://backend:8000';
process.env.GATEWAY_CLIENT_TOKEN = 'token-ficticio-de-prueba';

function importTs(file, dependencies) {
  const source = fs.readFileSync(file, 'utf8');
  const {outputText} = ts.transpileModule(source, {
    fileName: file,
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  });
  const mod = {exports: {}};
  new Function('require', 'module', 'exports', outputText)(
    (name) => {
      if (!(name in dependencies)) throw new Error('Dependencia inesperada: ' + name);
      return dependencies[name];
    }, mod, mod.exports,
  );
  return mod.exports;
}

const server = importTs(path.join(__dirname, '../src/lib/gateway/server.ts'), {});
const route = importTs(path.join(__dirname, '../src/app/api/privateway/models/route.ts'), {
  'next/server': {
    NextResponse: {
      json: (body, options = {}) => ({status: options.status ?? 200, body}),
    },
  },
  '@/lib/gateway/server': server,
});

async function check() {
  const data = {providers: [{id: 'simulado', label: 'Simulado', models: [{id: 'pw-simulado', label: 'pw-simulado'}]}]};
  global.fetch = async (url, opts) => {
    assert.equal(String(url), 'http://backend:8000/api/v1/models');
    assert.equal(opts.method, 'GET');
    assert.equal(opts.headers.Authorization, 'Bearer token-ficticio-de-prueba');
    return {ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => data};
  };
  let result = await route.GET();
  assert.equal(result.status, 200);
  assert.deepEqual(result.body, data);

  process.env.PRIVATEWAY_DEV_CATALOG = '0';
  result = await route.GET();
  assert.equal(result.status, 503);
  assert.equal(result.body.error.code, 'AUTENTICACION_PENDIENTE');
  process.env.PRIVATEWAY_DEV_CATALOG = '1';

  global.fetch = async () => {throw new Error('INTERNAL KEY SECRET');};
  result = await route.GET();
  assert.equal(result.status, 502);
  assert.equal(result.body.error.code, 'GATEWAY_INACCESIBLE');
  assert.ok(!JSON.stringify(result.body).includes('INTERNAL KEY SECRET'));

  global.fetch = async () => ({ok: true, status: 200, headers: {get: () => 'application/json'}, json: async () => ({providers: 'malformed'})});
  result = await route.GET();
  assert.equal(result.status, 502);
  assert.equal(result.body.error.code, 'GATEWAY_RESPUESTA_INVALIDA');

  console.log('BFF catalog contract: 4 offline tests passed');
}

check().catch((err) => { console.error(err); process.exitCode = 1; });
