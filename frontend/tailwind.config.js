/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))",
        "card-foreground": "hsl(var(--card-foreground))",
        primary: {
          DEFAULT: "#0284c7", // Sky blue (Purple Ban compliant)
          foreground: "#ffffff",
        },
        accent: {
          DEFAULT: "#10b981", // Emerald
          foreground: "#ffffff",
        },
        muted: {
          DEFAULT: "#1e293b",
          foreground: "#94a3b8",
        },
        border: "hsl(var(--border))",
      },
    },
  },
  plugins: [],
};
