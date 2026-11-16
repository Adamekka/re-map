// bun tests/render_readme_screenshots.mjs <python> tests/fixtures/re1/readme-screenshots.json
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { mapHeaders } from './map_browser_response.mjs';

assert.equal(process.argv.length, 4, 'Pass <python> <fixture-json>');
const root = fileURLToPath(new URL('..', import.meta.url));
const [python, fixturePath] = process.argv.slice(2);
const replay = spawnSync(python, ['tests/test_readme_screenshots.py', resolve(fixturePath)], { cwd: root, encoding: 'utf8', maxBuffer: 64 << 20 });
assert.equal(replay.status, 0, replay.stderr || replay.error?.message);
const { document: html, state } = JSON.parse(replay.stdout);
const headers = mapHeaders(html);
const { screenshots } = JSON.parse(readFileSync(resolve(fixturePath), 'utf8'));
const browser = await chromium.launch();
try {
  for (const shot of screenshots) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1, locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    // Intercept the real page's requests instead of opening a server or
    // connecting to a running tracker.
    await page.route('http://readme-map.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/') return route.fulfill({ headers, contentType: 'text/html', body: html });
      if (path === '/state') return route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(state) });
      errors.push(path === '/client-error' ? route.request().postDataJSON() : 'Unexpected request: ' + path);
      return route.fulfill({ status: 404 });
    });
    await page.goto('http://readme-map.test/');
    await page.waitForFunction(() => lastState?.status === 'display' && !document.getElementById('floor').disabled);
    if (shot.view === 'inspect') {
      await page.locator('#remaining-items .room-link[data-room="' + shot.room + '"]').click();
      assert.match(await page.locator('#room-id').textContent(), new RegExp('^Room ' + shot.room));
      // The click leaves a keyboard focus ring on the room, which reads as
      // clutter in a still image; the selection outline remains.
      await page.evaluate(() => document.activeElement.blur());
    } else {
      assert.equal(shot.view, 'follow');
      assert.equal(await page.locator('#current-room').getAttribute('aria-pressed'), 'true');
    }
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: resolve(root, shot.path), animations: 'disabled' });
    assert.deepEqual(errors, [], shot.path + ': browser/client errors');
    console.log('Wrote ' + shot.path);
    await page.close();
  }
} finally {
  await browser.close();
}
