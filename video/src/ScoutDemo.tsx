import { AbsoluteFill, Sequence } from "remotion";
import { SplitScreen } from "./components/SplitScreen";
import { Terminal } from "./components/Terminal";
import { Browser } from "./components/Browser";
import { WorkflowExport } from "./components/WorkflowExport";
import { Schedule } from "./components/Schedule";
import { ScoutLogo } from "./components/ScoutLogo";
import beatsData from "./beats.json";

/** Beats that render inside browser chrome */
const BROWSER_BEATS = new Set(["launch", "scout", "interact", "captured"]);

export const ScoutDemo: React.FC = () => {
  const beats = beatsData.beats;

  return (
    <AbsoluteFill>
      {/* Beats 1-6: split screen */}
      <Sequence from={0} durationInFrames={840}>
        <SplitScreen
          left={<Terminal beats={beats} />}
          right={
            <AbsoluteFill>
              {/* Browser-wrapped beats (landing through captured pricing) */}
              {beats.filter(b => BROWSER_BEATS.has(b.id)).map((beat) => (
                <Sequence key={beat.id} from={beat.startFrame} durationInFrames={beat.endFrame - beat.startFrame}>
                  <Browser
                    scene={beat.browser.scene as any}
                    shieldState={beat.browser.shieldState as any}
                    animate={beat.id === "launch"}
                  />
                </Sequence>
              ))}

              {/* Export: dark canvas, no browser chrome */}
              {beats.filter(b => b.id === "export").map((beat) => (
                <Sequence key={beat.id} from={beat.startFrame} durationInFrames={beat.endFrame - beat.startFrame}>
                  <AbsoluteFill style={{ backgroundColor: "#11111b" }}>
                    <WorkflowExport />
                  </AbsoluteFill>
                </Sequence>
              ))}

              {/* Schedule: dark canvas, no browser chrome */}
              {beats.filter(b => b.id === "schedule").map((beat) => (
                <Sequence key={beat.id} from={beat.startFrame} durationInFrames={beat.endFrame - beat.startFrame}>
                  <AbsoluteFill style={{ backgroundColor: "#11111b" }}>
                    <Schedule />
                  </AbsoluteFill>
                </Sequence>
              ))}
            </AbsoluteFill>
          }
        />
      </Sequence>

      {/* Outro: full-screen */}
      <Sequence from={840} durationInFrames={60}>
        <ScoutLogo />
      </Sequence>
    </AbsoluteFill>
  );
};
