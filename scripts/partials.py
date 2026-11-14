"""HTML fragments injected into every page by build.py. Owned by the design side.
Must stay CSP-safe: no inline <script> code, no style="" attributes, no on* handlers."""

# Display settings bottom sheet. Opened by any [data-open-settings] button; wired up by
# site/settings.js, which also fills in the current values. Choices are native radio
# buttons (arrow keys and VoiceOver "1 of 3" for free); text size is a stepper.
SETTINGS_HTML = """<dialog class="sheet" id="settings" aria-labelledby="settings-title">
<div class="sheet-body">
  <div class="sheet-head">
    <h2 id="settings-title">Display</h2>
    <button type="button" class="sheet-done" data-close-settings>Done</button>
  </div>
  <div class="setting" role="group" aria-labelledby="set-size-label">
    <span class="setting-label" id="set-size-label">Text size</span>
    <div class="stepper">
      <button type="button" class="step" data-size-step="-1" aria-label="Decrease text size"><span class="glyph small" aria-hidden="true">A</span><span class="sign" aria-hidden="true">&#8722;</span></button>
      <span class="size-value" id="set-size-value" aria-live="polite">100%</span>
      <button type="button" class="step" data-size-step="1" aria-label="Increase text size"><span class="glyph large" aria-hidden="true">A</span><span class="sign" aria-hidden="true">+</span></button>
    </div>
  </div>
  <div class="setting" role="radiogroup" aria-labelledby="set-theme-label">
    <span class="setting-label" id="set-theme-label">Theme</span>
    <div class="seg">
      <label><input type="radio" name="mm-theme" value="system"><span>System</span></label>
      <label><input type="radio" name="mm-theme" value="light"><span>Light</span></label>
      <label><input type="radio" name="mm-theme" value="dark"><span>Dark</span></label>
    </div>
  </div>
  <div class="setting" role="radiogroup" aria-labelledby="set-font-label">
    <span class="setting-label" id="set-font-label">Typeface</span>
    <div class="seg">
      <label><input type="radio" name="mm-font" value="serif"><span class="face-serif">Serif</span></label>
      <label><input type="radio" name="mm-font" value="sans"><span class="face-sans">Sans</span></label>
    </div>
  </div>
  <div class="setting" role="radiogroup" aria-labelledby="set-spacing-label">
    <span class="setting-label" id="set-spacing-label">Line spacing</span>
    <div class="seg">
      <label><input type="radio" name="mm-spacing" value="normal"><span>Normal</span></label>
      <label><input type="radio" name="mm-spacing" value="relaxed"><span>Relaxed</span></label>
    </div>
  </div>
  <div class="sheet-foot">
    <button type="button" class="reset" data-reset-settings>Reset to defaults</button>
    <p class="sheet-note" id="settings-note">Saved on this device only. The Home Screen app and Safari keep separate settings.</p>
  </div>
</div>
</dialog>"""
