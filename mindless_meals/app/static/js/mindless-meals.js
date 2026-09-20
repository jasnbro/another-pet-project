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
  // recipe id in a hidden field so submit knows whether to POST or PUT.
  const addRecipeDialog = document.getElementById("add-recipe-dialog");
  const addRecipeForm = document.getElementById("add-recipe-form");
  const addRecipeMessage = document.getElementById("add-recipe-message");
  const addRecipeTitle = document.getElementById("add-recipe-title");
  const recipeIdField = document.getElementById("field-recipe-id");
  const btnPreviewRecipe = document.getElementById("btn-preview-recipe");
  const deleteRecipeBtn = document.getElementById("btn-delete-recipe");
  const recipeEditStep = document.getElementById("recipe-edit-step");
  const recipePreviewStep = document.getElementById("recipe-preview-step");
  const btnBackToEdit = document.getElementById("btn-back-to-edit");
  const btnSaveRecipe = document.getElementById("btn-save-recipe");
  const previewCardContainer = document.getElementById("recipe-preview-card");

  // ─── INGREDIENT/SAUCE CHIP INPUT ─────────────────────────────
  // A small reusable chip-token widget: Enter, comma, or blur commits
  // the current text as a chip; each chip has an "x" to remove it; an
  // empty input + Backspace selects, then removes, the last chip. The
  // hidden input always carries the canonical " · "-joined string the
  // API and recipe card display already expect (see recipe-form.js) —
  // no data-model change needed.
  function createChipInput(containerEl, textInput, hiddenInput) {
    let chips = [];
    let selectedIndex = -1;

    function render() {
      containerEl.querySelectorAll(".chip").forEach((el) => el.remove());
      chips.forEach((chip, index) => {
        const chipEl = document.createElement("span");
        chipEl.className = "chip" + (index === selectedIndex ? " chip--selected" : "");
        chipEl.append(document.createTextNode(chip + " "));

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.setAttribute("aria-label", "Remove " + chip);
        removeBtn.textContent = "×";
        removeBtn.addEventListener("click", () => {
          chips.splice(index, 1);
          selectedIndex = -1;
          render();
          textInput.focus();
        });
        chipEl.appendChild(removeBtn);
        containerEl.insertBefore(chipEl, textInput);
      });
      hiddenInput.value = chipsToStored(chips);
    }

    function commitPendingText() {
      const cleaned = cleanChipToken(textInput.value);
      textInput.value = "";
      if (!cleaned) return;
      const key = cleaned.toLowerCase();
      if (chips.some((c) => c.toLowerCase() === key)) return;
      chips.push(cleaned);
      selectedIndex = -1;
      render();
    }

    textInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        commitPendingText();
      } else if (e.key === "Backspace" && textInput.value === "") {
        if (!chips.length) return;
        e.preventDefault();
        if (selectedIndex === chips.length - 1) {
          chips.pop();
          selectedIndex = -1;
        } else {
          selectedIndex = chips.length - 1;
        }
        render();
      } else {
        selectedIndex = -1;
      }
    });

    textInput.addEventListener("blur", commitPendingText);

    return {
      setChips(stored) {
        chips = parseChips(stored);
        selectedIndex = -1;
        textInput.value = "";
        render();
      },
      reset() {
        chips = [];
        selectedIndex = -1;
        textInput.value = "";
        render();
      },
      getValue() {
        return chipsToStored(chips);
      },
    };
  }

  const ingredientsChip = createChipInput(
    document.getElementById("ingredients-chip-input"),
    document.getElementById("field-ingredients-input"),
    document.getElementById("field-ingredients")
  );
  const sauceChip = createChipInput(
    document.getElementById("sauce-chip-input"),
    document.getElementById("field-sauce-input"),
    document.getElementById("field-sauce")
  );

  // Enter acts as an action separator in the Make field without turning
  // it into a multi-line textarea — it just inserts the canonical arrow,
  // matching the muscle memory of the chip inputs above.
  document.getElementById("field-method").addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const field = e.target;
    const trimmed = field.value.trim();
    if (!trimmed || trimmed.endsWith("→")) return;
    field.value = trimmed + " → ";
  });

  // ─── PREVIEW STEP ────────────────────────────────────────────
  function showEditStep() {
    recipeEditStep.hidden = false;
    recipePreviewStep.hidden = true;
    btnSaveRecipe.disabled = true;
  }

  function showPreviewStep() {
    recipeEditStep.hidden = true;
    recipePreviewStep.hidden = false;
    btnSaveRecipe.disabled = false;
  }

  function titleCaseTag(raw) {
    return raw.replace(/[-_]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function buildDraftRecipe() {
    const formData = new FormData(addRecipeForm);
    const effortLabel = addRecipeForm
      .querySelector('input[name="effort"]:checked')
      .closest("label")
      .textContent.trim();
    const otherLabels = Array.from(
      addRecipeForm.querySelectorAll('input[name="other_tags"]:checked')
    ).map((el) => el.closest("label").textContent.trim());
    const customTags = (formData.get("other_tags_custom") || "")
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean)
      .map(titleCaseTag);

    return {
      name: (formData.get("name") || "").trim(),
      cuisine: (formData.get("cuisine") || "").trim(),
      effort: formData.get("effort"),
      effort_label: effortLabel,
      ingredients: ingredientsChip.getValue(),
      sauce: sauceChip.getValue() || null,
      method: normalizeMethod(formData.get("method")),
      source_url: (formData.get("source_url") || "").trim() || null,
      other_tags_display: [...otherLabels, ...customTags],
    };
  }

  function makeSection(label, text) {
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

  // Mirrors the server-rendered .recipe card markup closely enough to
  // preview accurately, minus the controls (favorite/edit/slot pills)
  // that only make sense for a recipe that's already saved.
  function renderPreview(draft) {
    previewCardContainer.innerHTML = "";
    const article = document.createElement("article");
    article.className = "recipe";

    const top = document.createElement("div");
    top.className = "recipe__top";
    const name = document.createElement("h3");
    name.className = "recipe__name";
    name.textContent = draft.name;
    const effortTag = document.createElement("span");
    effortTag.className = "effort-tag";
    effortTag.style.background = "var(--effort-" + draft.effort.replace(/_/g, "-") + ")";
    effortTag.style.color = "#fff";
    effortTag.textContent = draft.effort_label;
    top.appendChild(name);
    top.appendChild(effortTag);
    article.appendChild(top);

    article.appendChild(makeSection("Cuisine", draft.cuisine));
    article.appendChild(makeSection("Ingredients", draft.ingredients));
    if (draft.sauce) {
      article.appendChild(makeSection("Sauce", draft.sauce));
    }
    article.appendChild(makeSection("Make", draft.method));

    if (draft.source_url) {
      const link = document.createElement("a");
      link.className = "recipe__source";
      link.href = draft.source_url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = "↗ Recipe Link";
      article.appendChild(link);
    }

    if (draft.other_tags_display.length) {
      const otherWrap = document.createElement("div");
      otherWrap.className = "recipe__other";
      draft.other_tags_display.forEach((label) => {
        const span = document.createElement("span");
        span.className = "other-tag";
        span.textContent = label;
        otherWrap.appendChild(span);
      });
      article.appendChild(otherWrap);
    }

    previewCardContainer.appendChild(article);
  }

  btnPreviewRecipe.addEventListener("click", () => {
    addRecipeMessage.textContent = "";
    if (!addRecipeForm.reportValidity()) return;
    if (!ingredientsChip.getValue().trim()) {
      addRecipeMessage.textContent = "Add at least one ingredient.";
      return;
    }
    renderPreview(buildDraftRecipe());
    showPreviewStep();
  });

  btnBackToEdit.addEventListener("click", () => {
    showEditStep();
  });

  function openRecipeDialog(recipe) {
    addRecipeMessage.textContent = "";
    addRecipeForm.reset();
    showEditStep();
    previewCardContainer.innerHTML = "";

    if (recipe) {
      addRecipeTitle.textContent = "Edit Recipe";
      deleteRecipeBtn.hidden = false;
      recipeIdField.value = recipe.id;
      addRecipeForm.elements["name"].value = recipe.name;
      addRecipeForm.elements["cuisine"].value = recipe.cuisine;
      ingredientsChip.setChips(recipe.ingredients);
      sauceChip.setChips(recipe.sauce || "");
      addRecipeForm.elements["method"].value = recipe.method;
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
      addRecipeTitle.textContent = "Add Recipe";
      deleteRecipeBtn.hidden = true;
      recipeIdField.value = "";
      ingredientsChip.reset();
      sauceChip.reset();
    }

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

  addRecipeForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    // Save Recipe only exists (and is only enabled) inside the preview
    // step, but guard anyway: nothing should ever persist without the
    // user having confirmed a preview first.
    if (recipePreviewStep.hidden) return;

    const formData = new FormData(e.target);
    const otherTags = formData.getAll("other_tags");
    const customTags = (formData.get("other_tags_custom") || "").split(",");
    customTags.forEach((t) => {
      const trimmed = t.trim();
      if (trimmed) otherTags.push(trimmed);
    });

    const payload = {
      name: formData.get("name"),
      cuisine: formData.get("cuisine"),
      effort: formData.get("effort"),
      ingredients: ingredientsChip.getValue(),
      sauce: sauceChip.getValue(),
      method: normalizeMethod(formData.get("method")),
      source_url: formData.get("source_url"),
      meal_types: formData.getAll("meal_types"),
      other_tags: otherTags,
    };

    const recipeId = formData.get("recipe_id");
    const url = recipeId ? "/api/recipes/" + recipeId : "/api/recipes";
    const method = recipeId ? "PUT" : "POST";

    try {
      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const result = await res.json();
      if (!res.ok) throw new Error(result.error || "Could not save recipe.");
      window.location.reload();
    } catch (err) {
      addRecipeMessage.textContent = err.message;
    }
  });

  // ─── SELECTION MODE (for scoped export) ──────────────────────
  // Separate from the Breakfast/Lunch/Dinner/Snack slot pills above —
  // this Set just tracks which recipes are checked for a one-off
  // export, and persists in memory regardless of scrolling or
  // re-filtering (it isn't rebuilt on every render).
  const selectedRecipeIds = new Set();
  const selectionToolbar = document.getElementById("selection-toolbar");
  const selectionCountEl = document.getElementById("selection-count");

  function getFilteredRecipeIds() {
    return Array.from(document.querySelectorAll(".recipe"))
      .filter(recipeMatches)
      .map((article) => Number(article.dataset.id));
  }

  function injectSelectionCheckboxes() {
    document.querySelectorAll(".recipe").forEach((article) => {
      if (article.querySelector(".recipe-select")) return;
      const id = Number(article.dataset.id);
      const label = document.createElement("label");
      label.className = "recipe-select";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "recipe-select__checkbox";
      checkbox.setAttribute("aria-label", "Select " + recipeNameById(id) + " for export");
      checkbox.checked = selectedRecipeIds.has(id);
      checkbox.addEventListener("change", () => {
        if (checkbox.checked) selectedRecipeIds.add(id);
        else selectedRecipeIds.delete(id);
        updateSelectionCount();
      });
      label.appendChild(checkbox);
      article.querySelector(".recipe__top").prepend(label);
    });
  }

  function updateSelectionCount() {
    selectionCountEl.textContent = selectedRecipeIds.size + " selected";
  }

  function enterSelectionMode() {
    injectSelectionCheckboxes();
    document.body.classList.add("selection-mode");
    selectionToolbar.hidden = false;
    updateSelectionCount();
  }

  function exitSelectionMode() {
    document.body.classList.remove("selection-mode");
    selectionToolbar.hidden = true;
  }

  document.getElementById("btn-select-all-shown").addEventListener("click", () => {
    getFilteredRecipeIds().forEach((id) => selectedRecipeIds.add(id));
    document.querySelectorAll(".recipe-select__checkbox").forEach((cb) => {
      const id = Number(cb.closest(".recipe").dataset.id);
      cb.checked = selectedRecipeIds.has(id);
    });
    updateSelectionCount();
  });

  document.getElementById("btn-clear-selection").addEventListener("click", () => {
    selectedRecipeIds.clear();
    document.querySelectorAll(".recipe-select__checkbox").forEach((cb) => (cb.checked = false));
    updateSelectionCount();
  });

  document.getElementById("btn-export-selected").addEventListener("click", () => {
    if (!selectedRecipeIds.size) return;
    exportRecipesByIds([...selectedRecipeIds]);
  });

  document.getElementById("btn-cancel-selection").addEventListener("click", exitSelectionMode);

  // ─── EXPORT ──────────────────────────────────────────────────
  const exportDialog = document.getElementById("export-dialog");
  const exportMessage = document.getElementById("export-message");

  function downloadTextFile(filename, text) {
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  // Reuses the existing /api/recipes/export YAML endpoint for every
  // recipe-list scope (favorites/filtered/selected/all) — ids=null
  // means "no filter", i.e. the original full-export behavior.
  function exportRecipesByIds(ids) {
    if (ids && !ids.length) return;
    window.location.href = ids ? "/api/recipes/export?ids=" + ids.join(",") : "/api/recipes/export";
  }

  async function exportCurrentPlan() {
    const res = await fetch("/api/meal-plans/current");
    const plan = await res.json();
    if (!plan || !plan.items.length) return;

    const slotOrder = ["breakfast", "lunch", "dinner", "snack", "unassigned"];
    const bySlot = {};
    plan.items.forEach((item) => {
      const slot = item.slot || "unassigned";
      (bySlot[slot] = bySlot[slot] || []).push(item.recipe_name);
    });

    const lines = ["Meal Plan: " + plan.name, "Saved: " + new Date(plan.created_at).toLocaleDateString(), ""];
    slotOrder.forEach((slot) => {
      if (!bySlot[slot]) return;
      lines.push((slot === "unassigned" ? "Unassigned" : slot[0].toUpperCase() + slot.slice(1)) + ":");
      bySlot[slot].forEach((name) => lines.push("- " + name));
      lines.push("");
    });
    downloadTextFile("mindless-meals-meal-plan.txt", lines.join("\n"));
  }

  function setExportOption(scope, count, disabled, reason) {
    const input = document.getElementById("export-option-" + scope);
    const meta = document.getElementById("export-meta-" + scope);
    const row = document.getElementById("export-row-" + scope);
    input.disabled = disabled;
    row.dataset.disabled = String(disabled);
    if (disabled && input.checked) input.checked = false;
    meta.textContent = reason || count + (count === 1 ? " recipe" : " recipes");
  }

  async function openExportDialog() {
    exportMessage.textContent = "";
    const totalCount = data.recipes.length;
    const favCount = favoriteIds.size;
    const filteredCount = getFilteredRecipeIds().length;
    const selectedCount = selectedRecipeIds.size;

    setExportOption("all", totalCount, totalCount === 0, totalCount === 0 ? "No recipes yet." : null);
    setExportOption("favorites", favCount, favCount === 0, favCount === 0 ? "No favorites yet." : null);
    setExportOption(
      "filtered",
      filteredCount,
      filteredCount === 0,
      filteredCount === 0 ? "No recipes match the current filters." : null
    );
    // Never disabled: 0 selected is a valid starting point that hands
    // the user into selection mode rather than a dead end.
    setExportOption(
      "selected",
      selectedCount,
      false,
      selectedCount === 0 ? "0 selected — Export will let you choose recipes." : null
    );
    setExportOption("current_plan", 0, true, "Checking for a saved plan…");

    if (!document.querySelector('input[name="export_scope"]:checked')) {
      document.getElementById("export-option-selected").checked = true;
    }

    exportDialog.showModal();

    try {
      const res = await fetch("/api/meal-plans/current");
      const plan = await res.json();
      const n = plan ? plan.items.length : 0;
      setExportOption("current_plan", n, n === 0, n === 0 ? "No saved meal plan yet." : null);
    } catch (err) {
      setExportOption("current_plan", 0, true, "Could not check for a saved plan.");
    }
  }

  document.getElementById("btn-export").addEventListener("click", openExportDialog);

  document.getElementById("btn-export-confirm").addEventListener("click", () => {
    const checked = document.querySelector('input[name="export_scope"]:checked');
    if (!checked) return;
    const scope = checked.value;

    if (scope === "all") {
      exportRecipesByIds(null);
    } else if (scope === "favorites") {
      exportRecipesByIds([...favoriteIds]);
    } else if (scope === "filtered") {
      exportRecipesByIds(getFilteredRecipeIds());
    } else if (scope === "selected") {
      if (selectedRecipeIds.size === 0) {
        exportDialog.close();
        enterSelectionMode();
        return;
      }
      exportRecipesByIds([...selectedRecipeIds]);
    } else if (scope === "current_plan") {
      exportCurrentPlan();
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
