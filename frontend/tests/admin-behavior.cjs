/** Pruebas de comportamiento de la lógica de administración SIN contactar Keycloak. */
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/lib/keycloak/admin.ts'), 'utf8')
const code = ts.transpileModule(source, { compilerOptions: {
  module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
}}).outputText

const one = '11111111-1111-4111-8111-111111111111'
const two = '22222222-2222-4222-8222-222222222222'
const three = '33333333-3333-4333-8333-333333333333'
const five = '55555555-5555-4555-8555-555555555555'
const six = '66666666-6666-4666-8666-666666666666'
const users = new Map([
  [one, { id: one, username: 'adminuno', enabled: true }],
  [two, { id: two, username: 'usuario', enabled: true }],
  [three, { id: three, username: 'adminotro', enabled: false }],
  [five, { id: five, username: 'sinrol', enabled: true }],
  [six, { id: six, username: 'service-account-privateway-admin-api', enabled: true }],
])
const userRoles = new Map([[one, new Set(['privateway-user', 'privateway-admin'])], [two, new Set(['privateway-user'])], [three, new Set(['privateway-admin'])], [five, new Set()], [six, new Set()]])
const calls = []
const tokenPath = '/realms/privateway/protocol/openid-connect/token'
const adminPrefix = '/admin/realms/privateway'
const response = (status, value, headers = {}) => ({
  ok: status >= 200 && status < 300, status,
  headers: { get: (key) => headers[key.toLowerCase()] || null },
  json: async () => value,
})
async function mockFetch(input, opts = {}) {
  const url = new URL(input)
  assert.equal(url.origin, 'http://keycloak:8081')
  calls.push({ path: url.pathname, method: opts.method || 'GET', body: opts.body ? String(opts.body) : null })
  if (url.pathname === tokenPath) {
    assert.match(String(opts.body), /grant_type=client_credentials/)
    return response(200, { access_token: 'fake-local-token' })
  }
  assert.match(opts.headers.Authorization, /^Bearer fake-local-token$/)
  const suffix = url.pathname.slice(adminPrefix.length)
  if (suffix === '/roles/privateway-admin/users') {
    return response(200, [...users.values()].filter((user) => userRoles.get(user.id)?.has('privateway-admin')))
  }
  if (suffix === '/roles/privateway-user') return response(200, { id: 'role-user', name: 'privateway-user' })
  if (suffix === '/roles/privateway-admin') return response(200, { id: 'role-admin', name: 'privateway-admin' })
  if (suffix === '/users' && opts.method === 'POST') {
    const body = JSON.parse(opts.body)
    assert.equal(body.enabled, false, 'la cuenta debe crearse deshabilitada')
    assert.equal(body.credentials[0].temporary, true)
    users.set('44444444-4444-4444-8444-444444444444', { id: '44444444-4444-4444-8444-444444444444', username: body.username, enabled: false })
    userRoles.set('44444444-4444-4444-8444-444444444444', new Set())
    return response(201, {}, { location: 'http://keycloak:8081/admin/realms/privateway/users/44444444-4444-4444-8444-444444444444' })
  }
  if (suffix === '/users' && (!opts.method || opts.method === 'GET')) return response(200, [...users.values()])
  const userMatch = suffix.match(/^\/users\/([a-f\d-]{36})(\/role-mappings\/realm|\/reset-password)?$/)
  if (userMatch) {
    const [, id, subroute] = userMatch
    const user = users.get(id)
    if (!user) return response(404, {})
    if (!opts.method || opts.method === 'GET') {
      if (subroute === '/role-mappings/realm') return response(200, [...userRoles.get(id)].map((name) => ({ id: name, name })))
      return response(200, user)
    }
    if (subroute === '/role-mappings/realm') {
      const role = JSON.parse(opts.body)[0].name
      if (opts.method === 'POST') userRoles.get(id).add(role)
      else if (opts.method === 'DELETE') userRoles.get(id).delete(role)
      return response(204, {})
    }
    if (subroute === '/reset-password') {
      assert.equal(JSON.parse(opts.body).temporary, true)
      return response(204, {})
    }
    if (!subroute && opts.method === 'PUT') {
      user.enabled = JSON.parse(opts.body).enabled
      return response(204, {})
    }
  }
  throw new Error(`Solicitud de prueba no prevista: ${opts.method || 'GET'} ${suffix}`)
}

