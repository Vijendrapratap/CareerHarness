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
        wash: "#e7edf4",
        ink: "#243044",
        muted: "#5c6b7d",
        accent: "#3d6b8c",
      },
    },
  },
  plugins: [],
};
