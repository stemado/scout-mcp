import { useState, useEffect } from "react";

const PHASES = [
  {
    id: "I",
    title: "Plugin",
    subtitle: "Claude Code MCP Server",
    audience: "Internal",
    description:
      "Scout operates as a Claude Code plugin, automating enterprise portals that resist automation. Credential vault with OS keyring integration. Runtime scrubbing ensures Claude never sees sensitive values.",
    validates: "Reliable automation against portals with anti-bot detection",
    keyCapabilities: [
      "12 MCP tools for browser control",
      "Encrypted credential vault",
      "Session export to standalone scripts",
      "Video recording & network interception",
    ],
    status: "active",
  },
  {
    id: "II",
    title: "Workflows",
    subtitle: "Stored & Scheduled Automation",
    audience: "Internal → External",
    description:
      "Workflows are defined, stored, and scheduled to run unattended — without Claude in the loop. This phase proves that automations can survive without human oversight and forces resolution of monitoring and reliability problems.",
    validates: "Unattended execution reliability and failure recovery",
    keyCapabilities: [
      "Workflow definition & persistence",
      "Cron-based scheduling engine",
      "Execution monitoring dashboard",
      "Claude-assisted self-healing on failure",
    ],
    status: "next",
  },
  {
    id: "III",
    title: "Hosted API",
    subtitle: "Published REST Endpoints",
    audience: "Internal → Gradual External",
    description:
      "Customers publish workflows as REST endpoints. Downstream systems call Scout's API and receive structured JSON — never knowing a browser was involved. This is the Plaid model: Scout becomes the API that legacy systems never built.",
    validates: "Enterprise-grade API synthesis at scale",
    keyCapabilities: [
      "Auto-generated API contracts from workflows",
      "Multi-tenant credential isolation (Azure Key Vault)",
      "Browser farm orchestration",
      "Per-call billing and metering",
    ],
    status: "future",
  },
  {
    id: "IV",
    title: "Adaptive Intelligence",
    subtitle: "Claude API — Proactive Change Detection",
    audience: "Platform-Wide",
    description:
      "The Claude API enables Scout to monitor portal health continuously — detecting UI changes, new authentication flows, and structural shifts before they cause workflow failures. Claude's vision and reasoning capabilities transform portal maintenance from a reactive staffing problem into an autonomous system capability. This is what allows Scout to scale without linear headcount growth.",
    validates: "Operational scalability without proportional human intervention",
    keyCapabilities: [
      "Scheduled portal health scans via Claude Vision",
      "Structural diff detection (DOM + visual)",
      "Autonomous repair for cosmetic changes",
      "Human-in-the-loop review for auth/data logic changes",
    ],
    status: "future",
  },
];

const ARCHITECTURE_LAYERS = [
  {
    name: "Client Systems",
    color: "#94A3B8",
    items: ["ERP", "HRIS", "Payroll Engine", "Custom Apps"],
    description: "Any system that needs data from a legacy portal",
  },
  {
    name: "Scout API Layer",
    color: "#F59E0B",
    items: [
      "REST Endpoints",
      "Auth & Rate Limiting",
      "Schema Contracts",
      "Billing / Metering",
    ],
    description: "Published endpoints with typed request/response contracts",
  },
  {
    name: "Orchestration",
    color: "#3B82F6",
    items: [
      "Workflow Engine",
      "Queue Management",
      "Scheduling",
      "Self-Healing (Claude)",
    ],
    description: "Execution coordination with AI-assisted failure recovery",
  },
  {
    name: "PII Redaction Middleware",
    color: "#EF4444",
    items: [
      "OCR + Pattern Matching",
      "Semantic Page Descriptions",
      "Image Redaction",
      "Local LLM Processing",
    ],
    description:
      "Structural guarantee: sensitive data never reaches the AI layer",
  },
  {
    name: "Security Boundary",
    color: "#10B981",
    items: [
      "Azure Key Vault",
      "Per-Tenant Isolation",
      "Credential Injection",
      "Audit Logging",
    ],
    description: "Multi-tenant credential management with zero-exposure design",
  },
  {
    name: "Browser Runtime",
    color: "#8B5CF6",
    items: [
      "Headless Chromium Pool",
      "Session Management",
      "Anti-Detection Engine",
      "Portal Connectors",
    ],
    description: "Reliable browser automation against resistant portals",
  },
];

