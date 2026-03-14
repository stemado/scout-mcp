import React from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { TerminalLine } from "./TerminalLine";
import { terminalFontFamily } from "../styles/fonts";

interface Line {
  text: string;
  color: string;
  framesPerChar?: number;
  delay?: number;
}

interface Beat {
  id: string;
  startFrame: number;
  endFrame: number;
  terminal: { lines: Line[] };
}

interface TerminalProps {
  beats: Beat[];
}

function computeLineStartFrames(beats: Beat[]): Array<{ line: Line; absoluteStart: number }> {
  const result: Array<{ line: Line; absoluteStart: number }> = [];
  let cursor = 0;

  for (const beat of beats) {
    cursor = beat.startFrame;
    for (const line of beat.terminal.lines) {
      const delay = line.delay ?? 0;
      const lineStart = cursor + delay;
      result.push({ line, absoluteStart: lineStart });
      if (line.framesPerChar && line.text.length > 0) {
        cursor = lineStart + line.text.length * line.framesPerChar;
      } else {
        cursor = lineStart + 1;
      }
    }
  }

  return result;
}

export const Terminal: React.FC<TerminalProps> = ({ beats }) => {
  const frame = useCurrentFrame();
  const allLines = React.useMemo(() => computeLineStartFrames(beats), [beats]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#1e1e2e",
        padding: "40px 30px",
        overflow: "hidden",
      }}
    >
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 20,
        paddingBottom: 12,
        borderBottom: "1px solid #313244",
      }}>
        <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: "#f38ba8" }} />
        <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: "#f9e2af" }} />
        <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: "#a6e3a1" }} />
        <span style={{
          fontFamily: terminalFontFamily,
          fontSize: 14,
          color: "#6c7086",
          marginLeft: 12,
        }}>
          claude — scout-mcp
        </span>
      </div>

      <div>
        {allLines.map(({ line, absoluteStart }, i) => (
          <TerminalLine
            key={i}
            text={line.text}
            color={line.color}
            startFrame={absoluteStart}
            framesPerChar={line.framesPerChar}
          />
        ))}
      </div>
    </AbsoluteFill>
  );
};
