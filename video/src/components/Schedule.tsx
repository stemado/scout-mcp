import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { uiFontFamily } from "../styles/fonts";

const DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];

export const Schedule: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = spring({ fps, frame, config: { damping: 100 } });

  return (
    <div style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "#1e1e2e",
      opacity: fadeIn,
      fontFamily: uiFontFamily,
    }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>&#x23F0;</div>
      <div style={{
        fontSize: 36,
        fontWeight: 700,
        color: "#f9e2af",
        marginBottom: 24,
      }}>
        9:00 AM
      </div>
      <div style={{ fontSize: 14, color: "#6c7086", marginBottom: 16 }}>
        daily-pricing — runs every day
      </div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(7, 48px)",
        gap: 8,
      }}>
        {DAYS.map((d) => (
          <div key={d} style={{
            textAlign: "center",
            fontSize: 12,
            color: "#6c7086",
            fontWeight: 600,
          }}>
            {d}
          </div>
        ))}
        {Array.from({ length: 7 }, (_, i) => {
          const checkDelay = 30 + i * 6;
          const checkProgress = spring({
            fps,
            frame: Math.max(0, frame - checkDelay),
            config: { damping: 80, stiffness: 200 },
          });
          return (
            <div key={i} style={{
              width: 48,
              height: 48,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              backgroundColor: checkProgress > 0.5 ? "#1e3a2f" : "#181825",
              border: `1px solid ${checkProgress > 0.5 ? "#a6e3a1" : "#313244"}`,
              fontSize: 20,
              transform: `scale(${interpolate(checkProgress, [0, 1], [0.5, 1])})`,
            }}>
              {checkProgress > 0.3 && <span style={{ opacity: checkProgress, color: "#a6e3a1" }}>&#x2713;</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
};
