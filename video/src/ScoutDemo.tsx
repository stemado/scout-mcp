import { AbsoluteFill, Sequence } from "remotion";
import { SplitScreen } from "./components/SplitScreen";
import { Terminal } from "./components/Terminal";
import { Browser } from "./components/Browser";
import { WorkflowExport } from "./components/WorkflowExport";
import { Schedule } from "./components/Schedule";
import { ScoutLogo } from "./components/ScoutLogo";
import beatsData from "./beats.json";

/** Beats that render inside browser chrome (pricing stays visible through pre-export) */
const BROWSER_BEATS = new Set(["launch", "scout", "interact", "captured", "pre-export"]);

export const ScoutDemo: React.FC = () => {
  const beats = beatsData.beats;
  const outroBeat = beats.find(b => b.id === "outro")!;

  return (
    <AbsoluteFill>
      {/* All beats except outro: split screen */}
      <Sequence from={0} durationInFrames={outroBeat.startFrame}>
        <SplitScreen
          left={<Terminal beats={beats} />}
          right={
            <AbsoluteFill>
              {/* Browser-wrapped beats (landing through pre-export pricing) */}
              {beats.filter(b => BROWSER_BEATS.has(b.id)).map((beat) => (
                <Sequence key={beat.id} from={beat.startFrame} durationInFrames={beat.endFrame - beat.startFrame}>
                  <Browser
                    scene={beat.browser.scene as any}
                    shieldState={beat.browser.shieldState as any}
                    animate={beat.id === "launch"}
                  />
                </Sequence>
              ))}

              {/* Export + pre-schedule: dark canvas with workflow files
                  (stays visible while "Schedule it..." types in terminal) */}
              {(() => {
                const exportBeat = beats.find(b => b.id === "export")!;
                const preSchBeat = beats.find(b => b.id === "pre-schedule")!;
                return (
                  <Sequence from={exportBeat.startFrame} durationInFrames={preSchBeat.endFrame - exportBeat.startFrame}>
                    <AbsoluteFill style={{ backgroundColor: "#11111b" }}>
                      <WorkflowExport />
                    </AbsoluteFill>
                  </Sequence>
                );
              })()}

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
      <Sequence from={outroBeat.startFrame} durationInFrames={outroBeat.endFrame - outroBeat.startFrame}>
        <ScoutLogo />
      </Sequence>
    </AbsoluteFill>
  );
};
