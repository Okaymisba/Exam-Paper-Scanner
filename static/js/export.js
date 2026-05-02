/*
 * export.js
 * Handles the Excel export button. Sends all students and the exam setup to
 * the /api/export endpoint, triggers a browser download, and navigates to
 * the success screen.
 */

document.getElementById('exportBtn').addEventListener('click', async () => {
  if (!students.length) {
    alert('No students added yet.');
    return;
  }

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

    const res = await fetch('/api/export', {
      method:  'POST',
      headers,
      body:    JSON.stringify({ students, setup }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      alert('Export failed: ' + (err.error || res.statusText));
      return;
    }

    /* Trigger a file download without leaving the page. */
    const blob     = await res.blob();
    const url      = URL.createObjectURL(blob);
    const anchor   = document.createElement('a');
    anchor.href    = url;
    anchor.download = `${(setup.examName || 'Exam').replace(/\s+/g, '_')}_Marks_`
                    + `${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);

    goTo('screenDone', 3);
  } catch (err) {
    alert('Export error: ' + err.message);
  }
});
