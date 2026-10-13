// Hubungkan form akun ke session dan CSRF Django tanpa menyimpan password di browser.
(() => {
  const login = document.getElementById('loginForm');
  const register = document.getElementById('registerForm');
  function showPanel(panel) {
    document.getElementById('loginPanel').hidden = panel !== 'login';
    document.getElementById('registerPanel').hidden = panel !== 'register';
    ['loginError', 'registerError', 'loginNotice'].forEach(id => {
      document.getElementById(id).hidden = true;
    });
    history.replaceState(null, '', panel === 'register' ? '#daftar' : '#masuk');
  }
  document.getElementById('showRegister').addEventListener('click', event => {
    event.preventDefault(); showPanel('register');
  });
  document.getElementById('showLogin').addEventListener('click', event => {
    event.preventDefault(); showPanel('login');
  });
  if (location.hash === '#daftar') showPanel('register');

  async function submit(form, errorId, onSuccess) {
    if (!form.reportValidity()) return;
    const button = form.querySelector('button[type="submit"]');
    const error = document.getElementById(errorId);
    button.disabled = true;
    form.setAttribute('aria-busy', 'true');
    error.hidden = true;
    try {
      // Ambil token terbaru, termasuk setelah session berubah pada tab lain.
      const csrfResponse = await fetch(login.dataset.csrfUrl, {credentials: 'same-origin'});
      if (!csrfResponse.ok) throw new Error('Sesi tidak dapat disiapkan. Silakan coba lagi.');
      const {csrf_token: token} = await csrfResponse.json();
      const response = await fetch(form.action, {
        method: 'POST', credentials: 'same-origin',
        headers: {'X-CSRFToken': token}, body: new FormData(form),
      });
      if (!response.headers.get('Content-Type')?.includes('application/json')) {
        throw new Error('Permintaan gagal. Muat ulang halaman lalu coba lagi.');
      }
      const data = await response.json();
      if (!response.ok) {
        const messages = Object.values(data.errors || {}).flat().map(item => item.message || item);
        throw new Error(messages.join(' ') || 'Permintaan gagal. Silakan coba lagi.');
      }
      onSuccess();
    } catch (failure) {
      error.textContent = failure.message || 'Tidak dapat terhubung ke server.';
      error.hidden = false;
    } finally {
      button.disabled = false;
      form.removeAttribute('aria-busy');
    }
  }
  login.addEventListener('submit', event => {
    event.preventDefault();
    submit(login, 'loginError', () => location.assign(login.dataset.redirectUrl));
  });
  register.addEventListener('submit', event => {
    event.preventDefault();
    submit(register, 'registerError', () => {
      document.getElementById('id_email').value = register.elements.email.value;
      register.reset();
      showPanel('login');
      const notice = document.getElementById('loginNotice');
      notice.textContent = 'Akun peserta berhasil dibuat. Silakan masuk.';
      notice.hidden = false;
      document.getElementById('id_password').focus();
    });
  });
})();
