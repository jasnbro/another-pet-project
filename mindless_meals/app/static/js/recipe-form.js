/* Pure, DOM-free helpers for the Add/Edit Recipe form: ingredient/sauce
 * chip parsing and Make-field arrow normalization. Factored out of
 * mindless-meals.js the same way filtering.js is, so the parsing/
 * normalization rules can be unit tested directly with Node's test
 * runner (see tests/recipe-form.test.js) without a browser.
 *
 * Ingredients/sauce are still stored as a single delimited string on
 * the recipe (no schema change) — " · " joins chips on save, matching
 * the separator the seed data and card display already use.
 */
const CHIP_SEPARATOR = " · ";

// Trims whitespace and any trailing punctuation a user might type out
// of habit (e.g. "cucumber," or "rice."), so chips stay clean.
function cleanChipToken(raw) {
  return raw.trim().replace(/[.,;]+$/, "").trim();
}

// Splits a stored "a · b · c" string into deduplicated (case-insensitive),
// cleaned chip tokens, in order of first appearance. Used both to seed a
// chip input when editing an existing recipe and to defend a freshly
// typed string against accidental duplicates.
function parseChips(stored) {
  const seen = new Set();
  const chips = [];
  (stored || "").split("·").forEach((part) => {
    const cleaned = cleanChipToken(part);
    if (!cleaned) return;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    chips.push(cleaned);
  });
  return chips;
}

function chipsToStored(chips) {
  return chips.join(CHIP_SEPARATOR);
}

// Normalizes the Make field into "Action → Action → Action": accepts
// Enter/comma/semicolon/arrow as separators (Enter is converted to an
// arrow by the form's keydown handler before this runs), trims each
// action, drops empty ones, and capitalizes only the first letter of
// each action — never expanding or inventing steps.
function normalizeMethod(raw) {
  return (raw || "")
    .split(/[;,→]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" → ");
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { CHIP_SEPARATOR, cleanChipToken, parseChips, chipsToStored, normalizeMethod };
}
