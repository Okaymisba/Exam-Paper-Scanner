/*
 * setup.js
 * Setup screen (screen 1): question row rendering, roll number preview,
 * CLO summary, and the form submit handler that creates the exam in the DB.
 */

/* Update the roll preview box when prefix or starting number changes. */
function updateRollPreview() {
  const prefix = document.getElementById('rollPrefix').value.trim().toUpperCase();
  const num    = document.getElementById('startingRoll').value.trim();
  const el     = document.getElementById('rollPreview');
  el.textContent = (prefix && num) ? `${prefix}-${num}` : '--';
}

/**
 * Rebuild the question rows table to match the selected question count.
 * Rows are added or removed at the end to avoid clearing user input.
 */
function renderQuestionRows() {
  const n       = parseInt(document.getElementById('numQuestions').value, 10);
  const section = document.getElementById('questionSection');
  const tbody   = document.getElementById('questionRows');

  if (!n || n < 1) {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');

  /* Remove excess rows from the end. */
  while (tbody.children.length > n) tbody.removeChild(tbody.lastChild);

  /* Append any missing rows. */
  for (let i = tbody.children.length + 1; i <= n; i++) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="q-num">Q${i}</td>
      <td data-label="CLO Number">
        <input type="number" id="qClo${i}" min="1" max="20"
               placeholder="e.g. 1" class="q-input" required
               oninput="refreshCloPreview()"/>
      </td>
      <td data-label="Max Marks">
        <input type="number" id="qMax${i}" min="0.5" max="1000" step="0.5"
               placeholder="e.g. 10" class="q-input" required
               oninput="refreshCloPreview()"/>
      </td>
    `;
    tbody.appendChild(tr);
  }
  refreshCloPreview();
}

/**
 * Compute CLO groups from the current question inputs and display a summary
 * line below the question table so the teacher can verify groupings.
 */
function refreshCloPreview() {
  const n      = parseInt(document.getElementById('numQuestions').value, 10) || 0;
  const groups = {};

  for (let i = 1; i <= n; i++) {
    const clo = parseInt(document.getElementById(`qClo${i}`)?.value, 10);
    const max = parseFloat(document.getElementById(`qMax${i}`)?.value);
    if (clo && max) {
      if (!groups[clo]) groups[clo] = { qs: [], total: 0 };
      groups[clo].qs.push(i);
      groups[clo].total += max;
    }
  }

  const clos = Object.keys(groups).sort((a, b) => +a - +b);
  const prev = document.getElementById('cloPreview');

  if (!clos.length) {
    prev.innerHTML = '';
    return;
  }

  prev.innerHTML = '<strong>CLO Summary:</strong> ' +
    clos.map(c =>
      `CLO ${c}: Q${groups[c].qs.join(', Q')} &nbsp;(total max: ${groups[c].total})`
    ).join(' &nbsp;|&nbsp; ');
}

/* Re-render question rows whenever the question count input changes. */
document.getElementById('numQuestions').addEventListener('input', renderQuestionRows);

/* Setup form submission: validate, save exam to DB, and open the entry screen. */
document.getElementById('setupForm').addEventListener('submit', async e => {
  e.preventDefault();

  const examName      = document.getElementById('examName').value.trim();
  const passThreshold = parseFloat(document.getElementById('passThreshold').value);
  const rollPrefix    = document.getElementById('rollPrefix').value.trim().toUpperCase();
  const startingRoll  = parseInt(document.getElementById('startingRoll').value.trim(), 10);
  const n             = parseInt(document.getElementById('numQuestions').value, 10);

  if (!examName)                         return alert('Please enter the exam name.');
  if (!rollPrefix)                       return alert('Please enter the department code (e.g. SE).');
  if (!startingRoll || isNaN(startingRoll)) return alert('Please enter a valid starting roll number.');
  if (!n)                                return alert('Please enter the number of questions.');

  const questions = [];
  for (let i = 1; i <= n; i++) {
    const clo = parseInt(document.getElementById(`qClo${i}`)?.value, 10);
    const max = parseFloat(document.getElementById(`qMax${i}`)?.value);
    if (!clo || isNaN(clo) || clo < 1) return alert(`Q${i}: please enter a valid CLO number.`);
    if (!max || isNaN(max) || max <= 0) return alert(`Q${i}: please enter valid max marks.`);
    questions.push({ no: i, clo, maxMarks: max });
  }

  setLoading(true, 'Setting up exam...');
  const { ok, data } = await apiFetch('/api/setup', {
    method: 'POST',
    body: JSON.stringify({ examName, rollPrefix, startingRoll, questions, passThreshold }),
  });
  setLoading(false);

  if (!ok) return alert('Setup error: ' + (data.error || 'Unknown'));

  setup = {
    examName, rollPrefix, startingRoll, questions, passThreshold,
    examId:        data.examId,
    questionIdMap: data.questionIdMap || {},
  };

  students     = [];
  currentRoll  = startingRoll;
  currentFile  = null;
  pendingMarks = null;

  initEntryScreen();
  goTo('screenEntry', 2);
});
