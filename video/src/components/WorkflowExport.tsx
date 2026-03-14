import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { terminalFontFamily, uiFontFamily } from "../styles/fonts";

const FILES = [
  { name: "login-workflow.py", icon: "\u{1F40D}" },
  { name: "login-workflow.json", icon: "\u{1F4C4}" },
  { name: ".env.example", icon: "\u{1F511}" },
];

const CODE_PREVIEW = `from scout import Workflow

wf = Workflow.load("login-workflow.json")
wf.set_env("EMAIL", "\${EMAIL}")
wf.set_env("PASSWORD", "\${PASSWORD}")
wf.run(headless=True)`;

export const WorkflowExport: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const slideIn = spring({ fps, frame, config: { damping: 80, stiffness: 100 } });
  const translateX = interpolate(slideIn, [0, 1], [400, 0]);

  return (
    <div style={{
      position: "absolute",
      inset: 0,
      display: "flex",
      flexDirection: "column",
      padding: 24,
      transform: `translateX(${translateX}px)`,
      backgroundColor: "#1e1e2e",
    }}>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontFamily: uiFontFamily, fontSize: 14, color: "#6c7086", marginBottom: 12 }}>
          workflows/login/
        </div>
        {FILES.map((file, i) => {
          const fileDelay = i * 15;
          const fileOpacity = interpolate(frame - fileDelay, [10, 20], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div key={file.name} style={{
              opacity: fileOpacity,
              fontFamily: terminalFontFamily,
              fontSize: 16,
              color: "#cdd6f4",
              padding: "4px 0 4px 20px",
            }}>
              {file.icon} {file.name}
            </div>
          );
        })}
      </div>

      <div style={{
        flex: 1,
        backgroundColor: "#181825",
        borderRadius: 8,
        border: "1px solid #313244",
        padding: 16,
        overflow: "hidden",
      }}>
        <div style={{ fontFamily: uiFontFamily, fontSize: 11, color: "#6c7086", marginBottom: 8 }}>
          login-workflow.py
        </div>
        <pre style={{
          fontFamily: terminalFontFamily,
          fontSize: 14,
          color: "#cdd6f4",
          margin: 0,
          lineHeight: 1.6,
          whiteSpace: "pre-wrap",
        }}>
          {CODE_PREVIEW}
        </pre>
      </div>
    </div>
  );
};
