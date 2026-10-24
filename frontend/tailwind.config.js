/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        // One accent (deep blue) + semantic flag colors. No brand colors.
        accent: { DEFAULT: "#1e3a8a", light: "#3b5bdb", soft: "#e8edfa" },
        warn: "#b45309",
        danger: "#b91c1c",
        ok: "#15803d",
      },
      fontFeatureSettings: { tabular: '"tnum"' },
    },
  },
  plugins: [],
};
