import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Shield } from "./Shield";
import { BrowserPage } from "./BrowserPage";
import { uiFontFamily } from "../styles/fonts";

type ShieldState = "solid" | "cracking" | "dissolved";
type Scene = "landing" | "page-loaded" | "form-fill" | "export" | "schedule" | "outro";

interface BrowserProps {
  scene: Scene;
  shieldState: ShieldState;
  children?: React.ReactNode;
}

export const Browser: React.FC<BrowserProps> = ({ scene, shieldState, children }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const enterScale = spring({ fps, frame, config: { damping: 100 } });
  const scale = 0.8 + 0.2 * enterScale;

  return (
    <AbsoluteFill style={{ backgroundColor: "#11111b", padding: 20 }}>
      <div style={{
        transform: `scale(${scale})`,
        transformOrigin: "center center",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        borderRadius: 12,
        overflow: "hidden",
        border: "1px solid #313244",
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 16px",
          backgroundColor: "#2b2b3d",
        }}>
          <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: "#f38ba8" }} />
          <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: "#f9e2af" }} />
          <div style={{ width: 12, height: 12, borderRadius: "50%", backgroundColor: "#a6e3a1" }} />
          <div style={{
            flex: 1,
            marginLeft: 12,
            padding: "4px 12px",
            backgroundColor: "#181825",
            borderRadius: 6,
            fontFamily: uiFontFamily,
            fontSize: 13,
            color: "#6c7086",
          }}>
            https://██████████.com
          </div>
        </div>

        {scene !== "outro" && (
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "12px 20px",
            backgroundColor: "#1e1e2e",
            borderBottom: "1px solid #313244",
          }}>
            <Shield state={shieldState} size={28} />
            <span style={{
              fontFamily: uiFontFamily,
              fontSize: 16,
              fontWeight: 700,
              color: shieldState === "dissolved" ? "#a6e3a1" : "#fab387",
            }}>
              BOT PROTECTED SITE
            </span>
            {shieldState === "dissolved" && (
              <span style={{ fontFamily: uiFontFamily, fontSize: 12, color: "#a6e3a1", marginLeft: "auto" }}>
                Access Granted
              </span>
            )}
          </div>
        )}

        <div style={{ flex: 1, backgroundColor: "#1e1e2e", position: "relative" }}>
          <BrowserPage scene={scene} />
          {children}
        </div>
      </div>
    </AbsoluteFill>
  );
};
