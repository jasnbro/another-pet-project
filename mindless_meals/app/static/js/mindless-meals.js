(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("mindless-meals-data").textContent);
  const favoriteIds = new Set(data.favoriteIds);

  const filters = {
    effort: new Set(),
    type: new Set(),
    cuisine: new Set(),
    other: new Set(),
  };
  let showFavoritesOnly = false;
  // recipeId -> Set of slot values ("breakfast" | "lunch" | "dinner" | "snack")
  const planDraft = new Map();

  const cuisineSections = Array.from(document.querySelectorAll(".cuisine-section"));
  const emptyState = document.getElementById("empty-state");
  const activeFiltersEl = document.getElementById("active-filters");

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
  // The DOM only stores filter-relevant fields as space-separated data
  // attributes; recipeMatchesFilters (filtering.js) is the shared,
  // testable source of truth for the actual matching rules.
  function recipeMatches(article) {
    const recipe = {
      id: Number(article.dataset.id),
      effort: article.dataset.effort,
      cuisine: article.dataset.cuisine,
      meal_types: article.dataset.mealTypes.split(" ").filter(Boolean),
      other_tags: article.dataset.other.split(" ").filter(Boolean),
    };
    return recipeMatchesFilters(recipe, filters, favoriteIds, showFavoritesOnly);
  }

  function applyFilters() {
    let anyVisible = false;
    cuisineSections.forEach((section) => {
      let sectionVisible = false;
      section.querySelectorAll(".recipe").forEach((article) => {
        const visible = recipeMatches(article);
        article.hidden = !visible;
        if (visible) sectionVisible = true;
      });
      section.hidden = !sectionVisible;
      if (sectionVisible) anyVisible = true;
    });
    emptyState.hidden = anyVisible;
  }

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

  // ─── MEAL PLAN DRAFT (slot pills on each recipe) ────────────
  function recipeNameById(id) {
    const article = document.querySelector('.recipe[data-id="' + id + '"]');
    return article ? article.querySelector(".recipe__name").textContent : "Recipe";
  }

  document.querySelectorAll(".slot-pill--applicable").forEach((pill) => {
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

  function renderPlanList() {
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

  // ─── ADD RECIPE DIALOG ───────────────────────────────────────
  const addRecipeDialog = document.getElementById("add-recipe-dialog");
  const addRecipeMessage = document.getElementById("add-recipe-message");

  document.getElementById("btn-add-recipe").addEventListener("click", () => {
    addRecipeMessage.textContent = "";
    addRecipeDialog.showModal();
  });

  document.getElementById("add-recipe-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const otherTags = formData.getAll("other_tags");
    const customTag = (formData.get("other_tags_custom") || "").trim();
    if (customTag) otherTags.push(customTag);

    const payload = {
      name: formData.get("name"),
      cuisine: formData.get("cuisine"),
      effort: formData.get("effort"),
      ingredients: formData.get("ingredients"),
      sauce: formData.get("sauce"),
      method: formData.get("method"),
      meal_types: formData.getAll("meal_types"),
      other_tags: otherTags,
    };

    try {
      const res = await fetch("/api/recipes", {
        method: "POST",
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

  // ─── DIALOG DISMISSAL ────────────────────────────────────────
  document.querySelectorAll("[data-close-dialog]").forEach((btn) => {
    btn.addEventListener("click", () => btn.closest("dialog").close());
  });
  [addRecipeDialog, mealPlanDialog].forEach((dialog) => {
    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) dialog.close();
    });
  });
})();
