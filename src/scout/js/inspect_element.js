// Element inspection JavaScript — injected via Runtime.evaluate
// Performs deep analysis of a single DOM element.
// Template placeholders are replaced by Python before injection.
// botasaurus-driver's run_js auto-wraps in IIFE, so this is the function body.

const SELECTOR = __SELECTOR__;
const INCLUDE_LISTENERS = __INCLUDE_LISTENERS__;
const INCLUDE_CHILDREN = __INCLUDE_CHILDREN__;

const result = {
  found: false,
  tag: "",
  bounding_rect: {},
  computed_visibility: {},
  is_visible: false,
  is_obscured: false,
  obscured_by: null,
  in_shadow_dom: false,
  shadow_host: null,
  parent_chain: [],
  attributes: {},
  aria: {},
  input_state: {},
  children_summary: {},
  event_listeners: []
};

// --- Utility: generate a compact selector for an element ---
function quickSelector(el) {
  if (!el || el === document.body || el === document.documentElement) return el ? el.tagName.toLowerCase() : "";
  let s = el.tagName.toLowerCase();
  if (el.id) s += "#" + el.id;
  else if (el.className && typeof el.className === "string") {
    const classes = el.className.trim().split(/\s+/).slice(0, 2).join(".");
    if (classes) s += "." + classes;
  }
  return s;
}

// --- Find the element ---
let el = null;
try {
  el = document.querySelector(SELECTOR);
} catch (e) {
  result.error = "Invalid selector: " + e.message;
  return JSON.stringify(result);
}

if (!el) {
  result.found = false;
  return JSON.stringify(result);
}

result.found = true;
result.tag = el.tagName.toLowerCase();

// --- Bounding rect ---
try {
  const rect = el.getBoundingClientRect();
  result.bounding_rect = {
    x: Math.round(rect.x),
    y: Math.round(rect.y),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
    top: Math.round(rect.top),
    right: Math.round(rect.right),
    bottom: Math.round(rect.bottom),
    left: Math.round(rect.left)
  };
} catch (e) { /* element may not have layout */ }

// --- Computed visibility ---
try {
  const style = window.getComputedStyle(el);
  result.computed_visibility = {
    display: style.display,
    visibility: style.visibility,
    opacity: style.opacity,
    overflow: style.overflow,
    "pointer-events": style.pointerEvents
  };

  const rect = el.getBoundingClientRect();
  const hasLayout = rect.width > 0 && rect.height > 0;
  const notHidden = style.display !== "none" && style.visibility !== "hidden" && parseFloat(style.opacity) > 0;
  const hasOffsetParent = !!el.offsetParent || style.position === "fixed" || style.position === "sticky" || el.tagName === "BODY";

  result.is_visible = hasLayout && notHidden && hasOffsetParent;
} catch (e) {
  result.is_visible = false;
}

// --- Obscured detection via elementFromPoint ---
try {
  const rect = el.getBoundingClientRect();
  if (rect.width > 0 && rect.height > 0) {
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    // Check if center point is within viewport
    if (cx >= 0 && cy >= 0 && cx <= window.innerWidth && cy <= window.innerHeight) {
      const topEl = document.elementFromPoint(cx, cy);
      if (topEl && topEl !== el && !el.contains(topEl)) {
        result.is_obscured = true;
        result.obscured_by = quickSelector(topEl);
      }
    }
  }
} catch (e) { /* elementFromPoint can fail in edge cases */ }

// --- Shadow DOM detection ---
try {
  let node = el;
  while (node) {
    const root = node.getRootNode();
    if (root instanceof ShadowRoot) {
      result.in_shadow_dom = true;
      result.shadow_host = quickSelector(root.host);
      break;
    }
    if (root === document) break;
    node = root.host || null;
  }
} catch (e) { /* shadow DOM walk failed */ }

// --- Parent chain ---
try {
  let current = el.parentElement;
  let depth = 0;
  while (current && current !== document.body && depth < 10) {
    result.parent_chain.push(quickSelector(current));
    current = current.parentElement;
    depth++;
  }
} catch (e) { /* parent walk failed */ }

// --- Attributes ---
try {
  const attrs = {};
  for (const attr of el.attributes) {
    // Skip very long attribute values (e.g., inline styles, data URIs)
    const val = attr.value.length > 200 ? attr.value.substring(0, 200) + "..." : attr.value;
    attrs[attr.name] = val;
  }
  result.attributes = attrs;
} catch (e) { /* attributes read failed */ }

// --- ARIA properties ---
try {
  const aria = {};
  for (const attr of el.attributes) {
    if (attr.name.startsWith("aria-")) {
      aria[attr.name] = attr.value;
    }
  }
  if (el.getAttribute("role")) aria.role = el.getAttribute("role");
  result.aria = aria;
} catch (e) { /* ARIA read failed */ }

// --- Input state (for form elements) ---
try {
  const tag = el.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") {
    const state = {};
    if (el.type !== "password") state.value = el.value || "";
    state.disabled = !!el.disabled;
    state.readOnly = !!el.readOnly;
    if (tag === "input" && (el.type === "checkbox" || el.type === "radio")) {
      state.checked = el.checked;
    }
    if (tag === "select") {
      state.selectedIndex = el.selectedIndex;
      state.selectedText = el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : "";
    }
    result.input_state = state;
  }
} catch (e) { /* input state read failed */ }

// --- Children summary ---
if (INCLUDE_CHILDREN) {
  try {
    const summary = {};
    for (const child of el.children) {
      const tag = child.tagName.toLowerCase();
      summary[tag] = (summary[tag] || 0) + 1;
    }
    result.children_summary = summary;
  } catch (e) { /* children walk failed */ }
}

// --- Event listeners (best effort via getEventListeners if available, or onclick-style detection) ---
if (INCLUDE_LISTENERS) {
  try {
    const listeners = [];
    // Check for inline event handlers
    const eventAttrs = ["onclick", "onchange", "onsubmit", "onfocus", "onblur", "onmouseover", "onmousedown", "onkeydown", "onkeyup", "oninput"];
    for (const attr of eventAttrs) {
      if (el[attr] || el.getAttribute(attr)) {
        listeners.push(attr.replace("on", ""));
      }
    }
    result.event_listeners = listeners;
  } catch (e) { /* listener detection failed */ }
}

return JSON.stringify(result);
