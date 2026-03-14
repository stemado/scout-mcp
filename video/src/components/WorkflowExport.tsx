import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { terminalFontFamily, uiFontFamily } from "../styles/fonts";

const FILES = [
  { name: "login-workflow.py", icon: "\u{1F40D}" },
  { name: "login-workflow.json", icon: "\u{1F4C4}" },
];

const CODE_PREVIEW = `from scout import Workflow

wf = Workflow.load("login-workflow.json")
wf.set_env("EMAIL", "\${EMAIL}")
wf.set_env("PASSWORD", "\${PASSWORD}")
wf.run(headless=True)`;

export const WorkflowExport: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = spring({ fps, frame, config: { damping: 100 } });

  // Files appear one by one, synced to terminal mentions
  // Terminal: "✓ 6 actions recorded" at ~frame 70, then files at ~82 and ~94
  const file1Appear = 75;
  const file2Appear = 90;

  // Code preview fades in after both files are listed
  const codeAppear = 105;
  const codeFade = interpolate(frame - codeAppear, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      padding: 32,
      backgroundColor: "#11111b",
      opacity: fadeIn,
    }}>
      {/* Header */}
      <div style={{
        fontFamily: uiFontFamily,
        fontSize: 16,
        fontWeight: 600,
        color: "#cdd6f4",
        marginBottom: 8,
      }}>
        Exported Workflow
      </div>
      <div style={{
        fontFamily: uiFontFamily,
        fontSize: 13,
        color: "#6c7086",
        marginBottom: 20,
      }}>
        workflows/login/
      </div>

      {/* File tree — files appear sequentially */}
      <div style={{ marginBottom: 24 }}>
        {FILES.map((file, i) => {
          const appearFrame = i === 0 ? file1Appear : file2Appear;
          const fileScale = frame >= appearFrame ? spring({
            fps,
            frame: frame - appearFrame,
            config: { damping: 60, stiffness: 200 },
          }) : 0;
          return (
            <div key={file.name} style={{
              opacity: fileScale,
              transform: `scale(${interpolate(fileScale, [0, 1], [0.8, 1])})`,
              transformOrigin: "left center",
              fontFamily: terminalFontFamily,
              fontSize: 18,
              color: "#a6e3a1",
              padding: "6px 0 6px 16px",
            }}>
              {file.icon} {file.name}
            </div>
          );
        })}
      </div>

      {/* Code preview — appears after files are listed */}
      <div style={{
        flex: 1,
        backgroundColor: "#181825",
        borderRadius: 8,
        border: "1px solid #313244",
        padding: 20,
        overflow: "hidden",
        opacity: codeFade,
      }}>
        <div style={{ fontFamily: uiFontFamily, fontSize: 12, color: "#6c7086", marginBottom: 10 }}>
          login-workflow.py
        </div>
        <pre style={{
          fontFamily: terminalFontFamily,
          fontSize: 15,
          color: "#cdd6f4",
          margin: 0,
          lineHeight: 1.7,
          whiteSpace: "pre-wrap",
        }}>
          {CODE_PREVIEW}
        </pre>
      </div>
    </div>
  );
};
