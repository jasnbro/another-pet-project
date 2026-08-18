/* Pure recipe-matching logic, factored out of mindless-meals.js so it can
 * be unit tested directly with Node's built-in test runner (see
 * tests/filtering.test.js) without needing a browser or a bundler.
 *
 * `filters` groups (effort/type/cuisine/other) are Set-like: anything
 * with `.size` and `.has()` works, so the browser can pass its live
 * Sets and tests can pass Sets built from plain arrays.
 */
function recipeMatchesFilters(recipe, filters, favoriteIds, showFavoritesOnly) {
  if (showFavoritesOnly && !favoriteIds.has(recipe.id)) return false;
  if (filters.effort.size && !filters.effort.has(recipe.effort)) return false;
  if (filters.cuisine.size && !filters.cuisine.has(recipe.cuisine)) return false;

  if (filters.type.size && !recipe.meal_types.some((t) => filters.type.has(t))) return false;
  if (filters.other.size && !recipe.other_tags.some((t) => filters.other.has(t))) return false;

  return true;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { recipeMatchesFilters };
}
