import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        void: "#07090a",
        panel: "#0e1310",
        "panel-raised": "#141b16",
        line: "rgba(178, 196, 178, 0.12)",
        "line-bright": "rgba(178, 196, 178, 0.28)",
        bone: "#e6e9e0",
        dim: "#7c8a7c",
        amber: {
          DEFAULT: "#ffb000",
          dim: "#8a6300",
          glow: "#ffcf5c",
        },
        alert: {
          DEFAULT: "#ff3b3b",
          dim: "#7a1f1f",
        },
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      backgroundImage: {
        "grid-fine":
          "linear-gradient(rgba(178,196,178,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(178,196,178,0.06) 1px, transparent 1px)",
      },
      backgroundSize: {
        "grid-fine": "28px 28px",
      },
      keyframes: {
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        flicker: {
          "0%, 100%": { opacity: "1" },
          "92%": { opacity: "1" },
          "93%": { opacity: "0.82" },
          "94%": { opacity: "1" },
          "96%": { opacity: "0.9" },
          "97%": { opacity: "1" },
        },
        blink: {
          "0%, 49%": { opacity: "1" },
          "50%, 100%": { opacity: "0" },
        },
        "pulse-ring": {
          "0%": { transform: "scale(0.9)", opacity: "0.8" },
          "80%": { transform: "scale(1.4)", opacity: "0" },
          "100%": { transform: "scale(1.4)", opacity: "0" },
        },
        marquee: {
          "0%": { transform: "translateX(0%)" },
          "100%": { transform: "translateX(-50%)" },
        },
      },
      animation: {
        scan: "scan 2.4s linear infinite",
        flicker: "flicker 6s linear infinite",
        blink: "blink 1.1s steps(1) infinite",
        "pulse-ring": "pulse-ring 1.8s cubic-bezier(0.2,0.6,0.4,1) infinite",
        marquee: "marquee 22s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
