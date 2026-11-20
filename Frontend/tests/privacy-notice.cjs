/* Regresión: la alerta solo corresponde al último mensaje del usuario. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const file = path.join(__dirname, '../src/lib/privacy-notice.ts');
const {outputText} = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  fileName: file,
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
});
const mod = {exports: {}};
new Function('module','exports',outputText)(mod,mod.exports);
const {shouldNotifyCurrentMessage} = mod.exports;
assert.equal(shouldNotifyCurrentMessage({accion:'permitir', mensaje_actual_seudonimizado:false, historial_seudonimizado:false}), false);
assert.equal(shouldNotifyCurrentMessage({accion:'seudonimizar', mensaje_actual_seudonimizado:true, historial_seudonimizado:false}), true);
assert.equal(shouldNotifyCurrentMessage({accion:'seudonimizar', mensaje_actual_seudonimizado:false, historial_seudonimizado:true}), false);
assert.equal(shouldNotifyCurrentMessage(null), false);
assert.equal(shouldNotifyCurrentMessage({accion:'seudonimizar'}), false);
console.log('Privacy notice regression: 5 casos superados');
