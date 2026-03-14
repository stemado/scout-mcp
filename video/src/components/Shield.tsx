import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

type ShieldState = "solid" | "cracking" | "dissolved";

interface ShieldProps {
  state: ShieldState;
  size?: number;
}

export const Shield: React.FC<ShieldProps> = ({ state, size = 40 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const colorProgress = state === "solid" ? 0 : state === "cracking" ? 0.5 : 1;
  const r = Math.round(interpolate(colorProgress, [0, 1], [243, 166]));
  const g = Math.round(interpolate(colorProgress, [0, 1], [139, 227]));
  const b = Math.round(interpolate(colorProgress, [0, 1], [168, 161]));
  const shieldColor = `rgb(${r},${g},${b})`;

  const opacity = state === "dissolved" ? 0.3 : 1;

  const crackProgress = state === "solid" ? 0 : spring({
    fps,
    frame,
    config: { damping: 100, stiffness: 200 },
  });
  const crackLength = size * 1.2;
  const crackDashoffset = interpolate(crackProgress, [0, 1], [crackLength, 0]);

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" style={{ opacity }}>
      <path
        d="M12 2L3 7v5c0 5.25 3.82 10.17 9 11.38C17.18 22.17 21 17.25 21 12V7L12 2z"
        fill={shieldColor}
      />
      {state !== "solid" && (
        <line
          x1="8"
          y1="6"
          x2="16"
          y2="18"
          stroke="#1e1e2e"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeDasharray={crackLength}
          strokeDashoffset={crackDashoffset}
        />
      )}
    </svg>
  );
};
