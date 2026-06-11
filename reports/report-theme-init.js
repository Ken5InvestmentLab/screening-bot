(() => {
  const STORAGE_KEY = "megaReportTheme:v1";
  const COOKIE_MAX_AGE = 60 * 60 * 24 * 365;

  const readCookie = (name) => {
    const prefix = `${name}=`;
    const match = document.cookie
      .split(";")
      .map((part) => part.trim())
      .find((part) => part.startsWith(prefix));
    return match ? decodeURIComponent(match.slice(prefix.length)) : "";
  };

  const writeCookie = (name, value) => {
    document.cookie = `${name}=${encodeURIComponent(value)}; Max-Age=${COOKIE_MAX_AGE}; Path=/; SameSite=Lax`;
  };

  const readTheme = () => {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY);
      if (value === "dark" || value === "light") return value;
    } catch (_error) {
      // Fall back to the cookie mirror below.
    }
    const cookieValue = readCookie(STORAGE_KEY);
    return cookieValue === "dark" || cookieValue === "light" ? cookieValue : "light";
  };

  const theme = readTheme();
  try {
    window.localStorage.setItem(STORAGE_KEY, theme);
  } catch (_error) {
    // The cookie mirror still preserves the preference.
  }
  writeCookie(STORAGE_KEY, theme);
  try {
    if (theme === "dark") {
      document.documentElement.dataset.theme = "dark";
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  } catch (_error) {
    document.documentElement.removeAttribute("data-theme");
  }
})();
