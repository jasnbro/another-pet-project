/* Pure text-formatting helpers for the Add/Edit Recipe form. Factored out
 * of chip-input.js/mindless-meals.js so the actual normalization rules
 * can be unit tested directly (see tests/format.test.js) without a DOM —
 * the same split filtering.js/filtering.test.js already uses.
 *
 * Ingredients/Sauce are stored as one "A · B · C" string (see
 * models.py's Recipe.ingredients/.sauce) — parseChipList/joinChipList
 * convert between that string and a clean, deduplicated array of chips
 * without changing the storage format at all.
 */
const CHIP_SEPARATOR = "·";

function normalizeChipEntry(raw) {
  return (raw || "")
    .trim()
    .replace(/[.,;]+$/, "") // trailing punctuation from accidental typing
    .replace(/\s+/g, " "); // collapse internal whitespace ("purple  cabbage")
}

function parseChipList(raw) {
  const parts = (raw || "")
    .split(CHIP_SEPARATOR)
    .map(normalizeChipEntry)
    .filter(Boolean);
  const seen = new Set();
  return parts.filter((value) => {
    const key = value.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function joinChipList(values) {
  return values.join(" " + CHIP_SEPARATOR + " ");
}

// "Roast sweet potatoes, brown turkey; assemble bowls" (or newline- or
// arrow-separated, or any mix) -> "Roast sweet potatoes → Brown turkey →
// Assemble bowls". Idempotent: normalizing an already-normalized string
// re-splits on the → it already contains and rejoins to the same result.
function normalizeMake(raw) {
  const actions = (raw || "")
    .split(/\r?\n|,|;|→|->/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1));
  return actions.join(" → ");
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { CHIP_SEPARATOR, normalizeChipEntry, parseChipList, joinChipList, normalizeMake };
}
