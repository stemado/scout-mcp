import React from "react";
import { spring, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import { uiFontFamily } from "../styles/fonts";

type Scene = "landing" | "page-loaded" | "form-fill" | "pricing" | "export" | "schedule" | "outro";

interface BrowserPageProps {
  scene: Scene;
}

export const BrowserPage: React.FC<BrowserPageProps> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (scene === "landing") {
    const fadeOut = interpolate(frame, [100, 130], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    return (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", fontFamily: uiFontFamily }}>
        <div style={{ opacity: fadeOut }}>
          <div style={{ fontSize: 18, color: "#6c7086", marginBottom: 20 }}>Checking your browser...</div>
          <div style={{ width: 200, height: 4, backgroundColor: "#313244", borderRadius: 2 }}>
            <div style={{
              width: `${interpolate(frame, [0, 100], [0, 100], { extrapolateRight: "clamp" })}%`,
              height: "100%",
              backgroundColor: "#f9e2af",
              borderRadius: 2,
            }} />
          </div>
        </div>
      </div>
    );
  }

  if (scene === "page-loaded") {
    const fadeIn = spring({ fps, frame, config: { damping: 200 } });
    // Login button pulses when find_elements locates it (around frame 140+ into this beat)
    const pulseStart = 140;
    const pulseProgress = frame > pulseStart ? spring({ fps, frame: frame - pulseStart, config: { damping: 60, stiffness: 300 } }) : 0;
    const buttonGlow = interpolate(pulseProgress, [0, 0.5, 1], [0, 8, 0]);
    const buttonScale = interpolate(pulseProgress, [0, 0.3, 1], [1, 1.05, 1]);

    return (
      <div style={{ opacity: fadeIn, padding: 30, fontFamily: uiFontFamily, color: "#cdd6f4" }}>
        <div style={{ display: "flex", gap: 20, marginBottom: 30, fontSize: 14, color: "#6c7086" }}>
          <span>Home</span><span>Products</span><span>Pricing</span><span>Contact</span>
        </div>
        <div style={{ maxWidth: 300, margin: "0 auto" }}>
          <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 20 }}>Sign In</div>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: "#6c7086", marginBottom: 4 }}>Email</div>
            <div style={{ height: 36, border: "1px solid #313244", borderRadius: 4, backgroundColor: "#181825" }} />
          </div>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "#6c7086", marginBottom: 4 }}>Password</div>
            <div style={{ height: 36, border: "1px solid #313244", borderRadius: 4, backgroundColor: "#181825" }} />
          </div>
          <div style={{
            height: 36,
            backgroundColor: "#89b4fa",
            borderRadius: 4,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            fontWeight: 600,
            color: "#1e1e2e",
            transform: `scale(${buttonScale})`,
            boxShadow: buttonGlow > 0 ? `0 0 ${buttonGlow}px ${buttonGlow}px rgba(137, 180, 250, 0.5)` : "none",
          }}>
            Login
          </div>
        </div>
      </div>
    );
  }

  if (scene === "form-fill") {
    const emailProgress = interpolate(frame, [0, 40], [0, 22], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const passwordProgress = interpolate(frame, [50, 80], [0, 16], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const buttonPressed = frame > 120;
    const dashboardFade = interpolate(frame, [130, 160], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

    if (dashboardFade > 0.1) {
      // Pricing table — realistic data worth scraping
      const plans = [
        { name: "Starter", price: "$49", period: "/mo", users: "5 users", storage: "10 GB", support: "Email", highlight: false },
        { name: "Pro", price: "$199", period: "/mo", users: "25 users", storage: "100 GB", support: "Priority", highlight: true },
        { name: "Enterprise", price: "$499", period: "/mo", users: "Unlimited", storage: "1 TB", support: "24/7 Phone", highlight: false },
      ];
      return (
        <div style={{ opacity: dashboardFade, padding: 24, fontFamily: uiFontFamily, color: "#cdd6f4" }}>
          <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 4 }}>Current Pricing</div>
          <div style={{ fontSize: 12, color: "#6c7086", marginBottom: 16 }}>Updated March 14, 2026</div>
          <div style={{ display: "flex", gap: 12 }}>
            {plans.map((plan) => (
              <div key={plan.name} style={{
                flex: 1,
                padding: 16,
                backgroundColor: plan.highlight ? "#1e3a2f" : "#181825",
                borderRadius: 8,
                border: `1px solid ${plan.highlight ? "#a6e3a1" : "#313244"}`,
              }}>
                <div style={{ fontSize: 13, color: "#6c7086", marginBottom: 4 }}>{plan.name}</div>
                <div style={{ display: "flex", alignItems: "baseline", marginBottom: 12 }}>
                  <span style={{ fontSize: 28, fontWeight: 700, color: plan.highlight ? "#a6e3a1" : "#cdd6f4" }}>{plan.price}</span>
                  <span style={{ fontSize: 12, color: "#6c7086", marginLeft: 2 }}>{plan.period}</span>
                </div>
                <div style={{ fontSize: 11, color: "#a6adc8", lineHeight: 1.8 }}>
                  <div>{plan.users}</div>
                  <div>{plan.storage}</div>
                  <div>{plan.support} support</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    }

    return (
      <div style={{ padding: 30, fontFamily: uiFontFamily, color: "#cdd6f4" }}>
        <div style={{ display: "flex", gap: 20, marginBottom: 30, fontSize: 14, color: "#6c7086" }}>
          <span>Home</span><span>Products</span><span>Pricing</span><span>Contact</span>
        </div>
        <div style={{ maxWidth: 300, margin: "0 auto" }}>
          <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 20 }}>Sign In</div>
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: "#6c7086", marginBottom: 4 }}>Email</div>
            <div style={{ height: 36, border: "1px solid #313244", borderRadius: 4, backgroundColor: "#181825", display: "flex", alignItems: "center", paddingLeft: 10, fontSize: 16, letterSpacing: 2 }}>
              {"•".repeat(Math.floor(emailProgress))}
            </div>
          </div>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 12, color: "#6c7086", marginBottom: 4 }}>Password</div>
            <div style={{ height: 36, border: "1px solid #313244", borderRadius: 4, backgroundColor: "#181825", display: "flex", alignItems: "center", paddingLeft: 10, fontSize: 16, letterSpacing: 2 }}>
              {"•".repeat(Math.floor(passwordProgress))}
            </div>
          </div>
          <div style={{
            height: 36,
            backgroundColor: buttonPressed ? "#74c7ec" : "#89b4fa",
            borderRadius: 4,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            fontWeight: 600,
            color: "#1e1e2e",
            transform: buttonPressed ? "scale(0.96)" : "scale(1)",
          }}>
            {buttonPressed ? "Logging in..." : "Login"}
          </div>
        </div>
      </div>
    );
  }

  if (scene === "pricing") {
    // Static pricing table — stays visible while terminal shows captured data
    const plans = [
      { name: "Starter", price: "$49", period: "/mo", users: "5 users", storage: "10 GB", support: "Email", highlight: false },
      { name: "Pro", price: "$199", period: "/mo", users: "25 users", storage: "100 GB", support: "Priority", highlight: true },
      { name: "Enterprise", price: "$499", period: "/mo", users: "Unlimited", storage: "1 TB", support: "24/7 Phone", highlight: false },
    ];
    return (
      <div style={{ padding: 24, fontFamily: uiFontFamily, color: "#cdd6f4" }}>
        <div style={{ fontSize: 20, fontWeight: 600, marginBottom: 4 }}>Current Pricing</div>
        <div style={{ fontSize: 12, color: "#6c7086", marginBottom: 16 }}>Updated March 14, 2026</div>
        <div style={{ display: "flex", gap: 12 }}>
          {plans.map((plan) => (
            <div key={plan.name} style={{
              flex: 1,
              padding: 16,
              backgroundColor: plan.highlight ? "#1e3a2f" : "#181825",
              borderRadius: 8,
              border: `1px solid ${plan.highlight ? "#a6e3a1" : "#313244"}`,
            }}>
              <div style={{ fontSize: 13, color: "#6c7086", marginBottom: 4 }}>{plan.name}</div>
              <div style={{ display: "flex", alignItems: "baseline", marginBottom: 12 }}>
                <span style={{ fontSize: 28, fontWeight: 700, color: plan.highlight ? "#a6e3a1" : "#cdd6f4" }}>{plan.price}</span>
                <span style={{ fontSize: 12, color: "#6c7086", marginLeft: 2 }}>{plan.period}</span>
              </div>
              <div style={{ fontSize: 11, color: "#a6adc8", lineHeight: 1.8 }}>
                <div>{plan.users}</div>
                <div>{plan.storage}</div>
                <div>{plan.support} support</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // export, schedule, outro — handled by overlay components (no browser chrome)
  return null;
};
