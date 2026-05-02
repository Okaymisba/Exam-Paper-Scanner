/*
 * students-list.js
 * Manages the saved-students table below the entry panel: building the header,
 * appending rows, and keeping the student count labels in sync.
 */

/**
 * Render the two-row header for the saved-students table.
 * Must be called after setup is initialised (getCloGroups depends on setup.questions).
 */
function buildStudentsListHead() {
  const cloGroups = getCloGroups();
  const head      = document.getElementById('studentsHead');

  let r1 = '<tr>'
    + '<th rowspan="2" class="th-fixed">#</th>'
    + '<th rowspan="2" class="th-fixed">Roll No</th>';

  cloGroups.forEach(g => {
    r1 += `<th colspan="${g.questions.length}" class="th-clo-group">CLO ${g.cloNo} <small>(/${g.totalMax})</small></th>`;
  });
  cloGroups.forEach(g => {
    r1 += `<th rowspan="2" class="th-subtot">CLO${g.cloNo}<br/>Total</th>`;
  });
  r1 += '<th rowspan="2" class="th-grand">Total</th>'
     +  '<th rowspan="2" class="th-pct">%</th>'
     +  '<th rowspan="2" class="th-result">Result</th>'
     +  '<th rowspan="2"></th></tr>';

  let r2 = '<tr>';
  cloGroups.forEach(g => {
    g.questions.forEach(q => {
      r2 += `<th class="th-q">Q${q.no}<br/><small>/${q.maxMarks}</small></th>`;
    });
  });
  r2 += '</tr>';

  head.innerHTML = r1 + r2;
}

/**
 * Append a single student row to the saved-students table.
 * The delete button removes the row locally and, if the student was loaded
 * from the database (has a resultId), also calls the delete API.
 * @param {{ rollNo: string, marks: object[], resultId?: string }} student
 */
function addStudentToList(student) {
  const tbody    = document.getElementById('studentsBody');
  const cloGroups = getCloGroups();
  const totalMax  = setup.questions.reduce((s, q) => s + q.maxMarks, 0);
  const rowNum    = students.length;

  document.getElementById('studentsListScroll').style.display = '';

  const tr = document.createElement('tr');

  /* Row number */
  const tdNum = document.createElement('td');
  tdNum.textContent = rowNum;
  tr.appendChild(tdNum);

  /* Roll number */
  const tdRoll = document.createElement('td');
  tdRoll.textContent = student.rollNo;
  tr.appendChild(tdRoll);

  /* Individual question marks */
  let grand = 0;
  cloGroups.forEach(g => {
    g.questions.forEach(q => {
      const m  = student.marks.find(mk => mk.questionNo === q.no) ?? { obtained: 0 };
      const td = document.createElement('td');
      td.textContent = fmt(m.obtained);
      grand += m.obtained;
      tr.appendChild(td);
    });
  });

  /* CLO subtotal cells */
  cloGroups.forEach(g => {
    const cloTot = g.questions.reduce((s, q) => {
      const m = student.marks.find(mk => mk.questionNo === q.no) ?? { obtained: 0 };
      return s + m.obtained;
    }, 0);
    const td = document.createElement('td');
    td.className   = 'col-computed';
    td.textContent = fmt(cloTot);
    tr.appendChild(td);
  });

  /* Grand total, percentage, result */
  const pct    = totalMax > 0 ? grand / totalMax * 100 : 0;
  const result = pct >= setup.passThreshold ? 'Pass' : 'Fail';

  const tdGrand = document.createElement('td');
  tdGrand.className   = 'col-computed';
  tdGrand.textContent = fmt(grand);
  tr.appendChild(tdGrand);

  const tdPct = document.createElement('td');
  tdPct.className   = 'col-computed';
  tdPct.textContent = pct.toFixed(1) + '%';
  tr.appendChild(tdPct);

  const tdRes = document.createElement('td');
  tdRes.className   = 'col-computed col-result ' + (result === 'Pass' ? 'result-pass' : 'result-fail');
  tdRes.textContent = result;
  tr.appendChild(tdRes);

  /* Delete button */
  const tdDel = document.createElement('td');
  const btn   = document.createElement('button');
  btn.className   = 'btn btn-danger btn-xs';
  btn.textContent = 'x';
  btn.onclick     = async () => {
    /* Remove from the database if this student was loaded from a saved result. */
    if (student.resultId && setup.examId) {
      await apiFetch(`/api/exams/${setup.examId}/students/${student.resultId}`, { method: 'DELETE' });
    }
    const idx = students.indexOf(student);
    if (idx > -1) students.splice(idx, 1);
    tr.remove();

    /* Re-number remaining rows */
    [...document.querySelectorAll('#studentsBody tr')].forEach((row, i) => {
      row.cells[0].textContent = i + 1;
    });

    updateStudentCount();
    document.getElementById('exportBtn').disabled = (students.length === 0);
    if (students.length === 0) document.getElementById('studentsListScroll').style.display = 'none';
  };
  tdDel.appendChild(btn);
  tr.appendChild(tdDel);

  tr.classList.add(result === 'Pass' ? 'row-pass' : 'row-fail');
  tbody.appendChild(tr);
}

/**
 * Refresh the student count labels in the entry topbar and the list card header.
 */
function updateStudentCount() {
  const n  = students.length;
  const el = document.getElementById('entryStudentCount');
  el.textContent = `${n} student${n !== 1 ? 's' : ''} added`;
  el.className   = 'entry-count-pill' + (n > 0 ? ' count-has-data' : '');
  document.getElementById('studentListSub').textContent = n > 0
    ? `${n} student${n !== 1 ? 's' : ''} recorded`
    : 'None yet';
}
