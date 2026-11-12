// bun tests/render_re2_readme_map.mjs <python> <explicit-publication-json> <output-dir>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import { mapHeaders } from './map_browser_response.mjs';

assert.equal(process.argv.length, 5, 'Pass Python, RE2 publication fixture and private output directory');
const result = spawnSync(process.argv[2], ['tests/test_re2_readme_map_fixture.py', resolve(process.argv[3])], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);
const fixture = JSON.parse(result.stdout);
const output = resolve(process.argv[4]);
mkdirSync(output, { recursive: true });
writeFileSync(resolve(output, 'publication.json'), JSON.stringify(fixture.state, null, 2) + '\n');
writeFileSync(resolve(output, 'map.html'), fixture.document);
const browser = await chromium.launch();
const report = { publication_sha256: fixture.publication_sha256, chromium: browser.version(), layouts: [] };
try {
  for (const [name, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }], ['tablet-portrait', { width: 768, height: 1024 }], ['tablet-landscape', { width: 1024, height: 768 }]]) {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1, locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce', isMobile: name === 'mobile', hasTouch: name !== 'desktop' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://re2-readme.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/') return route.fulfill({ headers: mapHeaders(fixture.document), contentType: 'text/html', body: fixture.document });
      if (path === '/state') return route.fulfill({ headers: mapHeaders(fixture.document), contentType: 'application/json', body: JSON.stringify(fixture.state) });
      errors.push(route.request().postDataJSON());
      return route.fulfill({ status: 204 });
    });
    await page.goto('http://re2-readme.test/');
    await page.waitForFunction(() => lastState?.status === 'display');
    await page.evaluate(() => document.fonts.ready);
    assert.deepEqual(await page.evaluate(() => lastState), fixture.state);
    assert.equal(await page.locator('#map .room').count(), Object.keys(fixture.visits.regions).length);
    assert.equal(await page.locator('#map .player').count(), 1);
    const screenshot = resolve(output, name + '.png');
    await page.screenshot({ path: screenshot, fullPage: true, animations: 'disabled' });
    for (const [area, visits] of Object.entries(fixture.state.explored_areas)) {
      await page.getByLabel('Floor', { exact: true }).selectOption(area);
      assert.deepEqual(await page.locator('#map .room').evaluateAll(nodes => nodes.map(n => n.dataset.region).sort()), visits.map(v => v.id).sort());
      for (const visit of visits) {
        // A room need not have remaining items to be a valid observed visit.
        const room = page.locator('#map .room[data-region="' + visit.id + '"]');
        await room.focus();
        await page.keyboard.press('Enter');
        assert.equal(await room.getAttribute('aria-label'), await page.locator('#room-name').textContent());
        assert.equal(await page.locator('#doors li').count(), fixture.state.doors.filter(d => d.source === visit.room).length);
        assert.equal(await page.locator('#items li').count(), visit.items.length);
      }
    }
    await page.getByRole('button', { name: 'Follow player', exact: true }).click();
    assert.equal(await page.locator('#room-id').textContent(), 'Room ' + fixture.state.current + ' · Current room');
    assert.deepEqual(await page.evaluate(() => lastState), fixture.state);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    assert.deepEqual(errors, []);
    report.layouts.push({ name, viewport, errors, overflow: false, screenshot_sha256: createHash('sha256').update(readFileSync(screenshot)).digest('hex') });
    await page.close();
  }
} finally {
  await browser.close();
}
writeFileSync(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('Observed-source RE2 README publication passed four layouts, keyboard inspection and exact-state preservation.');
