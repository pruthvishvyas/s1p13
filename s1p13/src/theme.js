// Runs before React mounts: prevents a flash of the wrong theme.
(function () {
  try {
    const saved = localStorage.getItem('theme');
    const preferred = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', saved || preferred);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();
