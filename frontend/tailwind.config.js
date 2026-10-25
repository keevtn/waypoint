/** @type {import('tailwindcss').Config} */
// Design tokens (design pass, checkpoint 1). The product reads as a financial instrument: warm off-white
// paper, near-black ink, one deep teal accent for the selected option and the primary action, and three
// semantic colors (amber, red, green) that appear only on flags and statuses. Dark mode mirrors it.
//
// `slate` is redefined as the warm ink scale and `white` as the paper tone so the existing utility classes
// (bg-white, text-slate-500, border-slate-200, dark:bg-slate-900 ...) pick the new palette up globally.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    fontFamily: {
      sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "Roboto", "sans-serif"],
      mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
    },
    // 6px is the largest corner anywhere; `full` stays for the few true circles (dots, legend swatches).
    borderRadius: {
      none: "0",
      sm: "3px",
      DEFAULT: "4px",
      md: "6px",
      lg: "6px",
      xl: "6px",
      "2xl": "6px",
      "3xl": "6px",
      full: "9999px",
    },
    // Eight sizes (DESIGN_NOTES.md R1-R3): 1.5 at <= 16px, 1.3-1.4 at 18-32px, 1.08 at >= 44px. Nothing below 12px.
    fontSize: {
      xs: ["12px", { lineHeight: "18px" }],
      sm: ["14px", { lineHeight: "21px" }],
      base: ["15px", { lineHeight: "22px" }],
      lg: ["18px", { lineHeight: "26px" }],
      xl: ["22px", { lineHeight: "28px" }],
      "2xl": ["26px", { lineHeight: "32px" }],
      "3xl": ["32px", { lineHeight: "36px" }],
      "4xl": ["44px", { lineHeight: "48px" }],
      "5xl": ["52px", { lineHeight: "56px" }],
    },
    // No drop shadows: depth comes from 1px borders and background shifts.
    boxShadow: {
      none: "none",
      sm: "none",
      DEFAULT: "none",
      md: "none",
      lg: "none",
      xl: "none",
    },
    extend: {
      colors: {
        white: "#fbfaf7", // paper
        slate: {
          // warm ink scale: 50 is a tint of paper, 950 is the dark-mode page
          50: "#f4f2ed",
          100: "#ebe8e1",
          200: "#dcd8cf",
          300: "#c3beb2",
          400: "#918b80",
          500: "#787369",
          600: "#4d4942",
          700: "#393631",
          800: "#252320",
          900: "#171614",
          950: "#0e0d0c",
        },
        // One accent: deep teal. `light` is the dark-mode counterpart, `soft` a paper tint for selection fills.
        accent: { DEFAULT: "#0e5a57", light: "#3fa39d", soft: "#e3eeec" },
        // Semantic colors, flags and statuses only. Each passes 4.5:1 on paper; dark mode uses the -300 steps.
        warn: "#9a5a00",
        danger: "#b42318",
        ok: "#1a7a3c",
      },
      letterSpacing: { tightest: "-0.02em" },
    },
  },
  plugins: [],
};