const SOLVED_CONCERNS = [
  {
    concern: "PII Exposure to AI",
    solution: "Redaction Middleware",
    detail:
      "Screenshots and DOM data pass through a redaction pipeline before reaching Claude. PII is replaced with semantic tokens ([SSN], [SALARY], [NAME]). Claude reasons about page structure without ever seeing sensitive values. The same architectural pattern already proven by Scout's credential vault — extended to visual data.",
    icon: "\u{1F6E1}\uFE0F",
  },
  {
    concern: "Credential Security at Scale",
    solution: "Vault-Per-Tenant Isolation",
    detail:
      "Customer credentials live in dedicated Azure Key Vault instances — cryptographically isolated, never at rest in the application layer. Short-lived access tokens with full audit trails. The compliance boundary stays inside Scout's infrastructure, entirely upstream of Anthropic.",
    icon: "\u{1F510}",
  },
  {
    concern: "Portal Fragility",
    solution: "Claude-Assisted Self-Healing",
    detail:
      "When a portal changes its UI, Claude's vision capabilities detect the structural shift from redacted screenshots and propose workflow repairs. Initially human-approved; autonomy widens over time for cosmetic changes. The only scalable approach to maintaining hundreds of portal integrations.",
    icon: "\u{1F504}",
  },
  {
    concern: "Compliance Surface Area",
    solution: "Architectural Containment",
    detail:
      "Because PII never crosses the boundary to Anthropic's API, SOC 2 Type II audit scope covers only Scout's redaction pipeline and vault — not Anthropic's entire inference infrastructure. This transforms a complex multi-party compliance negotiation into a self-contained engineering problem.",
    icon: "\u2713",
  },
];

