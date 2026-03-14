import { AbsoluteFill } from "remotion";
import { SplitScreen } from "./components/SplitScreen";
import { Terminal } from "./components/Terminal";
import beatsData from "./beats.json";

export const ScoutDemo: React.FC = () => {
  return (
    <AbsoluteFill>
      <SplitScreen
        left={<Terminal beats={beatsData.beats} />}
        right={
          <AbsoluteFill style={{ backgroundColor: "#11111b" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#6c7086" }}>
              Browser panel (coming soon)
            </div>
          </AbsoluteFill>
        }
      />
    </AbsoluteFill>
  );
};
