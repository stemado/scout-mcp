// Reconnaissance JavaScript — injected via Runtime.evaluate
// Returns a comprehensive JSON report of the page's DOM structure.
// botasaurus-driver's run_js auto-wraps in IIFE, so this is the function body.

const MAX_INTERACTIVE = 500;
const report = {
  page_metadata: {
    url: window.location.href,
    title: document.title,
    load_state: document.readyState
  },
  iframe_map: [],
  shadow_dom_boundaries: [],
  interactive_elements: [],
  page_summary: ""
};

// --- Utility: generate a unique CSS selector for an element ---
function getSelector(el) {
  if (el.id) return "#" + CSS.escape(el.id);

  // Try data-testid, name, or other stable attributes first
  if (el.getAttribute("data-testid")) {
    return el.tagName.toLowerCase() + '[data-testid="' + el.getAttribute("data-testid") + '"]';
  }
  if (el.name && el.tagName !== "DIV" && el.tagName !== "SPAN") {
    const nameSelector = el.tagName.toLowerCase() + '[name="' + CSS.escape(el.name) + '"]';
    if (document.querySelectorAll(nameSelector).length === 1) return nameSelector;
  }

  // Build path from parent chain
  const parts = [];
  let current = el;
  while (current && current !== document.body && current !== document.documentElement) {
    let sel = current.tagName.toLowerCase();
    if (current.id) {
      parts.unshift("#" + CSS.escape(current.id));
      break;
    }
    // Add nth-child if needed for uniqueness
    const parent = current.parentElement;
    if (parent) {
      const siblings = Array.from(parent.children).filter(c => c.tagName === current.tagName);
      if (siblings.length > 1) {
        const idx = siblings.indexOf(current) + 1;
        sel += ":nth-of-type(" + idx + ")";
      }
    }
    parts.unshift(sel);
    current = current.parentElement;
  }
  if (parts.length === 0) return el.tagName.toLowerCase();
  return parts.join(" > ");
}

// --- Utility: check element visibility ---
function isVisible(el) {
  if (!el.offsetParent && el.tagName !== "BODY" && el.tagName !== "HTML") {
    // Check for position:fixed elements which have no offsetParent
    const style = window.getComputedStyle(el);
    if (style.position !== "fixed" && style.position !== "sticky") return false;
  }
  const rect = el.getBoundingClientRect();
  if (rect.width === 0 && rect.height === 0) return false;
  const style = window.getComputedStyle(el);
  if (style.display === "none" || style.visibility === "hidden" || parseFloat(style.opacity) === 0) return false;
  return true;
}

// --- Utility: get visible text from an element ---
function getVisibleText(el) {
  // For inputs, use placeholder or value (but never expose password values)
  if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
    if (el.type === "password") {
      return el.placeholder || "";
    }
    return el.placeholder || el.value || "";
  }
  if (el.tagName === "SELECT") {
    const selected = el.options[el.selectedIndex];
    return selected ? selected.text : "";
  }
  // For other elements, get direct text (not deep)
  const text = (el.textContent || "").trim();
  return text.length > 100 ? text.substring(0, 100) + "..." : text;
}

// --- 1. Walk iframes recursively ---
function mapIframes(root, depth, parentSelector) {
  const iframes = root.querySelectorAll("iframe");
  for (const iframe of iframes) {
    const selector = parentSelector
      ? parentSelector + " >>> " + getSelector(iframe)
      : getSelector(iframe);
    const src = iframe.src || iframe.getAttribute("src") || "";

    let accessible = false;
    let crossOrigin = false;
    const children = [];

    try {
      // Try to access content document — throws on cross-origin
      const doc = iframe.contentDocument;
      if (doc) {
        accessible = true;
        // Recurse into accessible iframes
        mapIframes(doc, depth + 1, selector);
      }
    } catch (e) {
      crossOrigin = true;
    }

    // If src is a different origin, mark as cross-origin
    if (src && !crossOrigin) {
      try {
        const iframeUrl = new URL(src, window.location.href);
        if (iframeUrl.origin !== window.location.origin) {
          crossOrigin = true;
          accessible = false;
        }
      } catch (e) { /* invalid URL */ }
    }

    report.iframe_map.push({
      selector: selector,
      src: src,
      depth: depth,
      cross_origin: crossOrigin,
      accessible: accessible,
      children: children
    });
  }
}

