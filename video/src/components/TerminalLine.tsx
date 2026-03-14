import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { terminalFontFamily } from "../styles/fonts";

const COLOR_MAP: Record<string, string> = {
  command: "#a6e3a1",   // green — tool calls
  success: "#a6e3a1",   // green — checkmarks
  default: "#cdd6f4",   // light gray — output
  muted: "#6c7086",     // dim — progress text
  value: "#f9e2af",     // yellow — values
  user: "#89b4fa",      // blue — human prompts
  data: "#f9e2af",      // yellow — captured data
};

interface TerminalLineProps {
  text: string;
  color: string;
  startFrame: number;
  framesPerChar?: number;
}

export const TerminalLine: React.FC<TerminalLineProps> = ({
  text,
  color,
  startFrame,
  framesPerChar,
}) => {
  const frame = useCurrentFrame();
  const elapsed = frame - startFrame;

  if (elapsed < 0) return null;
  if (text === "") return <div style={{ height: 8 }} />;

  const textColor = COLOR_MAP[color] ?? COLOR_MAP.default;

  if (!framesPerChar) {
    return (
      <div style={{ fontFamily: terminalFontFamily, fontSize: 22, color: textColor, lineHeight: 1.6, whiteSpace: "pre" }}>
        {text}
      </div>
    );
  }

  const totalFrames = text.length * framesPerChar;
  const progress = interpolate(elapsed, [0, totalFrames], [0, text.length], {
    extrapolateRight: "clamp",
  });
  const visibleChars = Math.floor(progress);
  const displayText = text.slice(0, visibleChars);
  const showCursor = visibleChars < text.length && Math.floor(frame / 15) % 2 === 0;

  return (
    <div style={{ fontFamily: terminalFontFamily, fontSize: 22, color: textColor, lineHeight: 1.6, whiteSpace: "pre" }}>
      {displayText}
      {showCursor && <span style={{ opacity: 0.8 }}>{"\u258C"}</span>}
    </div>
  );
};
