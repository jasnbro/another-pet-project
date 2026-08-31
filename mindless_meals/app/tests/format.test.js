// Chip-list parsing/joining (Ingredients/Sauce) and Make's arrow
// normalization (product spec v1.1 §1-2).
// Run with: node --test mindless_meals/app/tests/format.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { parseChipList, joinChipList, normalizeMake } = require("../static/js/format.js");

test("parseChipList splits on the middle-dot separator and trims each entry", () => {
  assert.deepEqual(parseChipList("Salmon · Avocado · Cucumber"), ["Salmon", "Avocado", "Cucumber"]);
});

test("parseChipList keeps multiword entries intact", () => {
  assert.deepEqual(parseChipList("Purple cabbage · Turkey meatballs"), ["Purple cabbage", "Turkey meatballs"]);
});

test("parseChipList ignores blank entries from stray separators", () => {
  assert.deepEqual(parseChipList("Salmon ·  · Rice ·"), ["Salmon", "Rice"]);
});

test("parseChipList strips trailing punctuation", () => {
  assert.deepEqual(parseChipList("Salmon, · Rice."), ["Salmon", "Rice"]);
});

test("parseChipList dedupes case-insensitively, keeping the first casing seen", () => {
  assert.deepEqual(parseChipList("Rice · rice · RICE · Beans"), ["Rice", "Beans"]);
});

test("parseChipList collapses internal whitespace", () => {
  assert.deepEqual(parseChipList("Purple   cabbage"), ["Purple cabbage"]);
});

test("joinChipList reproduces the compact separator style", () => {
  assert.equal(
    joinChipList(["Salmon", "Avocado", "Cucumber", "Rice", "Purple cabbage"]),
    "Salmon · Avocado · Cucumber · Rice · Purple cabbage"
  );
});

test("parseChipList/joinChipList round-trip existing stored data unchanged", () => {
  const stored = "Ground turkey · broccoli · edamame · rice";
  assert.equal(joinChipList(parseChipList(stored)), stored);
});

test("normalizeMake joins arrow/comma/semicolon/newline-separated actions with →", () => {
  assert.equal(
    normalizeMake("Roast sweet potatoes, brown turkey; assemble bowls"),
    "Roast sweet potatoes → Brown turkey → Assemble bowls"
  );
  assert.equal(
    normalizeMake("Bake meatballs\nSimmer in gravy"),
    "Bake meatballs → Simmer in gravy"
  );
});

test("normalizeMake normalizes an ASCII arrow to the real arrow", () => {
  assert.equal(normalizeMake("Cook salmon -> dice vegetables -> assemble"), "Cook salmon → Dice vegetables → Assemble");
});

test("normalizeMake is idempotent on already-formatted text", () => {
  const formatted = "Sauté cabbage → Add sauce → Serve over rice";
  assert.equal(normalizeMake(formatted), formatted);
});

test("normalizeMake trims whitespace and drops empty actions", () => {
  assert.equal(normalizeMake("  Cook salmon ,, , dice vegetables  "), "Cook salmon → Dice vegetables");
});

test("normalizeMake capitalizes only the first character, preserving the rest", () => {
  assert.equal(normalizeMake("roast SWEET potatoes"), "Roast SWEET potatoes");
});

test("normalizeMake on empty input returns an empty string", () => {
  assert.equal(normalizeMake(""), "");
  assert.equal(normalizeMake("   "), "");
});
