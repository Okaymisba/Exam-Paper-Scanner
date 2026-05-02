/*
 * state.js
 * Shared application state. All variables are declared at module scope so
 * every other script that is loaded after this one can read and write them.
 * Load this file first, before any other JS module.
 */

/* JWT returned by Supabase Auth on login; persisted in localStorage. */
let authToken = localStorage.getItem('obe_token') || null;

/* Profile object returned by /api/auth/me: { id, full_name, email, role, status } */
let currentUser = null;

/*
 * Active exam configuration.
 * Shape: { examName, rollPrefix, startingRoll, questions, passThreshold,
 *           examId, questionIdMap }
 */
let setup = null;

/* Numeric part of the roll number currently displayed in the entry panel. */
let currentRoll = 0;

/* Array of student objects added in this session: { rollNo, marks, resultId? } */
let students = [];

/* Marks returned by the last OCR call, awaiting confirmation. */
let pendingMarks = null;

/* The File object selected in the drop zone (not yet processed). */
let currentFile = null;
