/*
 * app.js
 * Application bootstrap and global keyboard shortcuts.
 * Loaded last so that all other modules are available when it runs.
 */

/* Allow pressing Enter in the password fields to submit the respective form. */
document.getElementById('loginPassword').addEventListener('keydown', e => {
  if (e.key === 'Enter') doLogin();
});
document.getElementById('signupPassword').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSignup();
});

/* Validate the stored JWT and route to the appropriate screen on page load. */
restoreSession();
