/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        radar: {
          50: "#eef4ff",
          100: "#d9e5ff",
          200: "#bcd2ff",
          300: "#8eb4ff",
          400: "#598bff",
          500: "#3362ff",
          600: "#1c3df5",
          700: "#152ee1",
          800: "#1728b6",
          900: "#19288f",
          950: "#141a57",
        },
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5dae3",
          300: "#b1bac9",
          400: "#8695ac",
          500: "#677793",
          600: "#52607a",
          700: "#444e63",
          800: "#3a4252",
          900: "#343946",
          950: "#12141b",
        },
      },
      animation: {
        "pulse-ring": "pulse-ring 1.6s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "flow-dash": "flow-dash 1s linear infinite",
        "slide-up": "slide-up 0.25s ease-out",
        "fade-in": "fade-in 0.3s ease-out",
      },
      keyframes: {
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.7" },
          "70%": { transform: "scale(1.6)", opacity: "0" },
          "100%": { transform: "scale(1.6)", opacity: "0" },
        },
        "flow-dash": {
          to: { strokeDashoffset: "-24" },
        },
        "slide-up": {
          from: { transform: "translateY(6px)", opacity: "0" },
          to: { transform: "translateY(0)", opacity: "1" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
      },
    },
  },
  plugins: [],
}
