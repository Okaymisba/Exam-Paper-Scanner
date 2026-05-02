/*
 * auth.js
 * Authentication logic: tab switching, login, signup, logout, session restore,
 * and routing the user to the correct screen after a successful login.
 */

/**
 * Toggle between the Login and "Request Account" tabs in the auth screen.
 * @param {'login'|'signup'} tab
 */
function switchTab(tab) {
  const isLogin = tab === 'login';
  document.getElementById('formLogin').classList.toggle('hidden', !isLogin);
  document.getElementById('formSignup').classList.toggle('hidden', isLogin);
  document.getElementById('tabLogin').classList.toggle('active', isLogin);
  document.getElementById('tabSignup').classList.toggle('active', !isLogin);
  clearAlert('loginError');
  clearAlert('signupError');
  clearAlert('signupSuccess');
}

/**
 * Submit the login form. On success, stores the JWT and routes to the
 * appropriate screen (admin panel or exam history).
 */
async function doLogin() {
  clearAlert('loginError');
  const email    = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;

  if (!email || !password) {
    showAlert('loginError', 'Please enter your email and password.');
    return;
  }

  setLoading(true, 'Signing in...');
  const { ok, data } = await apiFetch('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
  setLoading(false);

  if (!ok) {
    const msg = data.error || 'Login failed.';
    if (msg.includes('pending')) {
      document.getElementById('headerRight').style.display = 'flex';
      goTo('screenPending');
      return;
    }
    if (msg.includes('not approved')) {
      document.getElementById('headerRight').style.display = 'flex';
      goTo('screenRejected');
      return;
    }
    showAlert('loginError', msg);
    return;
  }

  authToken   = data.access_token;
  currentUser = data.profile;
  localStorage.setItem('obe_token', authToken);
  afterLogin();
}

/**
 * Submit the signup (account request) form. Displays a success message on
 * acceptance; the teacher must wait for admin approval before logging in.
 */
async function doSignup() {
  clearAlert('signupError');
  clearAlert('signupSuccess');

  const fullName   = document.getElementById('signupName').value.trim();
  const email      = document.getElementById('signupEmail').value.trim();
  const password   = document.getElementById('signupPassword').value;
  const department = document.getElementById('signupDept').value.trim();

  if (!fullName || !email || !password) {
    showAlert('signupError', 'Name, email, and password are required.');
    return;
  }

  setLoading(true, 'Submitting request...');
  const { ok, data } = await apiFetch('/api/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ fullName, email, password, department }),
  });
  setLoading(false);

  if (!ok) {
    showAlert('signupError', data.error || 'Signup failed.');
    return;
  }

  showAlert('signupSuccess', data.message || 'Request submitted. Awaiting admin approval.');
  document.getElementById('signupName').value     = '';
  document.getElementById('signupEmail').value    = '';
  document.getElementById('signupPassword').value = '';
  document.getElementById('signupDept').value     = '';
}

/**
 * Sign the user out: clear stored state, remove the JWT, and show the auth screen.
 */
async function logout() {
  authToken   = null;
  currentUser = null;
  setup       = null;
  students    = [];
  localStorage.removeItem('obe_token');
  document.getElementById('headerRight').style.display = 'none';
  goTo('screenAuth');
}

/**
 * Update the header with the logged-in user's details and route to the
 * correct landing screen based on role.
 */
function afterLogin() {
  document.getElementById('headerRight').style.display = 'flex';
  document.getElementById('userName').textContent   = currentUser.full_name || currentUser.email;
  document.getElementById('userAvatar').textContent = (currentUser.full_name || 'T')[0].toUpperCase();

  if (currentUser.role === 'admin') {
    goTo('screenAdmin');
    loadAdminTeachers();
    return;
  }

  goTo('screenHistory');
  loadHistory();
}

/**
 * Validate the stored JWT on page load and restore the previous session if
 * the token is still valid. Redirects to the auth screen if the token is
 * absent or expired.
 */
async function restoreSession() {
  if (!authToken) {
    goTo('screenAuth');
    return;
  }

  setLoading(true, 'Restoring session...');
  const { ok, data } = await apiFetch('/api/auth/me');
  setLoading(false);

  if (!ok) {
    authToken = null;
    localStorage.removeItem('obe_token');
    goTo('screenAuth');
    return;
  }

  currentUser = data.profile;
  document.getElementById('headerRight').style.display = 'flex';
  document.getElementById('userName').textContent   = currentUser.full_name || currentUser.email;
  document.getElementById('userAvatar').textContent = (currentUser.full_name || 'T')[0].toUpperCase();

  if (currentUser.role === 'admin') {
    goTo('screenAdmin');
    loadAdminTeachers();
  } else {
    goTo('screenHistory');
    loadHistory();
  }
}