// --- 2. Find shadow DOM boundaries ---
function findShadowRoots(root, frameContext) {
  // Use TreeWalker for efficiency on large DOMs
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT);
  let node = walker.nextNode();
  while (node) {
    if (node.shadowRoot) {
      let interactiveCount = 0;
      try {
        interactiveCount = node.shadowRoot.querySelectorAll(
          "button, input, select, textarea, a[href], [role='button'], [onclick], [tabindex]"
        ).length;
      } catch (e) { /* closed shadow root */ }

      report.shadow_dom_boundaries.push({
        host_selector: getSelector(node),
        mode: node.shadowRoot.mode || "open",
        frame_context: frameContext,
        child_interactive_count: interactiveCount
      });

      // Recurse into open shadow roots for interactive elements
      if (node.shadowRoot.mode === "open") {
        findInteractiveElements(node.shadowRoot, frameContext, getSelector(node));
        findShadowRoots(node.shadowRoot, frameContext);
      }
    }
    node = walker.nextNode();
  }
}

// --- 3. Enumerate interactive elements ---
const INTERACTIVE_SELECTOR = [
  "button", "input", "select", "textarea",
  "a[href]",
  "[role='button']", "[role='link']", "[role='tab']",
  "[role='menuitem']", "[role='checkbox']", "[role='radio']",
  "[onclick]", "[tabindex]:not([tabindex='-1'])"
].join(", ");

function findInteractiveElements(root, frameContext, shadowHost) {
  if (report.interactive_elements.length >= MAX_INTERACTIVE) return;

  const elements = root.querySelectorAll(INTERACTIVE_SELECTOR);
  for (const el of elements) {
    if (report.interactive_elements.length >= MAX_INTERACTIVE) break;

    const tag = el.tagName.toLowerCase();
    const type = el.type || el.getAttribute("role") || tag;
    const selector = shadowHost
      ? shadowHost + " >>> " + getSelector(el)
      : getSelector(el);

    report.interactive_elements.push({
      tag: tag,
      type: type,
      selector: selector,
      text: getVisibleText(el),
      frame_context: frameContext,
      in_shadow_dom: !!shadowHost,
      shadow_host: shadowHost || null,
      attributes: (() => {
        const attrs = {};
        if (el.id) attrs.id = el.id;
        if (el.name) attrs.name = el.name;
        if (el.className) attrs.class = el.className;
        const href = el.href || el.getAttribute("href");
        if (href) attrs.href = href;
        if (el.placeholder) attrs.placeholder = el.placeholder;
        if (el.tagName === "INPUT" && el.type !== "password" && el.value) {
          attrs.value = el.value;
        }
        const ariaLabel = el.getAttribute("aria-label");
        if (ariaLabel) attrs.aria_label = ariaLabel;
        return attrs;
      })(),
      visible: isVisible(el),
      enabled: !el.disabled
    });
  }
}

// --- Execute reconnaissance ---
try {
  mapIframes(document, 0, "");
  findShadowRoots(document.body || document.documentElement, "main");
  findInteractiveElements(document, "main", null);
} catch (e) {
  report.page_summary = "Error during reconnaissance: " + e.message;
  return JSON.stringify(report);
}

// --- 4. Build human-readable summary ---
const crossOriginCount = report.iframe_map.filter(i => i.cross_origin).length;
const visibleCount = report.interactive_elements.filter(e => e.visible).length;
const truncated = report.interactive_elements.length >= MAX_INTERACTIVE;

report.page_summary = [
  "Page: " + document.title + " (" + window.location.href + ")",
  report.iframe_map.length + " iframe(s)" +
    (crossOriginCount > 0 ? " (" + crossOriginCount + " cross-origin)" : ""),
  report.shadow_dom_boundaries.length + " shadow DOM boundary(ies)",
  report.interactive_elements.length + " interactive element(s)" +
    " (" + visibleCount + " visible)" +
    (truncated ? " [TRUNCATED at " + MAX_INTERACTIVE + "]" : "")
].join(" | ");

return JSON.stringify(report);
