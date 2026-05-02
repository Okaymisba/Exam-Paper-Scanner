/*
 * nav.js
 * Screen navigation. Only one screen is visible at a time; goTo() hides all
 * others and optionally updates the step-indicator in the header.
 */

/**
 * Switch the visible screen and (optionally) update the step indicator.
 * @param {string}      screenId - ID of the target <section> element.
 * @param {number|null} [stepNum] - Step number to mark active (1-3), or omit to hide the indicator.
 */
function goTo(screenId, stepNum) {
  document.querySelectorAll('.screen').forEach(s => {
    s.classList.add('hidden');
    s.classList.remove('active');
  });

  const target = document.getElementById(screenId);
  target.classList.remove('hidden');
  target.classList.add('active');

  const stepIndicator = document.getElementById('stepIndicator');
  const showSteps     = stepNum !== undefined && stepNum !== null;
  stepIndicator.style.display = showSteps ? '' : 'none';

  if (showSteps) {
    document.querySelectorAll('.step').forEach(el => {
      const n = +el.dataset.n;
      el.classList.remove('active', 'completed');
      if (n < stepNum)   el.classList.add('completed');
      if (n === stepNum) el.classList.add('active');
    });
  }
}
