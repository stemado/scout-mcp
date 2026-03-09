"""Take a screenshot of the showcase page mid-demo for the README hero image."""
import time
from botasaurus_driver import Driver

JS_SETUP = """
(function() {
  engine.stop();

  document.getElementById('browser-url').textContent = 'benefits.example.com/dashboard';

  var dashHTML = '<div class="sim-portal-header">'
    + '<span class="portal-title">Benefits Portal</span>'
    + '<span class="portal-user">admin@corp.com</span>'
    + '</div>'
    + '<div class="sim-nav">'
    + '<span>Home</span><span>Employees</span><span class="active">Reports</span><span>Settings</span>'
    + '</div>'
    + '<table class="sim-table"><thead><tr><th>Report</th><th>Period</th><th>Status</th></tr></thead>'
    + '<tbody>'
    + '<tr><td style="color:var(--cyan);">Enrollment Summary</td><td>Feb 2026</td><td><span class="ok">Ready</span></td></tr>'
    + '<tr><td>Claims Detail</td><td>Feb 2026</td><td><span class="yellow">Pending</span></td></tr>'
    + '</tbody></table>';

  document.getElementById('browser-content').innerHTML = dashHTML;
  document.getElementById('browser-content').style.opacity = '1';

  document.getElementById('user-input').innerHTML =
    'Log into the benefits portal, go to Reports, and export this month\\u2019s enrollment CSV'
    + '<span class="cursor"></span>';

  var resp = document.getElementById('hero-response');
  resp.innerHTML = '';

  function addLine(html) {
    var d = document.createElement('div');
    d.className = 'response-line visible';
    d.innerHTML = html;
    resp.appendChild(d);
  }

  addLine('<span class="dim">I\\'ll scout the login page first.</span>');

  addLine('<div class="tool-box"><div class="tool-box-header">scout_page_tool</div>'
    + '<div class="tool-row"><span class="key">page:</span> <span class="str">Benefits Portal \\u2014 Login</span></div>'
    + '<div class="tool-row"><span class="key">iframes:</span> <span class="val">1 <span class="dim">(vendor-sso.okta.com)</span></span></div>'
    + '<div class="tool-row"><span class="key">elements:</span> <span class="val">input: 2, button: 1</span></div>'
    + '</div>');

  addLine('<span class="dim">Login form is inside an iframe. I see the fields.</span>');

  addLine('<div class="tool-box"><div class="tool-box-header">fill_secret</div>'
    + '<div class="tool-row"><span class="key">env_var:</span> <span class="str">"PORTAL_PASSWORD"</span></div>'
    + '<div class="tool-row"><span class="key">chars_typed:</span> <span class="val">18</span></div>'
    + '<div class="tool-callout"><span class="yellow">Password value: never in conversation</span></div>'
    + '</div>');

  addLine('<div class="tool-box"><div class="tool-box-header">execute_action_tool</div>'
    + '<div class="tool-row"><span class="key">action:</span> <span class="str">"click"</span></div>'
    + '<div class="tool-row"><span class="key">target:</span> <span class="str">"Enrollment Summary"</span></div>'
    + '</div>');

  document.getElementById('replay-btn').classList.remove('visible');
  window.scrollTo(0, 0);

  return 'done';
})();
"""

from PIL import Image

driver = Driver(headless=True, window_size=(1280, 800))
try:
    driver.get("https://stemado.github.io/otto/showcase.html")
    time.sleep(4)
    driver.run_js(JS_SETUP)
    time.sleep(0.5)
    driver.save_screenshot("assets/demo-showcase-full.png")

    # Crop to viewport (top 800px at whatever DPR the screenshot uses)
    img = Image.open("assets/demo-showcase-full.png")
    w, h = img.size
    # Assume the viewport is 1280x800 CSS px; the screenshot width tells us the DPR
    dpr = w / 1280
    crop_h = int(800 * dpr)
    cropped = img.crop((0, 0, w, crop_h))
    cropped.save("assets/demo-showcase.png")
    print(f"Cropped to {cropped.size[0]}x{cropped.size[1]} (DPR={dpr})")

    import os
    os.remove("assets/demo-showcase-full.png")
finally:
    driver.close()
