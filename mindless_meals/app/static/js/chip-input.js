/* Tokenized chip input for Ingredients/Sauce in the Add/Edit Recipe form.
 * DOM wiring only — the actual parsing/joining/dedup rules live in
 * format.js so they're unit-testable on their own.
 *
 * Keeps a hidden <input> (the real form field submitted with the recipe)
 * in sync with the compact "A · B · C" string format the rest of the app
 * already uses — this is purely a data-entry affordance on top of that
 * same string field, not a new data shape.
 */
function createChipInput({ chipsContainer, entryInput, hiddenInput }) {
  let values = [];
  // Index of a chip pending removal via a second Backspace ("select, then
  // remove" — the same two-step pattern used by most chip/token inputs so
  // a stray Backspace can't silently delete the wrong thing).
  let selectedIndex = -1;

  function sync() {
    hiddenInput.value = joinChipList(values);
  }

  function render() {
    chipsContainer.innerHTML = "";
    values.forEach((value, index) => {
      const chip = document.createElement("span");
      chip.className = "chip chip--input" + (index === selectedIndex ? " chip--selected" : "");
      chip.setAttribute("role", "listitem");
      chip.append(document.createTextNode(value + " "));

      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.setAttribute("aria-label", "Remove " + value);
      removeBtn.textContent = "✕";
      removeBtn.addEventListener("click", () => {
        removeAt(index);
        entryInput.focus();
      });
      chip.appendChild(removeBtn);
      chipsContainer.appendChild(chip);
    });
  }

  function addValue(raw) {
    const candidate = normalizeChipEntry(raw);
    if (!candidate) return;
    const isDuplicate = values.some((v) => v.toLowerCase() === candidate.toLowerCase());
    if (isDuplicate) return;
    values.push(candidate);
    selectedIndex = -1;
    render();
    sync();
  }

  function removeAt(index) {
    if (index < 0 || index >= values.length) return;
    values.splice(index, 1);
    selectedIndex = -1;
    render();
    sync();
  }

  function commitEntry() {
    if (!entryInput.value.trim()) return;
    addValue(entryInput.value);
    entryInput.value = "";
  }

  entryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault(); // never submit the form from here
      commitEntry();
    } else if (e.key === ",") {
      e.preventDefault();
      commitEntry();
    } else if (e.key === "Backspace" && entryInput.value === "") {
      e.preventDefault();
      if (selectedIndex === values.length - 1) {
        removeAt(selectedIndex);
      } else if (values.length > 0) {
        selectedIndex = values.length - 1;
        render();
      }
    } else if (selectedIndex !== -1) {
      selectedIndex = -1;
      render();
    }
  });

  entryInput.addEventListener("blur", commitEntry);

  return {
    getValue: () => joinChipList(values),
    setValue(str) {
      values = parseChipList(str);
      selectedIndex = -1;
      entryInput.value = "";
      render();
      sync();
    },
    focus: () => entryInput.focus(),
  };
}
