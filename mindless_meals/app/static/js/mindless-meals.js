(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("mindless-meals-data").textContent);
  const favoriteIds = new Set(data.favoriteIds);
  const recipesById = new Map(data.recipes.map((r) => [r.id, r]));

  const filters = {
    effort: new Set(),
    type: new Set(),
    cuisine: new Set(),
    other: new Set(),
  };
  let showFavoritesOnly = false;
  let searchTerm = "";
  // recipeId -> Set of slot values ("breakfast" | "lunch" | "dinner" | "snack")
  const planDraft = new Map();

  // ─── EXPORT SELECTION MODE ───────────────────────────────────
  // Kept separate from planDraft/slot-pills on purpose (product spec
  // v1.1 §4: "Do not confuse recipe-export selection with the existing
  // Breakfast, Lunch, Dinner, and Snack meal-plan controls") — a
  // different Set, a different toolbar, checkboxes instead of pills.
  let selectionMode = false;
  const selectedIds = new Set();

  // How many matching recipes are revealed at once; "Show More" adds
  // another page. Purely a client-side reveal — every recipe is already
  // in the page's embedded JSON, so paging in more costs nothing (no
  // extra fetch, no extra DB query). Resets to PAGE_SIZE whenever the
  // filtered/searched result set changes.
  const PAGE_SIZE = 25;
  let revealCount = PAGE_SIZE;

  const cuisineSections = Array.from(document.querySelectorAll(".cuisine-section"));
  const emptyState = document.getElementById("empty-state");
  const activeFiltersEl = document.getElementById("active-filters");
  const showMoreBtn = document.getElementById("btn-show-more");

  // Map "group::value" -> the option button, built once. Used both to
  // toggle pressed-state and to read display labels for chips, so we
  // never need to re-query with escaped CSS selectors.
  const optionButtons = {};
  document.querySelectorAll(".filter-option").forEach((opt) => {
    optionButtons[opt.dataset.group + "::" + opt.dataset.value] = opt;
  });

  // ─── FILTER PANEL OPEN/CLOSE ─────────────────────────────────
  const controls = Array.from(document.querySelectorAll(".filter-control"));
  const panels = Array.from(document.querySelectorAll(".filter-panel"));

  function closeAllPanels() {
    controls.forEach((c) => c.setAttribute("aria-expanded", "false"));
    panels.forEach((p) => (p.hidden = true));
  }

  controls.forEach((control) => {
    control.addEventListener("click", () => {
      const group = control.dataset.group;
      const panel = document.getElementById("panel-" + group);
      const wasOpen = control.getAttribute("aria-expanded") === "true";
      closeAllPanels();
      if (!wasOpen) {
        control.setAttribute("aria-expanded", "true");
        panel.hidden = false;
      }
    });
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".filter-control") && !e.target.closest(".filter-panel")) {
      closeAllPanels();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllPanels();
  });

  // ─── FILTER OPTIONS ──────────────────────────────────────────
  document.querySelectorAll(".filter-option").forEach((opt) => {
    opt.addEventListener("click", () => {
      const group = opt.dataset.group;
      const value = opt.dataset.value;
      const pressed = opt.getAttribute("aria-pressed") === "true";
      if (pressed) {
        filters[group].delete(value);
        opt.setAttribute("aria-pressed", "false");
      } else {
        filters[group].add(value);
        opt.setAttribute("aria-pressed", "true");
      }
      updateFilterUI();
      applyFilters();
    });
  });

  document.querySelectorAll(".filter-panel__clear").forEach((btn) => {
    btn.addEventListener("click", () => clearGroup(btn.dataset.clear));
  });

  function clearGroup(group) {
    filters[group].clear();
    document.querySelectorAll('.filter-option[data-group="' + group + '"]').forEach((o) => {
      o.setAttribute("aria-pressed", "false");
    });
    updateFilterUI();
    applyFilters();
  }

  function updateFilterUI() {
    Object.keys(filters).forEach((group) => {
      const control = document.getElementById("control-" + group);
      const countEl = control.querySelector(".filter-control__count");
      const n = filters[group].size;
      countEl.hidden = n === 0;
      countEl.textContent = n || "";
    });
    renderChips();
  }

  function renderChips() {
    activeFiltersEl.innerHTML = "";
    let any = false;

    Object.entries(filters).forEach(([group, set]) => {
      set.forEach((value) => {
        any = true;
        const optionBtn = optionButtons[group + "::" + value];
        const label = optionBtn ? optionBtn.textContent.trim() : value;

        const chip = document.createElement("span");
        chip.className = "chip";
        chip.append(document.createTextNode(label + " "));

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.setAttribute("aria-label", "Remove filter " + label);
        removeBtn.textContent = "✕";
        removeBtn.addEventListener("click", () => {
          set.delete(value);
          if (optionBtn) optionBtn.setAttribute("aria-pressed", "false");
          updateFilterUI();
          applyFilters();
        });
        chip.appendChild(removeBtn);
        activeFiltersEl.appendChild(chip);
      });
    });

    if (any) {
      const resetBtn = document.createElement("button");
      resetBtn.type = "button";
      resetBtn.className = "chip-reset";
      resetBtn.textContent = "Clear all filters";
      resetBtn.addEventListener("click", () => {
        Object.keys(filters).forEach(clearGroup);
      });
      activeFiltersEl.appendChild(resetBtn);
    }
  }

  // ─── APPLYING FILTERS ────────────────────────────────────────
  // recipesById already holds every field (from the page's embedded
  // JSON), so matching works directly off that rather than re-reading
  // fragments back out of data-* attributes. recipeMatchesFilters
  // (filtering.js) is the shared, testable source of truth for the
  // actual matching rules.
  function recipeMatches(article) {
    const recipe = recipesById.get(Number(article.dataset.id));
    if (!recipe) return false;
    return recipeMatchesFilters(recipe, filters, favoriteIds, showFavoritesOnly, searchTerm);
  }

  // resetReveal=false is used only by the Show More button, which wants
  // to keep whatever's already revealed and just extend it.
  function applyFilters(resetReveal = true) {
    if (resetReveal) revealCount = PAGE_SIZE;

    const allArticles = Array.from(document.querySelectorAll(".recipe"));
    const matching = allArticles.filter(recipeMatches);
    const revealed = new Set(matching.slice(0, revealCount));

    let anyVisible = false;
    cuisineSections.forEach((section) => {
      let sectionVisible = false;
      section.querySelectorAll(".recipe").forEach((article) => {
        const isRevealed = revealed.has(article);
        article.hidden = !isRevealed;
        if (isRevealed) sectionVisible = true;
      });
      section.hidden = !sectionVisible;
      if (sectionVisible) anyVisible = true;
    });
    emptyState.hidden = anyVisible;

    const remaining = matching.length - revealed.size;
    showMoreBtn.hidden = remaining <= 0;
    if (remaining > 0) {
      showMoreBtn.textContent = "Show More (" + remaining + " more)";
    }
  }

  showMoreBtn.addEventListener("click", () => {
    revealCount += PAGE_SIZE;
    applyFilters(false);
  });

  // ─── FAVORITES ───────────────────────────────────────────────
  document.querySelectorAll(".favorite-toggle").forEach((btn) => {
    btn.addEventListener("click", () => toggleFavorite(btn));
  });

  async function toggleFavorite(btn) {
    const id = Number(btn.dataset.recipeId);
    const isFav = btn.getAttribute("aria-pressed") === "true";
    btn.disabled = true;
    try {
      const res = await fetch("/api/favorites/" + id, { method: isFav ? "DELETE" : "POST" });
      if (!res.ok) throw new Error("Could not update favorite.");
      const result = await res.json();
      const icon = btn.querySelector("span");
      if (result.favorited) {
        favoriteIds.add(id);
        btn.setAttribute("aria-pressed", "true");
        icon.textContent = "★";
      } else {
        favoriteIds.delete(id);
        btn.setAttribute("aria-pressed", "false");
        icon.textContent = "☆";
      }
      if (showFavoritesOnly) applyFilters();
    } catch (err) {
      // Leave the star as it was — nothing changed server-side.
    } finally {
      btn.disabled = false;
    }
  }

  const btnViewFavorites = document.getElementById("btn-view-favorites");
  btnViewFavorites.addEventListener("click", () => {
    showFavoritesOnly = !showFavoritesOnly;
    btnViewFavorites.setAttribute("aria-pressed", String(showFavoritesOnly));
    applyFilters();
  });

  // ─── SEARCH ──────────────────────────────────────────────────
  document.getElementById("recipe-search").addEventListener("input", (e) => {
    searchTerm = e.target.value.trim();
    applyFilters();
  });

  // ─── EXPORT SELECTION MODE ───────────────────────────────────
  const selectionToolbar = document.getElementById("selection-toolbar");
  const selectionCountEl = document.getElementById("selection-count");
  const btnExportSelected = document.getElementById("btn-export-selected");

  function updateSelectionCount() {
    selectionCountEl.textContent = selectedIds.size + " selected";
    btnExportSelected.disabled = selectedIds.size === 0;
  }

  function syncSelectionCheckboxes() {
    document.querySelectorAll(".select-checkbox").forEach((cb) => {
      cb.checked = selectedIds.has(Number(cb.dataset.recipeId));
    });
  }

  function enterSelectionMode() {
    selectionMode = true;
    document.body.classList.add("selection-mode");
    selectionToolbar.hidden = false;
    syncSelectionCheckboxes();
    updateSelectionCount();
  }

  function exitSelectionMode() {
    selectionMode = false;
    document.body.classList.remove("selection-mode");
    selectionToolbar.hidden = true;
  }

  document.querySelectorAll(".select-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      const id = Number(cb.dataset.recipeId);
      if (cb.checked) selectedIds.add(id);
      else selectedIds.delete(id);
      updateSelectionCount();
    });
  });

  document.getElementById("btn-select-all-shown").addEventListener("click", () => {
    document.querySelectorAll(".recipe:not([hidden]) .select-checkbox").forEach((cb) => {
      selectedIds.add(Number(cb.dataset.recipeId));
    });
    syncSelectionCheckboxes();
    updateSelectionCount();
  });

  document.getElementById("btn-clear-selection").addEventListener("click", () => {
    selectedIds.clear();
    syncSelectionCheckboxes();
    updateSelectionCount();
  });

  document.getElementById("btn-cancel-selection").addEventListener("click", () => {
    selectedIds.clear();
    exitSelectionMode();
  });

  btnExportSelected.addEventListener("click", () => {
    if (!selectedIds.size) return;
    triggerRecipesExport(Array.from(selectedIds));
    selectedIds.clear();
    exitSelectionMode();
  });

  // ─── MEAL PLAN DRAFT (slot pills on each recipe) ────────────
  function recipeNameById(id) {
    const article = document.querySelector('.recipe[data-id="' + id + '"]');
    return article ? article.querySelector(".recipe__name").textContent : "Recipe";
  }

  document.querySelectorAll(".slot-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const id = Number(pill.dataset.recipeId);
      const slot = pill.dataset.slot;
      if (!planDraft.has(id)) planDraft.set(id, new Set());
      const slots = planDraft.get(id);
      const pressed = pill.getAttribute("aria-pressed") === "true";
      if (pressed) {
        slots.delete(slot);
        if (slots.size === 0) planDraft.delete(id);
        pill.setAttribute("aria-pressed", "false");
      } else {
        slots.add(slot);
        pill.setAttribute("aria-pressed", "true");
      }
      renderPlanList();
    });
  });

  // ─── SAVE MEAL PLAN DIALOG ───────────────────────────────────
  const mealPlanDialog = document.getElementById("meal-plan-dialog");
  const planListEl = document.getElementById("plan-list");
  const planEmptyMsg = document.getElementById("plan-empty-message");
  const planMessage = document.getElementById("plan-message");
  const btnSavePlanConfirm = document.getElementById("btn-save-plan-confirm");
  const savePlanDot = document.getElementById("save-plan-dot");

  // The Save Meal Plan dot only fills in once there's actually a draft
  // to save — it isn't a permanent decoration, and isn't a "you have
  // this open" indicator either (there's no persistent open/closed
  // state for a dialog you can only reach by clicking the button).
  function updateSavePlanDot() {
    savePlanDot.classList.toggle("utility-nav__dot--filled", planDraft.size > 0);
  }

  function renderPlanList() {
    updateSavePlanDot();
    planListEl.innerHTML = "";
    let count = 0;
    planDraft.forEach((slots, id) => {
      slots.forEach((slot) => {
        count += 1;
        const li = document.createElement("li");

        const left = document.createElement("span");
        const slotTag = document.createElement("span");
        slotTag.className = "plan-list__slot";
        slotTag.textContent = slot;
        left.appendChild(slotTag);
        left.append(document.createTextNode(recipeNameById(id)));

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "plan-list__remove";
        removeBtn.textContent = "Remove";
        removeBtn.addEventListener("click", () => {
          slots.delete(slot);
          if (slots.size === 0) planDraft.delete(id);
          const pill = document.querySelector(
            '.slot-pill[data-recipe-id="' + id + '"][data-slot="' + slot + '"]'
          );
          if (pill) pill.setAttribute("aria-pressed", "false");
          renderPlanList();
        });

        li.appendChild(left);
        li.appendChild(removeBtn);
        planListEl.appendChild(li);
      });
    });
    planEmptyMsg.hidden = count > 0;
    btnSavePlanConfirm.disabled = count === 0;
  }

  document.getElementById("btn-save-plan").addEventListener("click", () => {
    planMessage.textContent = "";
    renderPlanList();
    mealPlanDialog.showModal();
  });

  document.getElementById("btn-clear-plan").addEventListener("click", () => {
    planDraft.forEach((slots, id) => {
      slots.forEach((slot) => {
        const pill = document.querySelector(
          '.slot-pill[data-recipe-id="' + id + '"][data-slot="' + slot + '"]'
        );
        if (pill) pill.setAttribute("aria-pressed", "false");
      });
    });
    planDraft.clear();
    planMessage.textContent = "";
    renderPlanList();
  });

  btnSavePlanConfirm.addEventListener("click", async () => {
    const items = [];
    planDraft.forEach((slots, recipe_id) => {
      slots.forEach((slot) => items.push({ recipe_id, slot }));
    });
    if (!items.length) return;

    try {
      const res = await fetch("/api/meal-plans", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Could not save plan.");
      planMessage.style.color = "var(--green)";
      planMessage.textContent = "Saved.";
    } catch (err) {
      planMessage.style.color = "var(--effort-more)";
      planMessage.textContent = err.message;
    }
  });

  document.getElementById("btn-view-recent-plan").addEventListener("click", async () => {
    try {
      const res = await fetch("/api/meal-plans/current");
      const plan = await res.json();
      if (!plan) {
        planMessage.style.color = "var(--ink-muted)";
        planMessage.textContent = "No saved plan yet.";
        return;
      }
      planListEl.innerHTML = "";
      plan.items.forEach((item) => {
        const li = document.createElement("li");
        const left = document.createElement("span");
        const slotTag = document.createElement("span");
        slotTag.className = "plan-list__slot";
        slotTag.textContent = item.slot || "";
        left.appendChild(slotTag);
        left.append(document.createTextNode(item.recipe_name));
        li.appendChild(left);
        planListEl.appendChild(li);
      });
      planEmptyMsg.hidden = plan.items.length > 0;
      planMessage.style.color = "var(--ink-muted)";
      planMessage.textContent =
        'Showing "' + plan.name + '" — saved ' + new Date(plan.created_at).toLocaleDateString() + ".";
    } catch (err) {
      planMessage.style.color = "var(--effort-more)";
      planMessage.textContent = "Could not load the recent plan.";
    }
  });

  // ─── ADD / EDIT RECIPE DIALOG ────────────────────────────────
  // The same dialog and form serve both flows: Add Recipe opens it
  // empty, Edit opens it pre-filled from the recipe's own data (already
  // embedded in the page — no extra fetch needed) and remembers the
  // recipe id in a hidden field so Save knows whether to POST or PUT.
  //
  // v1.1: the form's primary action is "Preview Recipe", not a direct
  // save — nothing reaches the server until Save Recipe is clicked from
  // the preview step (product spec v1.1 §3). Ingredients/Sauce are chip
  // inputs (§1) that keep a hidden field in sync with the same "A · B ·
  // C" string the backend has always stored; Make is a textarea whose
  // content gets arrow-normalized (§2, format.js) at preview/save time.
  const addRecipeDialog = document.getElementById("add-recipe-dialog");
  const addRecipeForm = document.getElementById("add-recipe-form");
  const addRecipeMessage = document.getElementById("add-recipe-message");
  const addRecipeTitle = document.getElementById("add-recipe-title");
  const recipeIdField = document.getElementById("field-recipe-id");
  const deleteRecipeBtn = document.getElementById("btn-delete-recipe");
  const methodField = document.getElementById("field-method");

  const ingredientsChip = createChipInput({
    chipsContainer: document.getElementById("chips-ingredients"),
    entryInput: document.getElementById("field-ingredients-entry"),
    hiddenInput: document.getElementById("field-ingredients"),
  });
  const sauceChip = createChipInput({
    chipsContainer: document.getElementById("chips-sauce"),
    entryInput: document.getElementById("field-sauce-entry"),
    hiddenInput: document.getElementById("field-sauce"),
  });

  const btnPreviewRecipe = document.getElementById("btn-preview-recipe");
  const recipePreviewPanel = document.getElementById("recipe-preview");
  const recipePreviewCard = document.getElementById("recipe-preview-card");
  const btnSaveRecipe = document.getElementById("btn-save-recipe");
  const btnBackToEdit = document.getElementById("btn-back-to-edit");
  const previewMessage = document.getElementById("preview-message");

  let dialogMode = "add"; // "add" | "edit" — decides the title on Back to Edit
  let editingRecipeId = null;
  let pendingPayload = null; // built by Preview, sent to the server by Save

  function showEditStep() {
    recipePreviewPanel.hidden = true;
    addRecipeForm.hidden = false;
    addRecipeTitle.textContent = dialogMode === "edit" ? "Edit Recipe" : "Add Recipe";
  }

  function openRecipeDialog(recipe) {
    addRecipeMessage.textContent = "";
    previewMessage.textContent = "";
    pendingPayload = null;
    addRecipeForm.reset();
    ingredientsChip.setValue(recipe ? recipe.ingredients : "");
    sauceChip.setValue(recipe ? recipe.sauce || "" : "");

    if (recipe) {
      dialogMode = "edit";
      editingRecipeId = recipe.id;
      deleteRecipeBtn.hidden = false;
      recipeIdField.value = recipe.id;
      addRecipeForm.elements["name"].value = recipe.name;
      addRecipeForm.elements["cuisine"].value = recipe.cuisine;
      methodField.value = recipe.method;
      addRecipeForm.elements["source_url"].value = recipe.source_url || "";
      addRecipeForm.querySelectorAll('input[name="effort"]').forEach((el) => {
        el.checked = el.value === recipe.effort;
      });
      addRecipeForm.querySelectorAll('input[name="meal_types"]').forEach((el) => {
        el.checked = recipe.meal_types.includes(el.value);
      });
      addRecipeForm.querySelectorAll('input[name="other_tags"]').forEach((el) => {
        el.checked = recipe.other_tags.includes(el.value);
      });
    } else {
      dialogMode = "add";
      editingRecipeId = null;
      deleteRecipeBtn.hidden = true;
      recipeIdField.value = "";
    }

    showEditStep();
    addRecipeDialog.showModal();
  }

  document.getElementById("btn-add-recipe").addEventListener("click", () => openRecipeDialog(null));

  document.querySelectorAll(".edit-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const recipe = recipesById.get(Number(btn.dataset.recipeId));
      if (recipe) openRecipeDialog(recipe);
    });
  });

  deleteRecipeBtn.addEventListener("click", async () => {
    const recipeId = recipeIdField.value;
    if (!recipeId) return;
    const recipe = recipesById.get(Number(recipeId));
    const name = recipe ? recipe.name : "this recipe";
    if (!window.confirm('Delete "' + name + '"? This also removes it from any favorites or saved meal plans.')) {
      return;
    }
    try {
      const res = await fetch("/api/recipes/" + recipeId, { method: "DELETE" });
      if (!res.ok) throw new Error("Could not delete recipe.");
      window.location.reload();
    } catch (err) {
      addRecipeMessage.textContent = err.message;
    }
  });

  // ─── Preview step ─────────────────────────────────────────
  function slugifyTag(value) {
    return value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function titleCaseWords(value) {
    return value.replace(/\S+/g, (w) => w.charAt(0).toUpperCase() + w.slice(1));
  }

  // Mirrors models.py's other_tag_label(): a checkbox's own rendered
  // label if this is a known tag, otherwise the same title-cased
  // fallback the backend uses for freeform tags.
  function otherTagDisplayLabel(slug) {
    const checkbox = addRecipeForm.querySelector('input[name="other_tags"][value="' + slug + '"]');
    if (checkbox) return checkbox.closest("label").textContent.trim();
    return titleCaseWords(slug.replace(/-/g, " "));
  }

  function buildOtherTagsDisplay(rawTags) {
    const seen = new Set();
    const slugs = [];
    rawTags.forEach((raw) => {
      const slug = slugifyTag(raw);
      if (slug && !seen.has(slug)) {
        seen.add(slug);
        slugs.push(slug);
      }
    });
    return slugs.map(otherTagDisplayLabel);
  }

  function buildPayloadFromForm() {
    const formData = new FormData(addRecipeForm);
    const otherTags = formData.getAll("other_tags");
    (formData.get("other_tags_custom") || "").split(",").forEach((t) => {
      const trimmed = t.trim();
      if (trimmed) otherTags.push(trimmed);
    });

    return {
      name: (formData.get("name") || "").trim(),
      cuisine: (formData.get("cuisine") || "").trim(),
      effort: formData.get("effort"),
      ingredients: ingredientsChip.getValue(),
      sauce: sauceChip.getValue(),
      method: normalizeMake(methodField.value),
      source_url: (formData.get("source_url") || "").trim(),
      meal_types: formData.getAll("meal_types"),
      other_tags: otherTags,
    };
  }

  function buildPreviewRecipe(payload) {
    const effortInput = addRecipeForm.querySelector('input[name="effort"]:checked');
    const effortLabel = effortInput ? effortInput.closest("label").textContent.trim() : payload.effort;
    return {
      name: payload.name,
      cuisine: payload.cuisine,
      effort: payload.effort,
      effort_label: effortLabel,
      ingredients: payload.ingredients,
      sauce: payload.sauce || null,
      method: payload.method,
      source_url: payload.source_url || null,
      other_tags_display: buildOtherTagsDisplay(payload.other_tags),
    };
  }

  function buildRecipeSection(label, text) {
    const section = document.createElement("div");
    section.className = "recipe__section";
    const labelEl = document.createElement("div");
    labelEl.className = "recipe__label";
    labelEl.textContent = label;
    const textEl = document.createElement("div");
    textEl.className = "recipe__text";
    textEl.textContent = text;
    section.appendChild(labelEl);
    section.appendChild(textEl);
    return section;
  }

  // Mirrors the server-rendered .recipe card markup (templates/index.html)
  // closely enough to inherit its styling exactly, minus the controls
  // that don't apply to a not-yet-saved preview (favorite star, edit
  // link, meal-plan slot pills).
  function buildPreviewCard(recipe) {
    const wrapper = document.createDocumentFragment();

    const cuisineLine = document.createElement("div");
    cuisineLine.className = "recipe-preview__cuisine";
    cuisineLine.textContent = recipe.cuisine;
    wrapper.appendChild(cuisineLine);

    const article = document.createElement("div");
    article.className = "recipe";

    const top = document.createElement("div");
    top.className = "recipe__top";
    const name = document.createElement("h3");
    name.className = "recipe__name";
    name.textContent = recipe.name;
    top.appendChild(name);
    const effortTag = document.createElement("span");
    effortTag.className = "effort-tag";
    effortTag.style.background = "var(--effort-" + recipe.effort.replace(/_/g, "-") + ")";
    effortTag.style.color = "#fff";
    effortTag.textContent = recipe.effort_label;
    top.appendChild(effortTag);
    article.appendChild(top);

    article.appendChild(buildRecipeSection("Ingredients", recipe.ingredients));
    if (recipe.sauce) {
      article.appendChild(buildRecipeSection("Sauce", recipe.sauce));
    }
    article.appendChild(buildRecipeSection("Make", recipe.method));

    if (recipe.source_url) {
      const link = document.createElement("a");
      link.className = "recipe__source";
      link.href = recipe.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "↗ Recipe Link";
      article.appendChild(link);
    }

    if (recipe.other_tags_display.length) {
      const otherWrap = document.createElement("div");
      otherWrap.className = "recipe__other";
      recipe.other_tags_display.forEach((label) => {
        const tag = document.createElement("span");
        tag.className = "other-tag";
        tag.textContent = label;
        otherWrap.appendChild(tag);
      });
      article.appendChild(otherWrap);
    }

    wrapper.appendChild(article);
    return wrapper;
  }

  btnPreviewRecipe.addEventListener("click", () => {
    addRecipeMessage.textContent = "";
    if (!addRecipeForm.reportValidity()) return;
    if (!ingredientsChip.getValue()) {
      addRecipeMessage.textContent = "Add at least one ingredient.";
      return;
    }
    if (!normalizeMake(methodField.value)) {
      addRecipeMessage.textContent = "Add at least one Make step.";
      return;
    }

    pendingPayload = buildPayloadFromForm();
    const previewRecipe = buildPreviewRecipe(pendingPayload);
    recipePreviewCard.innerHTML = "";
    recipePreviewCard.appendChild(buildPreviewCard(previewRecipe));

    addRecipeTitle.textContent = "Preview Recipe";
    addRecipeForm.hidden = true;
    recipePreviewPanel.hidden = false;
    previewMessage.textContent = "";
    btnSaveRecipe.disabled = false;
    btnSaveRecipe.focus();
  });

  btnBackToEdit.addEventListener("click", showEditStep);

  // Pressing Enter anywhere in the form (e.g. in the Name field) behaves
  // like clicking Preview Recipe rather than doing nothing/submitting
  // the page — the chip-input entries already stop their own Enter
  // presses from bubbling this far (they commit a chip instead).
  addRecipeForm.addEventListener("submit", (e) => {
    e.preventDefault();
    btnPreviewRecipe.click();
  });

  btnSaveRecipe.addEventListener("click", async () => {
    if (!pendingPayload) return;
    btnSaveRecipe.disabled = true;
    const url = editingRecipeId ? "/api/recipes/" + editingRecipeId : "/api/recipes";
    const method = editingRecipeId ? "PUT" : "POST";
    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(pendingPayload),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Could not save recipe.");
      window.location.reload();
    } catch (err) {
      previewMessage.textContent = err.message;
      btnSaveRecipe.disabled = false;
    }
  });

  // ─── EXPORT DIALOG ────────────────────────────────────────────
  const exportDialog = document.getElementById("export-dialog");
  const exportMessage = document.getElementById("export-message");

  function triggerRecipesExport(ids) {
    const url = "/api/recipes/export" + (ids ? "?ids=" + ids.join(",") : "");
    window.location.href = url;
  }

  function triggerMealPlanExport() {
    window.location.href = "/api/meal-plans/current/export";
  }

  function setExportOptionState(key, count, itemNoun, reasonIfDisabled) {
    const input = exportDialog.querySelector('input[name="export-scope"][value="' + key + '"]');
    const option = input.closest(".export-option");
    const countEl = document.getElementById("export-count-" + key);
    const disabled = count === 0;
    input.disabled = disabled;
    option.classList.toggle("export-option--disabled", disabled);
    countEl.textContent = disabled ? reasonIfDisabled : count + " " + itemNoun + (count === 1 ? "" : "s");
    if (disabled && input.checked) {
      exportDialog.querySelector('input[name="export-scope"][value="all"]').checked = true;
    }
  }

  async function openExportDialog() {
    exportMessage.textContent = "";
    document.getElementById("export-count-all").textContent =
      data.recipes.length + " recipe" + (data.recipes.length === 1 ? "" : "s");

    setExportOptionState("favorites", favoriteIds.size, "recipe", "No favorites yet");

    const filteredMatches = data.recipes.filter((r) =>
      recipeMatchesFilters(r, filters, favoriteIds, showFavoritesOnly, searchTerm)
    );
    setExportOptionState("filtered", filteredMatches.length, "recipe", "No recipes match the current filters");

    setExportOptionState("selected", selectedIds.size, "recipe", "No recipes selected yet — use Choose recipes below");

    exportDialog.showModal();

    try {
      const res = await fetch("/api/meal-plans/current");
      const plan = await res.json();
      const count = plan ? plan.items.length : 0;
      setExportOptionState("current-plan", count, "entry", "No saved meal plan yet");
    } catch (err) {
      setExportOptionState("current-plan", 0, "entry", "Could not check the saved meal plan");
    }
  }

  document.getElementById("btn-export").addEventListener("click", openExportDialog);

  document.getElementById("btn-start-selection").addEventListener("click", () => {
    exportDialog.close();
    enterSelectionMode();
  });

  document.getElementById("btn-export-confirm").addEventListener("click", () => {
    const scope = exportDialog.querySelector('input[name="export-scope"]:checked').value;
    if (scope === "all") {
      triggerRecipesExport(null);
    } else if (scope === "favorites") {
      triggerRecipesExport(Array.from(favoriteIds));
    } else if (scope === "filtered") {
      const ids = data.recipes
        .filter((r) => recipeMatchesFilters(r, filters, favoriteIds, showFavoritesOnly, searchTerm))
        .map((r) => r.id);
      triggerRecipesExport(ids);
    } else if (scope === "selected") {
      triggerRecipesExport(Array.from(selectedIds));
    } else if (scope === "current-plan") {
      triggerMealPlanExport();
    }
    exportDialog.close();
  });

  // ─── DIALOG DISMISSAL ────────────────────────────────────────
  document.querySelectorAll("[data-close-dialog]").forEach((btn) => {
    btn.addEventListener("click", () => btn.closest("dialog").close());
  });
  [addRecipeDialog, mealPlanDialog, exportDialog].forEach((dialog) => {
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) dialog.close();
    });
  });

  // ─── INITIAL RENDER ──────────────────────────────────────────
  // The server renders every matching recipe with no hidden attribute;
  // apply the initial reveal cap (and Show More button state) before
  // the user does anything.
  applyFilters();
})();
