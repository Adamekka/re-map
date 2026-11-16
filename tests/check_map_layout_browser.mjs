// Run with Bun, Playwright and Chromium installed: bun tests/check_map_layout_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { mapHeaders } from './map_browser_response.mjs';

assert(process.argv[2], 'Pass the Python executable used for the tracker tests');
const root = fileURLToPath(new URL('..', import.meta.url));
const replay = spawnSync(process.argv[2], ['tests/test_readme_map_fixture.py', resolve(root, 'tests/fixtures/re1/readme-map.json')], { cwd: root, encoding: 'utf8' });
assert.equal(replay.status, 0, replay.stderr || replay.error?.message);
const fixture = JSON.parse(replay.stdout);
const headers = mapHeaders(fixture.document);
assert.equal(fixture.state.current, '00-07', 'layout checks expect the README fixture to start in the Art Room');

const browser = await chromium.launch();
try {
  async function openMap(viewport) {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();
    const run = { context, page, state: fixture.state, errors: [] };
    page.on('pageerror', error => run.errors.push(error.message));
    await page.route('http://layout-map.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/') return route.fulfill({ headers, contentType: 'text/html', body: fixture.document });
      if (path === '/state') return route.fulfill({ headers, contentType: 'application/json', body: JSON.stringify(run.state) });
      run.errors.push(path === '/client-error' ? route.request().postDataJSON() : 'Unexpected request: ' + path);
      return route.fulfill({ status: 404 });
    });
    run.load = async () => {
      await page.goto('http://layout-map.test/');
      await page.waitForFunction(() => lastState?.status === 'display' && !document.getElementById('floor').disabled);
    };
    await run.load();
    return run;
  }
  const sideBySide = page => page.evaluate(() => {
    const map = document.getElementById('map').getBoundingClientRect(), aside = document.querySelector('aside').getBoundingClientRect();
    return aside.left >= map.right - 1 && aside.top < map.bottom && document.documentElement.scrollHeight <= innerHeight;
  });
  const sidebarScroll = page => page.locator('aside').evaluate(node => node.scrollTop);

  // Wide windows, including short ones beside the emulator, keep the details beside a full-height map.
  for (const viewport of [{ width: 1280, height: 720 }, { width: 1280, height: 480 }]) {
    const { context, page, errors } = await openMap(viewport);
    assert(await sideBySide(page), JSON.stringify(viewport) + ': sidebar must sit beside the map without page scrolling');
    assert.deepEqual(errors, []);
    await context.close();
  }

  const desktop = await openMap({ width: 1280, height: 600 });
  const { page } = desktop;
  assert.equal(await page.locator('#status').getAttribute('data-state'), 'live');
  const badge = page.locator('#completion');
  assert.equal(await badge.getAttribute('data-state'), 'INCOMPLETE');
  assert.equal(await badge.getAttribute('data-story-items'), null, 'the Art Room has no remaining story item');
  const storeroom = page.locator('#remaining-items .room-link[data-room="00-18"]');
  assert.equal(await storeroom.locator('.result-item.story').textContent(), 'Chemical');
  assert.equal(await storeroom.locator('.result-item.story svg.list-symbol').count(), 1, 'remaining items need their category symbol');
  await storeroom.click();
  assert.equal(await badge.getAttribute('data-story-items'), '', 'a remaining story item must use the story badge');

  // Inspection reveals room details; Back returns to the earlier place in the sidebar list.
  await page.getByRole('button', { name: 'Follow player', exact: true }).click();
  const terrace = page.locator('#remaining-items .room-link[data-room="01-12"]');
  await terrace.scrollIntoViewIfNeeded();
  const scrolled = await sidebarScroll(page);
  assert(scrolled > 0, 'the last result must be below the sidebar fold');
  await terrace.click();
  assert.equal(await sidebarScroll(page), 0, 'a result must reveal the inspected room details');
  await page.getByRole('button', { name: 'Back to previous room', exact: true }).click();
  assert.equal(await page.locator('#room-id').textContent(), 'Room 00-07 · Current room');
  assert.equal(await sidebarScroll(page), scrolled, 'Back must restore the sidebar position');
  await page.locator('aside').evaluate(node => { node.scrollTop = node.scrollHeight; });
  assert(await sidebarScroll(page) > 0);
  await page.locator('#map .room[data-region="09"]').dispatchEvent('click');
  assert.match(await page.locator('#room-id').textContent(), /^Room 00-09/);
  assert.equal(await sidebarScroll(page), 0, 'selecting a room on the map must reveal its details');

  // Interruption clears live verdicts from the status dot and the badge.
  await storeroom.click();
  desktop.state = { status: 'waiting', error: 'Game connection interrupted.' };
  await page.waitForFunction(() => document.getElementById('completion').textContent === 'Tracking interrupted');
  assert.equal(await page.locator('#status').getAttribute('data-state'), 'paused');
  assert.equal(await badge.getAttribute('data-state'), 'UNKNOWN');
  assert.equal(await badge.getAttribute('data-story-items'), null, 'an interrupted badge must not keep the story color');
  assert.deepEqual(desktop.errors, []);
  await desktop.context.close();

  // The legend starts open beside a wide map, collapsed above stacked details, and keeps the viewer's choice.
  const narrow = await openMap({ width: 390, height: 844 });
  assert.equal(await narrow.page.locator('#legend').evaluate(node => node.open), false);
  await narrow.context.close();
  const wide = await openMap({ width: 1280, height: 720 });
  const legend = wide.page.locator('#legend');
  assert.equal(await legend.evaluate(node => node.open), true);
  await legend.locator('summary').click();
  assert.equal(await legend.evaluate(node => node.open), false);
  await wide.load();
  assert.equal(await legend.evaluate(node => node.open), false, 'a collapsed legend must stay collapsed after reload');
  assert.deepEqual(wide.errors, []);
  await wide.context.close();
} finally {
  await browser.close();
}
console.log('Map layout checks passed: side-by-side sidebar, status and completion badges, item symbols, sidebar reveal and Back restore, legend preference.');
