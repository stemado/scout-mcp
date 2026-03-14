import { AbsoluteFill, Sequence } from "remotion";
import { SplitScreen } from "./components/SplitScreen";
import { Terminal } from "./components/Terminal";
import { Browser } from "./components/Browser";
import beatsData from "./beats.json";

export const ScoutDemo: React.FC = () => {
  const beats = beatsData.beats;

  return (
    <AbsoluteFill>
      <SplitScreen
        left={<Terminal beats={beats} />}
        right={
          <AbsoluteFill>
            {beats.map((beat) => (
              <Sequence key={beat.id} from={beat.startFrame} durationInFrames={beat.endFrame - beat.startFrame}>
                <Browser scene={beat.browser.scene as any} shieldState={beat.browser.shieldState as any} />
              </Sequence>
            ))}
          </AbsoluteFill>
        }
      />
    </AbsoluteFill>
  );
};
