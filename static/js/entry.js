/*
 * entry.js
 * Student entry screen (screen 2): initialisation, roll number navigation,
 * file selection and drag-and-drop, OCR processing, Add Student flow,
 * and the reset helper used between students.
 */

/* DOM references captured once to avoid repeated lookups. */
const dropZone  = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');

/* ==========================================================================
   Entry screen initialisation
   ========================================================================== */

/**
 * Initialise (or reinitialise) the entry screen for the current exam setup.
 * Builds the table headers, resets the current-student panel, and seeds the
 * roll number field with the exam's starting roll.
 */
function initEntryScreen() {
  document.getElementById('entryExamTitle').textContent    = setup.examName;
  document.getElementById('rollPrefixDisplay').textContent = setup.rollPrefix + '-';
  document.getElementById('currentRollNum').value          = setup.startingRoll;
  currentRoll = setup.startingRoll;

  buildCurrentMarksTable();
  buildStudentsListHead();
  resetCurrentStudent();
  updateStudentCount();
}

/**
 * Read the full roll string from the roll-prefix display and the number input.
 * @returns {string} e.g. "SE-24001"
 */
function getCurrentRollStr() {
  const num = parseInt(document.getElementById('currentRollNum').value, 10);
  return `${setup.rollPrefix}-${num}`;
}

/* ==========================================================================
   Roll number navigation arrows
   ========================================================================== */

document.getElementById('prevRollBtn').addEventListener('click', () => {
  const inp = document.getElementById('currentRollNum');
  const v   = parseInt(inp.value, 10);
  if (v > 1) inp.value = v - 1;
});

document.getElementById('nextRollBtn').addEventListener('click', () => {
  const inp = document.getElementById('currentRollNum');
  inp.value = parseInt(inp.value, 10) + 1;
});

/* ==========================================================================
   File selection (click, keyboard, drag-and-drop, change)
   ========================================================================== */

dropZone.addEventListener('click',    () => fileInput.click());
dropZone.addEventListener('keypress', e  => { if (e.key === 'Enter') fileInput.click(); });
dropZone.addEventListener('dragover',  e  => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f && f.type.startsWith('image/')) setCurrentFile(f);
  else alert('Please drop an image file.');
});
fileInput.addEventListener('change', e => {
  if (e.target.files[0]) setCurrentFile(e.target.files[0]);
});

/**
 * Store the selected file and update the UI to reflect the selection.
 * Resets any previously extracted marks so the user must re-run OCR.
 * @param {File} f
 */
function setCurrentFile(f) {
  currentFile = f;

  const el = document.getElementById('selectedFilename');
  el.textContent = `📷 ${f.name}  (${(f.size / 1024).toFixed(0)} KB)`;
  el.classList.remove('hidden');

  document.getElementById('dropIcon').textContent  = '✔';
  document.getElementById('dropTitle').textContent = 'Image selected';
  document.getElementById('processBtn').disabled   = false;

  pendingMarks = null;
  document.getElementById('addStudentBtn').disabled = true;
  clearOcrStatus();
}

/* ==========================================================================
   OCR processing
   ========================================================================== */

document.getElementById('processBtn').addEventListener('click', async () => {
  if (!currentFile) return;

  setLoading(true, 'Running OCR...',
    'Detecting orientation, preprocessing, and extracting marks. May take 20-60 seconds.');
  clearOcrStatus();

  const fd = new FormData();
  fd.append('image',  currentFile);
  fd.append('examId', setup.examId || '');

  try {
    const { ok, data } = await apiFetchForm('/api/upload', fd);

    if (!ok || data.error) {
      showOcrStatus('error', 'OCR Error: ' + (data.error || 'Unknown error'));
      return;
    }

    pendingMarks = data.marks;
    populateCurrentMarksRow(pendingMarks);

    const allGood = pendingMarks.every(m => m.confidence >= 70);
    if (allGood) {
      showOcrStatus('success', 'Marks extracted successfully. Review and click "Add Student".');
    } else {
      const lowCount = pendingMarks.filter(m => m.confidence < 70).length;
      showOcrStatus('warn',
        `${lowCount} mark(s) have low OCR confidence (highlighted in yellow). Please verify.`);
    }

    document.getElementById('addStudentBtn').disabled = false;
  } catch (err) {
    showOcrStatus('error', 'Processing failed: ' + err.message);
  } finally {
    setLoading(false);
  }
});

/** Hide and clear the OCR status message strip. */
function clearOcrStatus() {
  const el    = document.getElementById('ocrStatusMsg');
  el.className   = 'ocr-status-msg hidden';
  el.textContent = '';
}

/**
 * Show a coloured status message below the marks table.
 * @param {'success'|'warn'|'error'} type
 * @param {string} msg
 */
function showOcrStatus(type, msg) {
  const el    = document.getElementById('ocrStatusMsg');
  el.className   = `ocr-status-msg ocr-status-${type}`;
  el.textContent = msg;
}

/* ==========================================================================
   Add Student
   ========================================================================== */

document.getElementById('addStudentBtn').addEventListener('click', async () => {
  const rollNo = getCurrentRollStr();

  /* Read current mark values by question number, not by DOM position.
     Inputs are rendered in CLO-grouped order, which may differ from
     setup.questions order, so positional indexing would assign marks
     to the wrong questions. */
  const marks = setup.questions.map(q => {
    const inp = document.querySelector(
      `#currentMarksBody input.mark-input[data-question-no="${q.no}"]`
    );
    return {
      questionNo: q.no,
      clo:        q.clo,
      maxMarks:   q.maxMarks,
      obtained:   parseFloat(inp?.value) || 0,
      confidence: null,
    };
  });

  students.push({ rollNo, marks });
  addStudentToList({ rollNo, marks });
  updateStudentCount();
  document.getElementById('exportBtn').disabled = (students.length === 0);

  /* Save to Supabase in the background; failures are silently ignored. */
  if (setup.examId) {
    try {
      await apiFetch('/api/save_student', {
        method: 'POST',
        body: JSON.stringify({ examId: setup.examId, rollNo, marks }),
      });
    } catch (_) {}
  }

  /* Advance roll number and reset the panel for the next student. */
  const numInp  = document.getElementById('currentRollNum');
  numInp.value  = parseInt(numInp.value, 10) + 1;
  resetCurrentStudent();
});

/* ==========================================================================
   Reset current-student panel
   ========================================================================== */

/**
 * Clear the file selection, OCR results, and marks inputs so the panel is
 * ready for the next student. Does not affect the saved-students list.
 */
function resetCurrentStudent() {
  currentFile  = null;
  pendingMarks = null;
  fileInput.value = '';

  const el = document.getElementById('selectedFilename');
  el.textContent = '';
  el.classList.add('hidden');

  document.getElementById('dropIcon').textContent  = '📷';
  document.getElementById('dropTitle').textContent = 'Drop image here or click to browse';
  document.getElementById('processBtn').disabled   = true;
  document.getElementById('addStudentBtn').disabled = true;

  /* Show zeroed marks so the teacher can enter manually without running OCR. */
  populateCurrentMarksRow(
    setup.questions.map(q => ({
      questionNo: q.no, clo: q.clo, maxMarks: q.maxMarks, obtained: 0, confidence: 100,
    }))
  );
  clearOcrStatus();
}

document.getElementById('clearBtn').addEventListener('click', resetCurrentStudent);
