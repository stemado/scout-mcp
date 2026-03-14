import { loadFont as loadJetBrainsMono } from "@remotion/google-fonts/JetBrainsMono";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";

const jetBrainsMono = loadJetBrainsMono();
const inter = loadInter();

export const terminalFontFamily = jetBrainsMono.fontFamily;
export const uiFontFamily = inter.fontFamily;