const exportsObject = {}
vm.runInNewContext(code, {
  exports: exportsObject,
  require: (id) => { if (id === 'server-only') return {}; throw new Error(`Import no previsto: ${id}`) },
  process: { env: {
    PRIVATEWAY_KEYCLOAK_INTERNAL_URL: 'http://keycloak:8081',
    PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_ID: 'privateway-admin-api',
    PRIVATEWAY_KEYCLOAK_ADMIN_CLIENT_SECRET: 'fake-secret',
  } },
  URL, URLSearchParams, AbortSignal, fetch: mockFetch,
})
const api = exportsObject

async function rejectsCode(work, code) {
  await assert.rejects(work, (error) => error && error.code === code, code)
}
async function main() {
  assert.deepEqual(JSON.parse(JSON.stringify(await api.readAccountPrivileges(one))), { enabled: true, isAdmin: true })
  assert.deepEqual(JSON.parse(JSON.stringify(await api.readAccountPrivileges(two))), { enabled: true, isAdmin: false })
  assert.deepEqual(JSON.parse(JSON.stringify(await api.readAccountPrivileges(three))), { enabled: false, isAdmin: false })
  assert.deepEqual(JSON.parse(JSON.stringify(await api.readAccountPrivileges(five))), { enabled: false, isAdmin: false }, 'usuario sin rol no puede acceder')

  await rejectsCode(() => api.updateManagedUser(one, 'set-enabled', false, one), 'NO_PUEDE_DESHABILITARSE')
  await rejectsCode(() => api.updateManagedUser(one, 'set-admin', false, one), 'NO_PUEDE_RETIRARSE_ADMIN')
  await rejectsCode(() => api.updateManagedUser(one, 'set-admin', false, two), 'ULTIMO_ADMINISTRADOR')
  await rejectsCode(() => api.updateManagedUser(three, 'set-admin', true, one), 'USUARIO_DESHABILITADO')
  await rejectsCode(() => api.updateManagedUser(two, 'reset-password', 'corta', one), 'DATOS_INVALIDOS')
  await rejectsCode(() => api.updateManagedUser(six, 'set-enabled', false, one), 'CUENTA_DE_SERVICIO_PROTEGIDA')

  await api.createManagedUser({ username: 'nueva', firstName: 'Nueva', lastName: 'Cuenta', email: 'nueva@example.test', password: 'ClaveTemporal-Segura-1234' })
  const created = users.get('44444444-4444-4444-8444-444444444444')
  assert.equal(created.enabled, true)
  assert.ok(userRoles.get(created.id).has('privateway-user'))
  assert.equal(calls.filter((event) => event.method === 'POST' && event.path.endsWith('/users')).length, 1)

  await api.updateManagedUser(two, 'set-admin', true, one)
  assert.ok(userRoles.get(two).has('privateway-admin'))
  await api.updateManagedUser(two, 'reset-password', 'ClaveTemporal-Distinta-5678', one)
  await api.updateManagedUser(one, 'set-admin', false, two)
  assert.ok(!userRoles.get(one).has('privateway-admin'))
  await api.updateManagedUser(one, 'set-enabled', false, two)
  assert.equal(users.get(one).enabled, false)

  const listed = await api.listManagedUsers()
  assert.ok(!listed.some((entry) => entry.id === six), 'ocultar cuentas de servicio')
  assert.ok(listed.some((entry) => entry.id === two && entry.isAdmin))
  assert.ok(listed.some((entry) => entry.id === one && !entry.enabled))
  console.log('Admin behavior: autenticación de servicio, roles, alta fail-closed, protección del último admin y reset temporal: correcto')
}
main().catch((error) => { console.error(error); process.exitCode = 1 })
