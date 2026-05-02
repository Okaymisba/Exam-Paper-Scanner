/*
 * history.js
 * Exam history screen: listing past exams, opening an existing exam for
 * editing, and starting a fresh exam setup.
 */

/**
 * Fetch the teacher's exam list and render it in the history table.
 * Shows an empty-state card when no exams exist yet.
 */
async function loadHistory() {
  const { ok, data } = await apiFetch('/api/exams');
  if (!ok) return;

  const exams = data.exams || [];
  document.getElementById('historyCountLabel').textContent =
    `${exams.length} exam${exams.length !== 1 ? 's' : ''}`;

  if (exams.length === 0) {
    document.getElementById('historyEmpty').classList.remove('hidden');
    document.getElementById('historyTableCard').style.display = 'none';
    return;
  }

  document.getElementById('historyEmpty').classList.add('hidden');
  document.getElementById('historyTableCard').style.display = '';

  document.getElementById('historyTableBody').innerHTML = exams.map((e, i) => {
    const date = new Date(e.created_at).toLocaleDateString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric',
    });
    return `<tr class="history-row" onclick="loadExam('${esc(e.id)}')" title="Click to open and edit">
      <td>${i + 1}</td>
      <td><strong>${esc(e.name)}</strong></td>
      <td>${esc(e.roll_prefix)}</td>
      <td>${e.pass_threshold}%</td>
      <td>${date}</td>
      <td><span class="open-hint">Open &rsaquo;</span></td>
    </tr>`;
  }).join('');
}

/**
 * Navigate to the history screen and refresh the list.
 */
function goToHistory() {
  goTo('screenHistory');
  loadHistory();
}

/**
 * Fetch a saved exam with all its student results, reconstruct the entry
 * screen state, pre-populate the students table, and open the entry screen.
 * @param {string} examId - UUID of the exam to load.
 */
async function loadExam(examId) {
  setLoading(true, 'Loading exam...');
  const { ok, data } = await apiFetch(`/api/exams/${examId}`);
  setLoading(false);

  if (!ok) {
    alert('Failed to load exam: ' + (data.error || 'Unknown error'));
    return;
  }

  const exam       = data.exam;
  const dbStudents = data.students || [];

  setup = {
    examName:      exam.name,
    rollPrefix:    exam.roll_prefix,
    startingRoll:  exam.starting_roll,
    passThreshold: parseFloat(exam.pass_threshold),
    questions:     exam.questions,
    examId,
    questionIdMap: {},
  };

  students     = [];
  currentFile  = null;
  pendingMarks = null;

  initEntryScreen();

  /* Pre-populate the students list with records already saved in the database. */
  dbStudents.forEach(s => {
    students.push({ rollNo: s.rollNo, marks: s.marks, resultId: s.resultId });
    addStudentToList({ rollNo: s.rollNo, marks: s.marks, resultId: s.resultId });
  });

  updateStudentCount();
  document.getElementById('exportBtn').disabled = (students.length === 0);

  /* Advance the roll input past the last known student so the next entry is pre-filled. */
  if (dbStudents.length > 0) {
    const lastNum = dbStudents.reduce((max, s) => {
      const n = parseInt(s.rollNo.split('-').pop(), 10);
      return n > max ? n : max;
    }, setup.startingRoll - 1);
    document.getElementById('currentRollNum').value = lastNum + 1;
  }

  goTo('screenEntry', 2);
}

/**
 * Reset all exam state and navigate to the setup screen to start a new exam.
 */
function startNewExam() {
  setup    = null;
  students = [];
  document.getElementById('setupForm').reset();
  document.getElementById('questionSection').classList.add('hidden');
  document.getElementById('questionRows').innerHTML    = '';
  document.getElementById('cloPreview').innerHTML      = '';
  document.getElementById('rollPreview').textContent   = '--';
  goTo('screenSetup', 1);
}
