// Find the skill choices and builder controls.
const builder = document.getElementById("builder");
const checkboxes = Array.from(
  builder.querySelectorAll('input[name="skills"]')
);
const skillCount = document.getElementById("skill-count");
const buildButton = document.getElementById("build-button");
const resetButton = document.getElementById("reset-builder");
const scientistResult = document.getElementById("scientist-result");

// Return the selected skill checkboxes.
function getSelectedSkills() {
  return checkboxes.filter(checkbox => checkbox.checked);
}

// Update the counter, buttons and selected card appearance.
function updateBuilder(message = "") {
  const selected = getSelectedSkills();
  const ready = selected.length >= 3 && selected.length <= 4;

  skillCount.textContent = message ||
    `${selected.length} of 4 selected. ${ready
      ? "Ready to build."
      : "Choose three or four skills."}`;

  buildButton.disabled = !ready;
  resetButton.disabled = selected.length === 0;

  checkboxes.forEach(checkbox => {
    checkbox.closest(".skill-card").classList.toggle(
      "is-selected",
      checkbox.checked
    );
  });
}

// Respond to skill selections, allowing no more than four.
checkboxes.forEach(checkbox => {
  checkbox.addEventListener("change", () => {
    if (checkbox.checked && getSelectedSkills().length > 4) {
      checkbox.checked = false;
      updateBuilder("Four skills selected. Remove one to choose another.");
      return;
    }

    // Hide the previous reveal when the combination changes.
    scientistResult.hidden = true;
    updateBuilder();
  });
});

// Reveal only the photograph and name.
buildButton.addEventListener("click", () => {
  const selected = getSelectedSkills();

  if (selected.length < 3 || selected.length > 4) return;

  scientistResult.hidden = false;
  scientistResult.focus();
});

// Clear the selection and hide the reveal.
resetButton.addEventListener("click", () => {
  checkboxes.forEach(checkbox => {
    checkbox.checked = false;
  });

  scientistResult.hidden = true;
  updateBuilder();
  checkboxes[0].focus();
});

// Keep restored selections within the four-skill limit.
getSelectedSkills().slice(4).forEach(checkbox => {
  checkbox.checked = false;
});
updateBuilder();