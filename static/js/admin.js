/*
 * admin.js
 * Admin panel: loading all teacher accounts and approving or rejecting them.
 */

/**
 * Fetch all teacher accounts and render them in the admin table.
 */
async function loadAdminTeachers() {
  document.getElementById('teacherCountLabel').textContent = 'Loading...';
  document.getElementById('adminTableBody').innerHTML =
    '<tr><td colspan="6" class="empty-row">Loading...</td></tr>';

  const { ok, data } = await apiFetch('/api/admin/teachers');
  if (!ok) {
    showAlert('adminError', data.error || 'Failed to load teachers.');
    return;
  }

  const teachers = data.teachers || [];
  const pending  = teachers.filter(t => t.status === 'pending').length;

  document.getElementById('teacherCountLabel').textContent =
    `${teachers.length} teacher${teachers.length !== 1 ? 's' : ''} (${pending} pending)`;

  const tbody = document.getElementById('adminTableBody');

  if (teachers.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty-row">No teachers registered yet.</td></tr>';
    return;
  }

  tbody.innerHTML = teachers.map(t => {
    const requestedDate = t.requested_at
      ? new Date(t.requested_at).toLocaleDateString()
      : '-';

    const statusBadge = `<span class="status-badge status-${t.status}">${t.status}</span>`;

    /* Show context-appropriate action buttons based on current status. */
    const actions = t.status === 'pending'
      ? `<button class="btn btn-success btn-xs" onclick="adminApprove('${t.id}')">Approve</button>
         <button class="btn btn-danger  btn-xs" onclick="adminReject('${t.id}')">Reject</button>`
      : t.status === 'approved'
      ? `<button class="btn btn-danger  btn-xs" onclick="adminReject('${t.id}')">Revoke</button>`
      : `<button class="btn btn-success btn-xs" onclick="adminApprove('${t.id}')">Approve</button>`;

    return `<tr>
      <td>${esc(t.full_name)}</td>
      <td>${esc(t.email)}</td>
      <td>${esc(t.department || '-')}</td>
      <td>${requestedDate}</td>
      <td>${statusBadge}</td>
      <td class="action-cell">${actions}</td>
    </tr>`;
  }).join('');
}

/**
 * Approve a teacher's account request and refresh the table.
 * @param {string} userId - UUID of the teacher_profiles row.
 */
async function adminApprove(userId) {
  clearAlert('adminError');
  setLoading(true, 'Approving...');
  const { ok, data } = await apiFetch('/api/admin/approve', {
    method: 'POST',
    body: JSON.stringify({ userId }),
  });
  setLoading(false);

  if (!ok) {
    showAlert('adminError', data.error || 'Failed to approve.');
    return;
  }
  loadAdminTeachers();
}

/**
 * Reject (or revoke) a teacher's account and refresh the table.
 * @param {string} userId - UUID of the teacher_profiles row.
 */
async function adminReject(userId) {
  clearAlert('adminError');
  setLoading(true, 'Updating...');
  const { ok, data } = await apiFetch('/api/admin/reject', {
    method: 'POST',
    body: JSON.stringify({ userId }),
  });
  setLoading(false);

  if (!ok) {
    showAlert('adminError', data.error || 'Failed to update.');
    return;
  }
  loadAdminTeachers();
}
