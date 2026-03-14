import { AbsoluteFill } from "remotion";
import { SplitScreen } from "./components/SplitScreen";

export const ScoutDemo: React.FC = () => {
  return (
    <AbsoluteFill>
      <SplitScreen
        left={
          <AbsoluteFill style={{ backgroundColor: "#1e1e2e" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#cdd6f4" }}>
              Terminal panel
            </div>
          </AbsoluteFill>
        }
        right={
          <AbsoluteFill style={{ backgroundColor: "#11111b" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#6c7086" }}>
              Browser panel
            </div>
          </AbsoluteFill>
        }
      />
    </AbsoluteFill>
  );
};
