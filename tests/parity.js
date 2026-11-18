// Checks that the browser models give the same answers as Python.   Run:  node tests/parity.js
const fs = require("fs"), path = require("path");
const root = path.resolve(__dirname, "..");
const models = JSON.parse(fs.readFileSync(path.join(root, "tools/src/models.json")));
const ref = JSON.parse(fs.readFileSync(path.join(__dirname, "ref.json")));
eval(fs.readFileSync(path.join(root, "tools/src/core.js"), "utf8") + ";globalThis.makeCore = makeCore;");
const C = makeCore(models);
let e1 = 0, e2 = 0;
ref.clf_rows.forEach((x, i) => (e1 = Math.max(e1, Math.abs(C.predictClf(x) - ref.clf_prob[i]))));
ref.sim_rows.forEach((x, i) => (e2 = Math.max(e2, Math.abs(C.predictAch(Object.fromEntries(C.SIM_F.map((k, j) => [k, x[j]]))) - ref.sim_pred[i]))));
console.log("classifier max diff:", e1.toExponential(2), "| simulator max diff:", e2.toExponential(2));
if (e1 > 1e-4 || e2 > 1e-2) { console.error("PARITY FAILED"); process.exit(1); }
console.log("PARITY OK");
