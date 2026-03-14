import React from "react";
import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { uiFontFamily } from "../styles/fonts";

export const ScoutLogo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scaleSpring = spring({ fps, frame, config: { damping: 80 } });
  const scale = interpolate(scaleSpring, [0, 1], [0.6, 1]);
  const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  const fadeOut = interpolate(frame, [45, 60], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{
      backgroundColor: "#1e1e2e",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      opacity: fadeOut,
    }}>
      <Img
        src={staticFile("logo-transparent.png")}
        style={{
          width: 120,
          height: 120,
          opacity,
          transform: `scale(${scale})`,
        }}
      />
      <div style={{
        fontFamily: uiFontFamily,
        fontSize: 32,
        fontWeight: 700,
        color: "#cdd6f4",
        marginTop: 16,
        opacity,
      }}>
        scout-mcp
      </div>
      <div style={{
        fontFamily: uiFontFamily,
        fontSize: 14,
        color: "#6c7086",
        marginTop: 8,
        opacity,
      }}>
        github.com/stemado/scout-mcp
      </div>
    </AbsoluteFill>
  );
};
