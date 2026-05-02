/*
 * marks-table.js
 * Builds and recomputes the current-student marks table in the entry screen.
 * The table has two header rows: CLO group spans on top, individual question
 * columns below, followed by CLO subtotals, grand total, percentage, and result.
 */

/**
 * Derive CLO groups from the active exam setup. Each group contains all
 * questions that share the same CLO number, plus their combined max marks.
 * @returns {Array<{ cloNo: number, questions: object[], totalMax: number }>}
 */
function getCloGroups() {
  const groups = {};
  setup.questions.forEach(q => {
    if (!groups[q.clo]) groups[q.clo] = [];
    groups[q.clo].push(q);
  });
  return Object.keys(groups)
    .sort((a, b) => +a - +b)
    .map(c => ({
      cloNo:     +c,
      questions: groups[c],
      totalMax:  groups[c].reduce((s, q) => s + q.maxMarks, 0),
    }));
}

/**
 * Render the two-row header and set up the empty body row for the
 * current-student marks table. Call once when entering the entry screen.
 */
function buildCurrentMarksTable() {
  const cloGroups = getCloGroups();
  const head      = document.getElementById('currentMarksHead');

  /* Row 1: CLO group spans + subtotal / total / pct / result headings */
  let r1 = '<tr>';
  cloGroups.forEach(g => {
    r1 += `<th colspan="${g.questions.length}" class="th-clo-group">CLO ${g.cloNo} <small>(max ${g.totalMax})</small></th>`;
  });
  cloGroups.forEach(g => {
    r1 += `<th class="th-subtot">CLO${g.cloNo}<br/>Total</th>`;
  });
  r1 += '<th class="th-grand">Total</th><th class="th-pct">%</th><th class="th-result">Result</th></tr>';

  /* Row 2: individual question columns */
  let r2 = '<tr>';
  cloGroups.forEach(g => {
    g.questions.forEach(q => {
      r2 += `<th class="th-q">Q${q.no}<br/><small>/${q.maxMarks}</small></th>`;
    });
  });
  cloGroups.forEach(() => r2 += '<th></th>');
  r2 += '<th></th><th></th><th></th></tr>';

  head.innerHTML = r1 + r2;
  document.getElementById('currentMarksBody').innerHTML = '<tr id="currentMarksRow"></tr>';
}

/**
 * Fill the current-student row with editable inputs pre-populated from
 * the provided marks array. Any input change triggers a live recompute.
 * @param {Array<{ questionNo: number, obtained: number, confidence: number }>} marks
 */
function populateCurrentMarksRow(marks) {
  const cloGroups = getCloGroups();
  const tr        = document.getElementById('currentMarksRow');
  tr.innerHTML    = '';

  cloGroups.forEach(g => {
    g.questions.forEach(q => {
      const m    = marks.find(mk => mk.questionNo === q.no) ?? { obtained: 0, confidence: 100 };
      const td   = document.createElement('td');
      const conf = m.confidence ?? 100;
      if (conf < 80) td.classList.add('low-conf');

      const inp       = document.createElement('input');
      inp.type        = 'number';
      inp.min         = 0;
      inp.max         = q.maxMarks;
      inp.step        = 0.5;
      inp.value       = m.obtained ?? 0;
      inp.className   = 'cell-input mark-input';
      inp.dataset.max = q.maxMarks;
      inp.addEventListener('input', () => {
        /* Clamp to valid range. */
        const v = parseFloat(inp.value);
        if (!isNaN(v) && v > q.maxMarks) inp.value = q.maxMarks;
        if (!isNaN(v) && v < 0)          inp.value = 0;
        recomputeCurrentRow();
        /* Allow manual entry to enable the Add Student button. */
        document.getElementById('addStudentBtn').disabled = false;
      });

      td.appendChild(inp);
      tr.appendChild(td);
    });
  });

  /* CLO subtotal cells (computed, not editable). */
  cloGroups.forEach(g => {
    const td = document.createElement('td');
    td.className   = 'col-computed col-clo-tot';
    td.dataset.clo = g.cloNo;
    tr.appendChild(td);
  });

  /* Grand total, percentage, result cells. */
  ['col-computed col-grand', 'col-computed col-pct', 'col-computed col-result'].forEach(cls => {
    const td      = document.createElement('td');
    td.className  = cls;
    tr.appendChild(td);
  });

  recomputeCurrentRow();
}

/**
 * Recalculate CLO subtotals, grand total, percentage, and pass/fail result
 * from the current input values and write them into the computed cells.
 */
function recomputeCurrentRow() {
  const cloGroups = getCloGroups();
  const tr        = document.getElementById('currentMarksRow');
  if (!tr) return;

  const totalMax = setup.questions.reduce((s, q) => s + q.maxMarks, 0);
  const inputs   = [...tr.querySelectorAll('.mark-input')];
  let grand = 0;
  let mIdx  = 0;

  cloGroups.forEach(g => {
    let cloTot = 0;
    g.questions.forEach(() => {
      const v = parseFloat(inputs[mIdx]?.value) || 0;
      cloTot += v;
      grand  += v;
      mIdx++;
    });
    const cell = tr.querySelector(`.col-clo-tot[data-clo="${g.cloNo}"]`);
    if (cell) cell.textContent = fmt(cloTot);
  });

  const pct    = totalMax > 0 ? grand / totalMax * 100 : 0;
  const result = pct >= setup.passThreshold ? 'Pass' : 'Fail';

  const gc = tr.querySelector('.col-grand');
  const pc = tr.querySelector('.col-pct');
  const rc = tr.querySelector('.col-result');
  if (gc) gc.textContent = fmt(grand);
  if (pc) pc.textContent = pct.toFixed(1) + '%';
  if (rc) {
    rc.textContent = result;
    rc.className   = 'col-computed col-result ' + (result === 'Pass' ? 'result-pass' : 'result-fail');
  }
}
