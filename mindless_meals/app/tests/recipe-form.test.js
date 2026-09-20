// Add/Edit Recipe form helpers: ingredient/sauce chip parsing and Make
// arrow normalization (product spec: Mindless Meals v1.1 §1-2).
// Run with: node --test mindless_meals/app/tests/recipe-form.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { cleanChipToken, parseChips, chipsToStored, normalizeMethod } = require("../static/js/recipe-form.js");

test("cleanChipToken trims whitespace and trailing punctuation", () => {
  assert.equal(cleanChipToken("  cucumber  "), "cucumber");
  assert.equal(cleanChipToken("cucumber,"), "cucumber");
  assert.equal(cleanChipToken("cucumber."), "cucumber");
  assert.equal(cleanChipToken("cucumber;"), "cucumber");
  assert.equal(cleanChipToken("  cucumber. "), "cucumber");
});

test("parseChips keeps multiword entries as a single chip", () => {
  assert.deepEqual(parseChips("Salmon · Avocado · Cucumber · Rice · Purple cabbage"), [
    "Salmon",
    "Avocado",
    "Cucumber",
    "Rice",
    "Purple cabbage",
  ]);
});

test("parseChips drops blank entries from stray separators", () => {
  assert.deepEqual(parseChips("Salmon ·  · Rice"), ["Salmon", "Rice"]);
});

test("parseChips deduplicates case-insensitively, keeping first occurrence", () => {
  assert.deepEqual(parseChips("Rice · rice · RICE · Beans"), ["Rice", "Beans"]);
});

test("parseChips returns an empty list for empty/undefined input", () => {
  assert.deepEqual(parseChips(""), []);
  assert.deepEqual(parseChips(undefined), []);
});

test("chipsToStored joins chips back with the compact separator", () => {
  assert.equal(chipsToStored(["Salmon", "Avocado", "Cucumber"]), "Salmon · Avocado · Cucumber");
});

test("chipsToStored round-trips through parseChips", () => {
  const original = "Ground turkey · Purple cabbage · Rice";
  assert.equal(chipsToStored(parseChips(original)), original);
});

test("normalizeMethod converts commas/semicolons/arrows to a single arrow style", () => {
  assert.equal(
    normalizeMethod("roast sweet potatoes, brown turkey, assemble bowls"),
    "Roast sweet potatoes → Brown turkey → Assemble bowls"
  );
  assert.equal(
    normalizeMethod("bake meatballs; simmer in gravy"),
    "Bake meatballs → Simmer in gravy"
  );
});

test("normalizeMethod is idempotent on an already-arrow-joined string", () => {
  assert.equal(
    normalizeMethod("Cook salmon → Dice vegetables → Assemble"),
    "Cook salmon → Dice vegetables → Assemble"
  );
});

test("normalizeMethod trims whitespace and drops empty actions", () => {
  assert.equal(normalizeMethod("  sauté cabbage ,, add sauce ,  , serve over rice  "), "Sauté cabbage → Add sauce → Serve over rice");
});

test("normalizeMethod only capitalizes the first letter, preserving the rest of the phrase", () => {
  assert.equal(normalizeMethod("air fry tofu → stir fry veg"), "Air fry tofu → Stir fry veg");
});

test("normalizeMethod handles a single action with no separators", () => {
  assert.equal(normalizeMethod("simmer together"), "Simmer together");
});

test("normalizeMethod returns an empty string for empty/undefined input", () => {
  assert.equal(normalizeMethod(""), "");
  assert.equal(normalizeMethod(undefined), "");
});
