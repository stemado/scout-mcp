import { Composition } from "remotion";
import { ScoutDemo } from "./ScoutDemo";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="ScoutDemo"
      component={ScoutDemo}
      durationInFrames={900}
      fps={30}
      width={1920}
      height={1080}
    />
  );
};
