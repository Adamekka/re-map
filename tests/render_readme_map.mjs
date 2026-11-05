// bun tests/render_readme_map.mjs <python> tests/fixtures/re1/readme-map.json <output-dir>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { mapHeaders } from './map_browser_response.mjs';

assert.equal(process.argv.length, 5, 'Pass <python> <fixture-json> <output-dir>');
const root = fileURLToPath(new URL('..', import.meta.url));
const [python, fixturePath, outputDirectory] = process.argv.slice(2);
const output = resolve(outputDirectory);
const replay = () => {
  const result = spawnSync(python, ['tests/test_readme_map_fixture.py', resolve(fixturePath)], { cwd: root, encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return JSON.parse(result.stdout);
};
const fixture = replay();
const publication = JSON.stringify(fixture.state);
const headers = mapHeaders(fixture.document);
mkdirSync(output, { recursive: true });
writeFileSync(resolve(output, 'map.html'), fixture.document);
writeFileSync(resolve(output, 'publication.json'), JSON.stringify(fixture.state, null, 2) + '\n');
writeFileSync(resolve(output, 'visits.json'), JSON.stringify(fixture.visits, null, 2) + '\n');
const layouts = [
  ['desktop', { width: 1440, height: 1000 }],
  ['mobile', { width: 390, height: 844 }],
  ['tablet-portrait', { width: 768, height: 1024 }],
  ['tablet-landscape', { width: 1024, height: 768 }],
];
const report = { publication_sha256: fixture.publication_sha256, inputs_sha256: fixture.inputs_sha256, layouts: [] };
const browser = await chromium.launch();
try {
  report.chromium = browser.version();
  for (const [name, viewport] of layouts) {
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1, locale: 'en-US', timezoneId: 'UTC', reducedMotion: 'reduce', isMobile: name === 'mobile', hasTouch: name !== 'desktop' });
    const errors = [];
    let stateRequests = 0;
    page.on('pageerror', error => errors.push(error.message));
    // Intercept the real page's requests instead of opening a server or
    // connecting to a running tracker. The publication is immutable here.
    await page.route('http://readme-map.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/') return route.fulfill({ headers, contentType: 'text/html', body: fixture.document });
      if (path === '/state') {
        stateRequests++;
        return route.fulfill({ headers, contentType: 'application/json', body: publication });
      }
      errors.push(path === '/client-error' ? route.request().postDataJSON() : 'Unexpected request: ' + path);
      return route.fulfill({ status: 404 });
    });
    await page.goto('http://readme-map.test/');
    await page.waitForFunction(() => lastState?.status === 'display' && !document.getElementById('floor').disabled);
    await page.evaluate(() => document.fonts.ready);
    assert.deepEqual(await page.evaluate(() => lastState), fixture.state);
    assert.equal(await page.locator('#room-id').textContent(), 'Room ' + fixture.state.current + ' · Current room');
    assert.equal(await page.locator('#map .player').count(), 1);
    assert.equal(await page.locator('#current-room').getAttribute('aria-pressed'), 'true');
    const overflow = () => page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
    assert.equal(await overflow(), false, name + ': horizontal overflow');
    const screenshot = resolve(output, 're1-readme-' + name + '.png');
    await page.screenshot({ path: screenshot, fullPage: true, animations: 'disabled' });

    for (const [area, visits] of Object.entries(fixture.state.explored_areas)) {
      await page.getByLabel('Floor', { exact: true }).selectOption(area);
      assert.deepEqual(await page.locator('#map .room').evaluateAll(nodes => nodes.map(node => node.dataset.region).sort()), visits.map(visit => visit.id).sort(), name + ': only observed outlines may render');
      for (const visit of visits) {
        // All fixture rooms have a remaining item, so the production overview
        // gives each room a pointer/touch target even on the narrow layout.
        const link = page.locator('#remaining-items .room-link[data-room="' + visit.room + '"]');
        if (name === 'desktop') await link.click();
        else await link.tap();
        assert.match(await page.locator('#room-id').textContent(), new RegExp('^Room ' + visit.room));
        assert.equal(await page.locator('#map .room.selected').getAttribute('data-region'), visit.id);
        const room = page.locator('#map .room[data-region="' + visit.id + '"]');
        assert.equal(await room.getAttribute('tabindex'), '0');
        assert((await room.locator('text').textContent()).trim(), name + ': room needs a visible label');
        for (const item of visit.items) assert((await page.locator('#items').textContent()).includes(item.label));
        assert.equal(await page.locator('#doors li').count(), fixture.state.doors.filter(door => door.source === visit.room).length);
        await page.locator('#room-name').scrollIntoViewIfNeeded();
        const details = await page.locator('aside').boundingBox();
        assert(details.width >= 240 && details.x >= 0 && details.x + details.width <= viewport.width, name + ': room details must fit');
        assert.equal(await overflow(), false, name + ': overflow after room navigation');
      }
    }
    await page.getByRole('button', { name: 'Follow player', exact: true }).click();
    assert.equal(await page.getByLabel('Floor', { exact: true }).inputValue(), fixture.state.area);
    assert.equal(await page.locator('#map .room.selected').getAttribute('data-region'), fixture.state.map_region);
    await page.waitForFunction(() => lastState?.status === 'display');
    assert.deepEqual(await page.evaluate(() => lastState), fixture.state, name + ': rendering/navigation changed the publication');
    assert.deepEqual(errors, [], name + ': browser/client errors');
    assert(stateRequests > 0);
    report.layouts.push({ name, viewport, state_requests: stateRequests, page_errors: errors, horizontal_overflow: await overflow(), screenshot, screenshot_sha256: createHash('sha256').update(readFileSync(screenshot)).digest('hex') });
    await page.close();
  }
} finally {
  await browser.close();
}
// Replaying again checks exact visits, all source bytes and the full
// publication after browser rendering, including departed-room verdicts.
assert.deepEqual(replay(), fixture, 'Rendering changed replay inputs, publication or visits');
report.publication_and_visits_unchanged = true;
writeFileSync(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('README map rendered; four layouts, room details, exact publication and visits passed. Report: ' + resolve(output, 'report.json'));
