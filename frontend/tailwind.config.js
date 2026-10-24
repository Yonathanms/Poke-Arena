/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        arena: {
          bg: "#0B0F19",
          card: "#151C2C",
          surface: "#1E2738",
          border: "#2A364F",
          accent: "#3B82F6",
        },
        type: {
          FUE: "#EF4444",
          AGU: "#3B82F6",
          PLA: "#10B981",
          ELE: "#F59E0B",
          PSI: "#8B5CF6",
          LUC: "#D97706",
          INC: "#9CA3AF",
        },
      },
      fontFamily: {
        sans: ["Outfit", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
