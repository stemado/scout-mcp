import { AbsoluteFill, Sequence } from "remotion";
import { SplitScreen } from "./components/SplitScreen";
import { Terminal } from "./components/Terminal";
import { Browser } from "./components/Browser";
import { WorkflowExport } from "./components/WorkflowExport";
import { Schedule } from "./components/Schedule";
import { ScoutLogo } from "./components/ScoutLogo";
import beatsData from "./beats.json";

export const ScoutDemo: React.FC = () => {
  const beats = beatsData.beats;

  return (
    <AbsoluteFill>
      {/* Beats 1-5: split screen */}
      <Sequence from={0} durationInFrames={840}>
        <SplitScreen
          left={<Terminal beats={beats} />}
          right={
            <AbsoluteFill>
              {beats.filter(b => b.id !== "outro").map((beat) => (
                <Sequence key={beat.id} from={beat.startFrame} durationInFrames={beat.endFrame - beat.startFrame}>
                  <Browser scene={beat.browser.scene as any} shieldState={beat.browser.shieldState as any} animate={beat.id === "launch"}>
                    {beat.id === "export" && <WorkflowExport />}
                    {beat.id === "schedule" && <Schedule />}
                  </Browser>
                </Sequence>
              ))}
            </AbsoluteFill>
          }
        />
      </Sequence>

      {/* Beat 6: full-screen outro */}
      <Sequence from={840} durationInFrames={60}>
        <ScoutLogo />
      </Sequence>
    </AbsoluteFill>
  );
};
