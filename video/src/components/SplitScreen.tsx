import React from "react";
import { AbsoluteFill } from "remotion";

interface SplitScreenProps {
  splitRatio?: number;
  left: React.ReactNode;
  right: React.ReactNode;
}

export const SplitScreen: React.FC<SplitScreenProps> = ({
  splitRatio = 0.5,
  left,
  right,
}) => {
  const leftWidth = `${splitRatio * 100}%`;
  const rightWidth = `${(1 - splitRatio) * 100}%`;

  return (
    <AbsoluteFill style={{ display: "flex", flexDirection: "row" }}>
      <div style={{ width: leftWidth, height: "100%", position: "relative", overflow: "hidden" }}>
        {left}
      </div>
      <div style={{ width: 2, backgroundColor: "#313244", flexShrink: 0 }} />
      <div style={{ width: rightWidth, height: "100%", position: "relative", overflow: "hidden" }}>
        {right}
      </div>
    </AbsoluteFill>
  );
};
