document.addEventListener('DOMContentLoaded', () => {
  const status = document.querySelector('[data-app-status]');
  if (status) {
    status.textContent = 'Portal ready';
  }
});