export default function ScoutOverview() {
  const [activePhase, setActivePhase] = useState(0);
  const [activeArch, setActiveArch] = useState(null);
  const [activeConcern, setActiveConcern] = useState(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 100);
    return () => clearTimeout(t);
  }, []);

  return (
    <div
      style={{
        fontFamily: "'DM Sans', 'Helvetica Neue', sans-serif",
        background: "#0A0F1C",
        color: "#E2E8F0",
        minHeight: "100vh",
        overflow: "hidden",
      }}
    >
      <link
        href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,700;1,9..40,300&family=DM+Mono:wght@300;400;500&family=Instrument+Serif:ital@0;1&display=swap"
        rel="stylesheet"
      />

      <header
        style={{
          position: "relative",
          padding: "80px 48px 64px",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "-200px",
            right: "-100px",
            width: "600px",
            height: "600px",
            background:
              "radial-gradient(circle, rgba(245,158,11,0.08) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "-300px",
            left: "-200px",
            width: "800px",
            height: "800px",
            background:
              "radial-gradient(circle, rgba(59,130,246,0.05) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        <div
          style={{
            maxWidth: 1100,
            margin: "0 auto",
            position: "relative",
            opacity: mounted ? 1 : 0,
            transform: mounted ? "translateY(0)" : "translateY(24px)",
            transition: "all 0.8s cubic-bezier(0.16, 1, 0.3, 1)",
          }}
        >
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 10,
              marginBottom: 32,
              padding: "6px 16px",
              background: "rgba(245,158,11,0.1)",
              border: "1px solid rgba(245,158,11,0.2)",
              borderRadius: 100,
              fontSize: 13,
              fontFamily: "'DM Mono', monospace",
              color: "#F59E0B",
              letterSpacing: "0.04em",
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "#F59E0B",
                display: "inline-block",
              }}
            />
            STRATEGIC OVERVIEW
          </div>

          <h1
            style={{
              fontFamily: "'Instrument Serif', Georgia, serif",
              fontSize: "clamp(42px, 5.5vw, 72px)",
              fontWeight: 400,
              lineHeight: 1.05,
              margin: 0,
              color: "#F8FAFC",
              maxWidth: 800,
            }}
          >
            Scout turns any web portal
            <br />
            <span style={{ color: "#F59E0B", fontStyle: "italic" }}>
              into a programmable API
            </span>
          </h1>

          <p
            style={{
              fontSize: 18,
              lineHeight: 1.7,
              color: "#94A3B8",
              maxWidth: 620,
              marginTop: 28,
              fontWeight: 300,
            }}
          >
            An API synthesis engine for legacy systems. Browser automation that
            enterprises trust with their most sensitive workflows — because
            sensitive data never reaches the AI layer.
          </p>

          <div
            style={{
              display: "flex",
              gap: 32,
              marginTop: 48,
              paddingTop: 32,
              borderTop: "1px solid rgba(148,163,184,0.1)",
            }}
          >
            {[
              ["Industry", "Horizontal"],
              ["Architecture", "MCP Server \u2192 Hosted API"],
              ["Security Model", "Structural Containment"],
            ].map(([label, value]) => (
              <div key={label}>
                <div
                  style={{
                    fontSize: 11,
                    fontFamily: "'DM Mono', monospace",
                    color: "#64748B",
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    marginBottom: 6,
                  }}
                >
                  {label}
                </div>
                <div style={{ fontSize: 15, color: "#CBD5E1", fontWeight: 500 }}>
                  {value}
                </div>
              </div>
            ))}
          </div>
        </div>
      </header>

      <section style={{ padding: "48px 48px 64px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 2,
              borderRadius: 16,
              overflow: "hidden",
              opacity: mounted ? 1 : 0,
              transform: mounted ? "translateY(0)" : "translateY(24px)",
              transition: "all 0.8s cubic-bezier(0.16, 1, 0.3, 1) 0.15s",
            }}
          >
            {[
              {
                company: "Plaid",
                what: "Banks didn't have APIs.",
                how: "Plaid became the API. Screen scraping, credential proxying, browser automation \u2014 hidden behind clean REST endpoints. Developers called /transactions/get and never knew a scraper was involved.",
                accent: "#10B981",
              },
              {
                company: "Scout",
                what: "Enterprise portals don't have APIs.",
                how: "Scout becomes the API. Stealth browser automation, credential vault, PII redaction \u2014 hidden behind published endpoints. Client systems call /employees/elections and never know a browser was involved.",
                accent: "#F59E0B",
              },
            ].map((item) => (
              <div
                key={item.company}
                style={{
                  background: "rgba(148,163,184,0.04)",
                  padding: "40px 36px",
                  position: "relative",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: 2,
                    background: item.accent,
                  }}
                />
                <div
                  style={{
                    fontFamily: "'DM Mono', monospace",
                    fontSize: 12,
                    color: item.accent,
                    letterSpacing: "0.1em",
                    textTransform: "uppercase",
                    marginBottom: 16,
                  }}
                >
                  {item.company}
                </div>
                <div
                  style={{
                    fontFamily: "'Instrument Serif', serif",
                    fontSize: 24,
                    color: "#F8FAFC",
                    marginBottom: 16,
                    fontStyle: "italic",
                  }}
                >
                  {item.what}
                </div>
                <p
                  style={{
                    fontSize: 14,
                    lineHeight: 1.75,
                    color: "#94A3B8",
                    margin: 0,
                    fontWeight: 300,
                  }}
                >
                  {item.how}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section style={{ padding: "64px 48px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <SectionLabel>Phased Roadmap</SectionLabel>
          <h2 style={sectionTitleStyle}>
            Each phase validates the next
          </h2>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.7,
              color: "#94A3B8",
              maxWidth: 640,
              marginBottom: 48,
              fontWeight: 300,
            }}
          >
            Every phase is dogfooded internally before external release.
            Capability maturity and audience scope advance on independent axes —
            never simultaneously.
          </p>

          <div
            style={{
              display: "flex",
              gap: 0,
              marginBottom: 0,
              borderBottom: "1px solid rgba(148,163,184,0.1)",
            }}
          >
            {PHASES.map((p, i) => {
              const isActive = i === activePhase;
              const statusColor =
                p.status === "active"
                  ? "#10B981"
                  : p.status === "next"
                    ? "#F59E0B"
                    : "#64748B";
              return (
                <button
                  key={p.id}
                  onClick={() => setActivePhase(i)}
                  style={{
                    background: "none",
                    border: "none",
                    borderBottom: `2px solid ${isActive ? "#F59E0B" : "transparent"}`,
                    padding: "16px 28px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    transition: "all 0.2s",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 22,
                      fontWeight: 500,
                      color: isActive ? "#F8FAFC" : "#475569",
                      transition: "color 0.2s",
                    }}
                  >
                    {p.id}
                  </span>
                  <span
                    style={{
                      fontSize: 15,
                      color: isActive ? "#CBD5E1" : "#64748B",
                      fontWeight: 500,
                      transition: "color 0.2s",
                    }}
                  >
                    {p.title}
                  </span>
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: statusColor,
                      opacity: 0.8,
                    }}
                  />
                </button>
              );
            })}
          </div>

          {PHASES.map((phase, i) => {
            if (i !== activePhase) return null;
            return (
              <div
                key={phase.id}
                style={{
                  background: "rgba(148,163,184,0.03)",
                  border: "1px solid rgba(148,163,184,0.08)",
                  borderTop: "none",
                  borderRadius: "0 0 12px 12px",
                  padding: "40px 36px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: 24,
                  }}
                >
                  <div>
                    <h3
                      style={{
                        fontFamily: "'Instrument Serif', serif",
                        fontSize: 28,
                        fontWeight: 400,
                        color: "#F8FAFC",
                        margin: "0 0 4px",
                      }}
                    >
                      {phase.title}
                    </h3>
                    <span
                      style={{
                        fontFamily: "'DM Mono', monospace",
                        fontSize: 13,
                        color: "#64748B",
                      }}
                    >
                      {phase.subtitle}
                    </span>
                  </div>
                  <div
                    style={{
                      padding: "5px 14px",
                      borderRadius: 100,
                      fontSize: 12,
                      fontFamily: "'DM Mono', monospace",
                      letterSpacing: "0.04em",
                      background:
                        phase.status === "active"
                          ? "rgba(16,185,129,0.1)"
                          : phase.status === "next"
                            ? "rgba(245,158,11,0.1)"
                            : "rgba(100,116,139,0.1)",
                      color:
                        phase.status === "active"
                          ? "#10B981"
                          : phase.status === "next"
                            ? "#F59E0B"
                            : "#64748B",
                      border: `1px solid ${
                        phase.status === "active"
                          ? "rgba(16,185,129,0.2)"
                          : phase.status === "next"
                            ? "rgba(245,158,11,0.2)"
                            : "rgba(100,116,139,0.15)"
                      }`,
                    }}
                  >
                    {phase.audience}
                  </div>
                </div>

                <p
                  style={{
                    fontSize: 15,
                    lineHeight: 1.75,
                    color: "#94A3B8",
                    margin: "0 0 28px",
                    maxWidth: 680,
                    fontWeight: 300,
                  }}
                >
                  {phase.description}
                </p>

                <div
                  style={{
                    background: "rgba(245,158,11,0.04)",
                    border: "1px solid rgba(245,158,11,0.1)",
                    borderRadius: 8,
                    padding: "14px 20px",
                    marginBottom: 28,
                    fontSize: 14,
                    color: "#F59E0B",
                  }}
                >
                  <span
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 11,
                      opacity: 0.7,
                      marginRight: 10,
                      letterSpacing: "0.06em",
                    }}
                  >
                    VALIDATES \u2192
                  </span>
                  {phase.validates}
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: 12,
                  }}
                >
                  {phase.keyCapabilities.map((cap) => (
                    <div
                      key={cap}
                      style={{
                        padding: "12px 16px",
                        background: "rgba(148,163,184,0.04)",
                        borderRadius: 8,
                        fontSize: 13,
                        color: "#CBD5E1",
                        fontFamily: "'DM Mono', monospace",
                        border: "1px solid rgba(148,163,184,0.06)",
                      }}
                    >
                      {cap}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section style={{ padding: "64px 48px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <SectionLabel>Technical Architecture</SectionLabel>
          <h2 style={sectionTitleStyle}>
            Six layers, one security boundary
          </h2>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.7,
              color: "#94A3B8",
              maxWidth: 640,
              marginBottom: 48,
              fontWeight: 300,
            }}
          >
            The PII redaction middleware is the critical boundary. Everything
            below it handles sensitive data within Scout's infrastructure.
            Everything above it receives only sanitized, semantic
            representations. Claude never sees the raw data.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
            {ARCHITECTURE_LAYERS.map((layer, i) => {
              const isActive = activeArch === i;
              const isRedaction = i === 3;
              return (
                <div
                  key={layer.name}
                  onClick={() => setActiveArch(isActive ? null : i)}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "220px 1fr",
                    background: isActive
                      ? "rgba(148,163,184,0.06)"
                      : "rgba(148,163,184,0.02)",
                    borderRadius: 10,
                    overflow: "hidden",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    border: isRedaction
                      ? "1px solid rgba(239,68,68,0.2)"
                      : "1px solid rgba(148,163,184,0.06)",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      padding: "18px 24px",
                      borderRight: `2px solid ${layer.color}`,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                    }}
                  >
                    <div
                      style={{
                        fontFamily: "'DM Mono', monospace",
                        fontSize: 11,
                        color: "#64748B",
                        letterSpacing: "0.06em",
                        marginBottom: 4,
                      }}
                    >
                      LAYER {i + 1}
                    </div>
                    <div
                      style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: layer.color,
                      }}
                    >
                      {layer.name}
                    </div>
                  </div>
                  <div style={{ padding: "18px 24px" }}>
                    <div
                      style={{
                        display: "flex",
                        gap: 10,
                        flexWrap: "wrap",
                        marginBottom: isActive ? 14 : 0,
                      }}
                    >
                      {layer.items.map((item) => (
                        <span
                          key={item}
                          style={{
                            padding: "4px 12px",
                            background: `${layer.color}10`,
                            borderRadius: 6,
                            fontSize: 12,
                            color: layer.color,
                            fontFamily: "'DM Mono', monospace",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                    {isActive && (
                      <p
                        style={{
                          fontSize: 13,
                          lineHeight: 1.7,
                          color: "#94A3B8",
                          margin: 0,
                          fontWeight: 300,
                        }}
                      >
                        {layer.description}
                      </p>
                    )}
                  </div>

                  {isRedaction && (
                    <div
                      style={{
                        position: "absolute",
                        right: 20,
                        top: "50%",
                        transform: "translateY(-50%)",
                        fontFamily: "'DM Mono', monospace",
                        fontSize: 10,
                        color: "#EF4444",
                        letterSpacing: "0.1em",
                        opacity: 0.7,
                      }}
                    >
                      \u2190 PII BOUNDARY
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "center",
              gap: 40,
              marginTop: 32,
              paddingTop: 24,
              borderTop: "1px solid rgba(148,163,184,0.06)",
            }}
          >
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                color: "#64748B",
                fontFamily: "'DM Mono', monospace",
              }}
            >
              <span
                style={{
                  width: 24,
                  height: 2,
                  background: "#10B981",
                  display: "inline-block",
                }}
              />
              Sanitized data \u2192 Claude
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                fontSize: 12,
                color: "#64748B",
                fontFamily: "'DM Mono', monospace",
              }}
            >
              <span
                style={{
                  width: 24,
                  height: 2,
                  background: "#EF4444",
                  display: "inline-block",
                }}
              />
              Raw PII \u2014 never leaves Scout infrastructure
            </div>
          </div>
        </div>
      </section>

      <section style={{ padding: "64px 48px 80px" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <SectionLabel>Resolved Technical Concerns</SectionLabel>
          <h2 style={sectionTitleStyle}>
            Four problems, four structural solutions
          </h2>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.7,
              color: "#94A3B8",
              maxWidth: 640,
              marginBottom: 48,
              fontWeight: 300,
            }}
          >
            Each concern is addressed architecturally — through structural
            prevention rather than reactive defense. The security is in the
            design, not in hoping the software behaves correctly.
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 2,
              borderRadius: 12,
              overflow: "hidden",
            }}
          >
            {SOLVED_CONCERNS.map((item, i) => {
              const isActive = activeConcern === i;
              return (
                <div
                  key={item.concern}
                  onClick={() => setActiveConcern(isActive ? null : i)}
                  style={{
                    background: isActive
                      ? "rgba(148,163,184,0.06)"
                      : "rgba(148,163,184,0.025)",
                    padding: "32px 28px",
                    cursor: "pointer",
                    transition: "background 0.2s",
                  }}
                >
                  <div
                    style={{
                      fontSize: 28,
                      marginBottom: 16,
                      filter: "grayscale(0.3)",
                    }}
                  >
                    {item.icon}
                  </div>
                  <div
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 11,
                      color: "#EF4444",
                      letterSpacing: "0.06em",
                      marginBottom: 6,
                      textTransform: "uppercase",
                      textDecoration: "line-through",
                      opacity: 0.7,
                    }}
                  >
                    {item.concern}
                  </div>
                  <div
                    style={{
                      fontSize: 17,
                      fontWeight: 500,
                      color: "#F8FAFC",
                      marginBottom: isActive ? 16 : 0,
                    }}
                  >
                    {item.solution}
                  </div>
                  {isActive && (
                    <p
                      style={{
                        fontSize: 13,
                        lineHeight: 1.75,
                        color: "#94A3B8",
                        margin: 0,
                        fontWeight: 300,
                      }}
                    >
                      {item.detail}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section
        style={{
          padding: "64px 48px 80px",
          borderTop: "1px solid rgba(148,163,184,0.06)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: "800px",
            height: "400px",
            background:
              "radial-gradient(ellipse, rgba(59,130,246,0.04) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />
        <div style={{ maxWidth: 1100, margin: "0 auto", position: "relative" }}>
          <SectionLabel>Phase IV — The Scalability Inflection</SectionLabel>
          <h2 style={sectionTitleStyle}>
            Claude's API is how Scout scales
            <br />
            <span style={{ color: "#3B82F6", fontStyle: "italic", fontFamily: "'Instrument Serif', serif" }}>
              without scaling headcount
            </span>
          </h2>
          <p
            style={{
              fontSize: 16,
              lineHeight: 1.7,
              color: "#94A3B8",
              maxWidth: 660,
              marginBottom: 48,
              fontWeight: 300,
            }}
          >
            Legacy portals change constantly — redesigns, new auth flows,
            shifted DOM structures. Every traditional automation platform treats
            this as a staffing problem: more portals, more engineers to maintain
            them. The Claude API transforms this from a linear cost into an
            autonomous system capability.
          </p>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 48px 1fr",
              gap: 0,
              alignItems: "stretch",
              marginBottom: 48,
            }}
          >
            <div
              style={{
                background: "rgba(239,68,68,0.04)",
                border: "1px solid rgba(239,68,68,0.12)",
                borderRadius: "12px 0 0 12px",
                padding: "32px 28px",
              }}
            >
              <div
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 11,
                  color: "#EF4444",
                  letterSpacing: "0.08em",
                  marginBottom: 20,
                  textTransform: "uppercase",
                }}
              >
                Without Claude API
              </div>
              <div
                style={{
                  fontFamily: "'Instrument Serif', serif",
                  fontSize: 22,
                  color: "#F8FAFC",
                  marginBottom: 16,
                }}
              >
                Linear scaling trap
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[
                  "Portal changes \u2192 workflow breaks silently",
                  "Human investigates after customer reports failure",
                  "Engineer manually rewrites selectors & logic",
                  "100 portals = 100\u00D7 maintenance burden",
                  "Headcount grows with every new integration",
                ].map((item, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 13,
                      color: "#94A3B8",
                      fontWeight: 300,
                      lineHeight: 1.6,
                      paddingLeft: 16,
                      borderLeft: "2px solid rgba(239,68,68,0.2)",
                    }}
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "rgba(148,163,184,0.03)",
              }}
            >
              <div
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 18,
                  color: "#475569",
                }}
              >
                \u2192
              </div>
            </div>

            <div
              style={{
                background: "rgba(59,130,246,0.04)",
                border: "1px solid rgba(59,130,246,0.12)",
                borderRadius: "0 12px 12px 0",
                padding: "32px 28px",
              }}
            >
              <div
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 11,
                  color: "#3B82F6",
                  letterSpacing: "0.08em",
                  marginBottom: 20,
                  textTransform: "uppercase",
                }}
              >
                With Claude API
              </div>
              <div
                style={{
                  fontFamily: "'Instrument Serif', serif",
                  fontSize: 22,
                  color: "#F8FAFC",
                  marginBottom: 16,
                }}
              >
                Autonomous adaptation
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[
                  "Scheduled health scans detect changes proactively",
                  "Claude Vision compares expected vs. actual page state",
                  "Cosmetic changes repaired autonomously",
                  "Structural changes flagged with proposed fix for review",
                  "1000 portals \u2260 1000\u00D7 engineers",
                ].map((item, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: 13,
                      color: "#CBD5E1",
                      fontWeight: 300,
                      lineHeight: 1.6,
                      paddingLeft: 16,
                      borderLeft: "2px solid rgba(59,130,246,0.3)",
                    }}
                  >
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div
            style={{
              background: "rgba(148,163,184,0.025)",
              border: "1px solid rgba(148,163,184,0.08)",
              borderRadius: 12,
              padding: "32px 28px",
            }}
          >
            <div
              style={{
                fontFamily: "'DM Mono', monospace",
                fontSize: 11,
                color: "#64748B",
                letterSpacing: "0.08em",
                marginBottom: 24,
                textTransform: "uppercase",
              }}
            >
              Adaptive Intelligence Pipeline
            </div>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr 1fr",
                gap: 3,
              }}
            >
              {[
                {
                  step: "01",
                  title: "Scan",
                  desc: "Scheduled health checks capture portal state \u2014 screenshots pass through PII redaction before any analysis",
                  color: "#94A3B8",
                },
                {
                  step: "02",
                  title: "Compare",
                  desc: "Claude Vision diffs the redacted scan against the expected page structure stored from the last successful run",
                  color: "#F59E0B",
                },
                {
                  step: "03",
                  title: "Classify",
                  desc: "Changes categorized: cosmetic (CSS/layout), structural (DOM reorganization), or critical (auth flow, data schema)",
                  color: "#3B82F6",
                },
                {
                  step: "04",
                  title: "Adapt",
                  desc: "Cosmetic \u2192 auto-repair. Structural \u2192 proposed fix, human approval. Critical \u2192 alert, workflow paused, manual review",
                  color: "#10B981",
                },
              ].map((item) => (
                <div
                  key={item.step}
                  style={{
                    background: "rgba(148,163,184,0.03)",
                    borderRadius: 8,
                    padding: "24px 20px",
                    position: "relative",
                  }}
                >
                  <div
                    style={{
                      fontFamily: "'DM Mono', monospace",
                      fontSize: 28,
                      fontWeight: 300,
                      color: item.color,
                      opacity: 0.3,
                      marginBottom: 12,
                    }}
                  >
                    {item.step}
                  </div>
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 500,
                      color: "#F8FAFC",
                      marginBottom: 10,
                    }}
                  >
                    {item.title}
                  </div>
                  <p
                    style={{
                      fontSize: 12,
                      lineHeight: 1.7,
                      color: "#94A3B8",
                      margin: 0,
                      fontWeight: 300,
                    }}
                  >
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 24, padding: "20px 0 4px" }}>
              <div
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 10,
                  color: "#64748B",
                  letterSpacing: "0.08em",
                  marginBottom: 12,
                }}
              >
                AUTONOMY SPECTRUM \u2014 WIDENS OVER TIME
              </div>
              <div
                style={{
                  height: 6,
                  borderRadius: 3,
                  background: "rgba(148,163,184,0.08)",
                  position: "relative",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    top: 0,
                    height: "100%",
                    width: "35%",
                    background: "#10B981",
                    borderRadius: 3,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: "35%",
                    top: 0,
                    height: "100%",
                    width: "35%",
                    background: "#F59E0B",
                    opacity: 0.6,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: "70%",
                    top: 0,
                    height: "100%",
                    width: "30%",
                    background: "#EF4444",
                    borderRadius: "0 3px 3px 0",
                    opacity: 0.4,
                  }}
                />
              </div>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginTop: 8,
                }}
              >
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: "'DM Mono', monospace",
                    color: "#10B981",
                  }}
                >
                  Auto-repair
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: "'DM Mono', monospace",
                    color: "#F59E0B",
                  }}
                >
                  Propose + approve
                </span>
                <span
                  style={{
                    fontSize: 10,
                    fontFamily: "'DM Mono', monospace",
                    color: "#EF4444",
                  }}
                >
                  Human-only
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section
        style={{
          padding: "64px 48px 96px",
          borderTop: "1px solid rgba(148,163,184,0.06)",
        }}
      >
        <div style={{ maxWidth: 1100, margin: "0 auto" }}>
          <SectionLabel>Competitive Moat</SectionLabel>
          <h2 style={sectionTitleStyle}>Three compounding advantages</h2>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: 2,
              marginTop: 40,
              borderRadius: 12,
              overflow: "hidden",
            }}
          >
            <div style={{ background: "rgba(148,163,184,0.03)", padding: "36px 32px" }}>
              <div
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 12,
                  color: "#F59E0B",
                  letterSpacing: "0.08em",
                  marginBottom: 16,
                }}
              >
                MOAT 1 \u2014 WORKFLOW NETWORK EFFECTS
              </div>
              <p
                style={{
                  fontSize: 15,
                  lineHeight: 1.75,
                  color: "#CBD5E1",
                  margin: 0,
                  fontWeight: 300,
                }}
              >
                Every workflow a customer builds becomes institutional knowledge
                encoded in the platform. When multiple customers automate the same
                portal, those workflows become more resilient and well-tested. Over
                time, Scout can offer pre-built connectors for popular systems —
                turning individual automations into a library of ready-made
                integrations.
              </p>
            </div>
            <div style={{ background: "rgba(148,163,184,0.03)", padding: "36px 32px" }}>
              <div
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 12,
                  color: "#3B82F6",
                  letterSpacing: "0.08em",
                  marginBottom: 16,
                }}
              >
                MOAT 2 \u2014 COMPLIANCE AS PRODUCT
              </div>
              <p
                style={{
                  fontSize: 15,
                  lineHeight: 1.75,
                  color: "#CBD5E1",
                  margin: 0,
                  fontWeight: 300,
                }}
              >
                The PII redaction middleware and vault-per-tenant isolation aren't
                just security measures — they're the product. Most competitors will
                avoid the compliance complexity entirely. The company that can hand
                an enterprise customer a SOC 2 Type II report and a clear data flow
                diagram showing exactly where PII goes and how long it lives at each
                node owns the enterprise market. Everyone else is selling toys.
              </p>
            </div>
            <div style={{ background: "rgba(148,163,184,0.03)", padding: "36px 32px" }}>
              <div
                style={{
                  fontFamily: "'DM Mono', monospace",
                  fontSize: 12,
                  color: "#10B981",
                  letterSpacing: "0.08em",
                  marginBottom: 16,
                }}
              >
                MOAT 3 \u2014 ADAPTIVE INTELLIGENCE
              </div>
              <p
                style={{
                  fontSize: 15,
                  lineHeight: 1.75,
                  color: "#CBD5E1",
                  margin: 0,
                  fontWeight: 300,
                }}
              >
                The Claude API enables Scout to maintain integrations autonomously as
                portals evolve. Competitors face a linear scaling trap — every new
                portal integration requires proportional engineering maintenance.
                Scout's adaptive intelligence breaks that curve. The more portals it
                monitors, the better its change detection becomes, and the cost of
                maintaining 1,000 integrations approaches the cost of maintaining 100.
              </p>
            </div>
          </div>
        </div>
      </section>

      <footer
        style={{
          padding: "32px 48px",
          borderTop: "1px solid rgba(148,163,184,0.06)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          maxWidth: 1196,
          margin: "0 auto",
        }}
      >
        <div
          style={{
            fontFamily: "'DM Mono', monospace",
            fontSize: 13,
            color: "#475569",
          }}
        >
          Scout \u2014 Strategic Overview \u2014 February 2026
        </div>
        <div
          style={{
            fontFamily: "'DM Mono', monospace",
            fontSize: 12,
            color: "#334155",
          }}
        >
          CONFIDENTIAL
        </div>
      </footer>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div
      style={{
        fontFamily: "'DM Mono', monospace",
        fontSize: 12,
        color: "#F59E0B",
        letterSpacing: "0.1em",
        textTransform: "uppercase",
        marginBottom: 16,
      }}
    >
      {children}
    </div>
  );
}

const sectionTitleStyle = {
  fontFamily: "'Instrument Serif', Georgia, serif",
  fontSize: "clamp(28px, 3.5vw, 40px)",
  fontWeight: 400,
  color: "#F8FAFC",
  margin: "0 0 12px",
  lineHeight: 1.15,
};