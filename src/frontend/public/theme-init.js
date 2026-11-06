(function () {
  var p = null
  try {
    p = localStorage.getItem('coffer.theme')
  } catch (e) {}
  var dark = true
  try {
    dark = typeof window.matchMedia !== 'function' || window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch (e) {}
  var t = p === 'light' || p === 'dark' ? p : dark ? 'dark' : 'light'
  document.documentElement.dataset.theme = t
  document.documentElement.style.colorScheme = t
  var m = document.querySelector('meta[name="theme-color"]')
  if (m) m.setAttribute('content', t === 'dark' ? '#15171c' : '#faf7f0')
})()
