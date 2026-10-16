// Pure UI lifecycle test, not a browser emulator or a domain workflow executor.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const markup = fs.readFileSync(path.join(__dirname, "../../app/onboarding.html"), "utf8");
const script = markup.match(/<script>([\s\S]*?)<\/script>/)[1];

class Control {
  constructor(document) {
    this.document = document;
    this.listeners = {};
    this.isConnected = true;
  }
  addEventListener(name, callback) { this.listeners[name] = callback; }
  focus() { this.document.activeElement = this; }
  click() { if (!this.disabled) this.listeners.click(); }
}
function freshDocument() {
  const document = {};
  document.activeElement = new Control(document);
  document.getElementById = id => id === "tr-onboarding" ? document.dialog : null;
  return document;
}
function mount(document) {
  const dialog = new Control(document);
  dialog.dataset = {};
  dialog.controls = {};
  dialog.querySelector = selector => dialog.controls[selector] ??= new Control(document);
  dialog.querySelectorAll = () => [
    dialog.querySelector("[data-guide-close]"),
    dialog.querySelector("[data-guide-previous]"),
    dialog.querySelector("[data-guide-next]"),
  ];
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; };
  document.dialog = dialog;
  vm.runInNewContext(script, { document, Symbol });
  return dialog;
}
const document = freshDocument();
const originalFocus = document.activeElement;
let dialog = mount(document);
const control = name => dialog.querySelector(`[data-guide-${name}]`);
assert.equal(dialog.open, true);
assert.equal(control("progress").textContent, "第 1 步，共 5 步");
assert.equal(control("previous").disabled, true);
assert.equal(document.activeElement, control("close"));
dialog.listeners.keydown({ key: "Tab", shiftKey: true, preventDefault() {} });
assert.equal(document.activeElement, control("next"));
dialog.listeners.keydown({ key: "Tab", shiftKey: false, preventDefault() {} });
assert.equal(document.activeElement, control("close"));
control("next").click();
assert.equal(control("heading").textContent, "确认核验范围");
assert.equal(document.activeElement, control("step"));
dialog = mount(document); // Backend rerun replaces markup, but not document state.
assert.equal(control("progress").textContent, "第 2 步，共 5 步");
control("previous").click();
assert.equal(control("progress").textContent, "第 1 步，共 5 步");
let prevented = false;
dialog.listeners.cancel({ preventDefault() { prevented = true; } });
assert.equal(prevented, true);
assert.equal(dialog.open, false);
assert.equal(document.activeElement, originalFocus);
dialog = mount(document);
assert.notEqual(dialog.open, true); // Escape dismissal survives rerun.
const refreshedDocument = freshDocument();
dialog = mount(refreshedDocument); // Full webpage refresh creates a new document.
assert.equal(dialog.open, true);
assert.equal(control("progress").textContent, "第 1 步，共 5 步");
for (let i = 0; i < 4; i += 1) control("next").click();
assert.equal(control("next").textContent, "完成引导");
control("next").click();
assert.equal(dialog.open, false);
dialog = mount(refreshedDocument);
assert.notEqual(dialog.open, true); // Completion also survives rerun.
dialog = mount(freshDocument());
control("close").click();
assert.equal(dialog.open, false);
console.log("onboarding lifecycle: PASS");
