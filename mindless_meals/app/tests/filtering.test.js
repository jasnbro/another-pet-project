// Filtering: Effort/Type/Cuisine/Other + favorites-only (product spec §4-10).
// Run with: node --test mindless_meals/app/tests/filtering.test.js
const test = require("node:test");
const assert = require("node:assert/strict");
const { recipeMatchesFilters } = require("../static/js/filtering.js");

function emptyFilters() {
  return {
    effort: new Set(),
    type: new Set(),
    cuisine: new Set(),
    other: new Set(),
  };
}

const gochujangBowls = {
  id: 1,
  name: "Gochujang Turkey Bowls",
  effort: "easy",
  cuisine: "East Asian",
  meal_types: ["lunch", "dinner"],
  other_tags: ["high-protein", "reheat"],
};

const berryYogurt = {
  id: 2,
  name: "Berry Yogurt Bowls",
  effort: "easiest",
  cuisine: "Breakfast Rotation",
  meal_types: ["breakfast"],
  other_tags: ["fiber"],
};

test("no filters and not favorites-only matches everything", () => {
  assert.equal(recipeMatchesFilters(gochujangBowls, emptyFilters(), new Set(), false), true);
  assert.equal(recipeMatchesFilters(berryYogurt, emptyFilters(), new Set(), false), true);
});

test("effort filter excludes non-matching effort", () => {
  const filters = emptyFilters();
  filters.effort.add("easiest");
  assert.equal(recipeMatchesFilters(gochujangBowls, filters, new Set(), false), false);
  assert.equal(recipeMatchesFilters(berryYogurt, filters, new Set(), false), true);
});

test("cuisine filter matches on exact cuisine", () => {
  const filters = emptyFilters();
  filters.cuisine.add("East Asian");
  assert.equal(recipeMatchesFilters(gochujangBowls, filters, new Set(), false), true);
  assert.equal(recipeMatchesFilters(berryYogurt, filters, new Set(), false), false);
});

test("type filter matches if the recipe has any selected meal type", () => {
  const filters = emptyFilters();
  filters.type.add("breakfast");
  filters.type.add("dinner");
  // gochujangBowls has "dinner" -> matches even though it lacks "breakfast"
  assert.equal(recipeMatchesFilters(gochujangBowls, filters, new Set(), false), true);
  assert.equal(recipeMatchesFilters(berryYogurt, filters, new Set(), false), true);
});

test("other filter requires at least one matching tag", () => {
  const filters = emptyFilters();
  filters.other.add("freezer");
  assert.equal(recipeMatchesFilters(gochujangBowls, filters, new Set(), false), false);
  assert.equal(recipeMatchesFilters(berryYogurt, filters, new Set(), false), false);
});

test("filters across different groups combine with AND", () => {
  const filters = emptyFilters();
  filters.cuisine.add("East Asian");
  filters.other.add("reheat");
  assert.equal(recipeMatchesFilters(gochujangBowls, filters, new Set(), false), true);

  filters.other.add("freezer-friendly-that-doesnt-exist-on-this-recipe");
  filters.other.clear();
  filters.other.add("fiber"); // gochujangBowls doesn't have this tag
  assert.equal(recipeMatchesFilters(gochujangBowls, filters, new Set(), false), false);
});

test("favorites-only hides non-favorited recipes regardless of other filters", () => {
  assert.equal(
    recipeMatchesFilters(gochujangBowls, emptyFilters(), new Set([2]), true),
    false
  );
  assert.equal(
    recipeMatchesFilters(gochujangBowls, emptyFilters(), new Set([1, 2]), true),
    true
  );
});

test("search term matches the recipe name case-insensitively", () => {
  assert.equal(
    recipeMatchesFilters(gochujangBowls, emptyFilters(), new Set(), false, "gochujang"),
    true
  );
  assert.equal(
    recipeMatchesFilters(gochujangBowls, emptyFilters(), new Set(), false, "GOCHUJANG"),
    true
  );
  assert.equal(
    recipeMatchesFilters(gochujangBowls, emptyFilters(), new Set(), false, "yogurt"),
    false
  );
});

test("empty search term matches everything, same as no search", () => {
  assert.equal(recipeMatchesFilters(gochujangBowls, emptyFilters(), new Set(), false, ""), true);
});

test("search term combines with other filters as AND", () => {
  const filters = emptyFilters();
  filters.cuisine.add("Breakfast Rotation");
  // matches the cuisine filter but not the search term
  assert.equal(
    recipeMatchesFilters(berryYogurt, filters, new Set(), false, "gochujang"),
    false
  );
  assert.equal(recipeMatchesFilters(berryYogurt, filters, new Set(), false, "yogurt"), true);
});
