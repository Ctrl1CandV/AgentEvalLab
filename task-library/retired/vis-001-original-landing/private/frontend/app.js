// vis-001 reference interaction: signup form empty, error, and success states.
// Visual quality is reviewed by people; automated checks cover structure and contrast.
(function () {
  const form = document.getElementById('signup-form');
  const state = document.getElementById('form-state');
  const MSG = {
    empty: 'Enter a book title, area, and email to continue.',
    error: 'Fix the fields marked in red, then try again.',
    success: 'Your book is listed. We will contact you within two business days.'
  };
  function setState(s) { form.setAttribute('data-state', s); state.textContent = MSG[s]; }
  setState('empty');
  form.addEventListener('submit', function (ev) {
    ev.preventDefault();
    const email = form.querySelector('[name="email"]');
    const title = form.querySelector('[name="title"]');
    const district = form.querySelector('[name="district"]');
    const condition = form.querySelector('[name="condition"]:checked');
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value || '');
    if (!title.value.trim() || !district.value || !emailOk || !condition) {
      setState('error');
      // Trigger native :invalid styling.
      form.querySelectorAll('input,select').forEach(el => { el.setAttribute('data-touched', '1'); });
      return;
    }
    setState('success');
    form.reset();
  });
})();
