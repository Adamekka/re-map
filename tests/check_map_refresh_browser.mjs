// Delayed requests must not restore old item verdicts or stall live tracking.
// NODE_PATH=<runtime node_modules> bun tests/check_map_refresh_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chromium } from 'playwright';

assert(process.argv[2], 'Pass the Python executable used for tracker tests');
const setup = spawnSync(process.argv[2], ['-c', `
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from games.game_profile import RoomId
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import Tracker,ItemDetail
from ui.map_view import map_page,map_state
p=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json'))
t=Tracker(player_heading=90)
for number in (2,1):
    room=RoomId(0,number)
    t.mark_current(room)
    t.current_region='re2-00:'+str(number).zfill(2)
    t.region_visits[t.current_region]=str(room)
    t.update_room_items(room,0,0,True,False,False)
room=RoomId(0,1)
t.rooms[str(room)].items=(ItemDetail('Handgun ammo','available',15, True),)
t.update_room_items(room,1,0,True,True,False)
before=map_state(t)
t.rooms[str(room)].items=(ItemDetail('Handgun ammo','taken',15, True),)
t.update_room_items(room,1,1,True,False,False)
print(json.dumps({'document':map_page(p.map_layout.document).decode(),'before':before,'collected':map_state(t)}))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const fixture = JSON.parse(setup.stdout);
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const errors = [], reports = [];
  let requests = 0, held, aborted = false;
  page.on('pageerror', error => errors.push(error.message));
  page.on('requestfailed', request => {
    if (request === held?.request()) aborted = true;
  });
  await page.route('http://refresh.test/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: fixture.document });
    if (path === '/client-error') {
      reports.push(route.request().postDataJSON());
      return route.fulfill({ status: 204 });
    }
    assert.equal(path, '/state');
    requests++;
    if (requests === 2) { held = route; return; }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(requests === 1 ? fixture.before : fixture.collected) });
  });
  await page.goto('http://refresh.test/');
  await page.waitForFunction(() => document.getElementById('completion').textContent === 'Items remain');
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  const map = page.locator('#map');
  const chosenView = await map.getAttribute('viewBox');
  const neighbor = page.locator('.room:not(.current)');
  const selectedName = await neighbor.getAttribute('aria-label');
  await neighbor.press('Enter');
  await page.waitForFunction(() => document.getElementById('room-name').textContent !== "Kendo's Gun Shop");
  // Wait across several normal polling periods while the second request is held.
  await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 350)));
  assert.equal(requests, 2, 'only one state request may remain in flight');
  await page.waitForFunction(() => document.getElementById('completion').textContent === 'Tracking interrupted');
  assert.equal(await page.locator('#map .room').count(), 2, 'interruption must retain explored geometry');
  assert.equal(await page.locator('#map .current,#map .CLEARED,#map .INCOMPLETE,#map .player,#map .door').count(), 0);
  assert.equal(await page.locator('#items li,#doors li,#overview button').count(), 0, 'timeout must clear stale verdicts and navigation summaries');
  assert.equal(await map.getAttribute('viewBox'), chosenView);
  assert.equal(await page.locator('#status').textContent(), 'Map connection interrupted.');
  await page.waitForFunction(() => lastState?.status === 'display' && lastState.current_detail.items[0]?.state === 'taken');
  assert(aborted, 'a timed-out request must be aborted before polling resumes');
  assert.equal(await page.locator('#room-name').textContent(), selectedName, 'reconnection must retain the inspected room');
  assert.equal(await map.getAttribute('viewBox'), chosenView, 'reconnection must retain zoom and pan');
  assert.equal(await page.locator('#remaining-items .room-link').count(), 0);
  assert(reports.some(report => report.source === 'refresh' && report.message === 'Map state request timed out'));
  await held.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture.before) });
  await page.evaluate(() => new Promise(resolve => setTimeout(resolve, 150)));
  assert.equal(await page.locator('#remaining-items .room-link').count(), 0, 'a late expired response cannot restore a remaining pickup');
  assert.equal(await page.evaluate(() => lastState.current_detail.items[0].state), 'taken');
  await page.close();

  // A response body can stall after successful headers, so the same deadline
  // must remain active through JSON consumption rather than just fetch().
  const bodyPage = await browser.newPage();
  bodyPage.on('pageerror', error => errors.push(error.message));
  await bodyPage.route('http://body.test/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: fixture.document });
    if (path === '/client-error') return route.fulfill({ status: 204 });
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(fixture.before) });
  });
  await bodyPage.addInitScript(() => {
    const fetchState = window.fetch;
    let reads = 0;
    window.fetch = async (...args) => {
      const response = await fetchState(...args);
      if (args[0] === '/state' && ++reads === 2) {
        response.json = () => new Promise((resolve, reject) => {
          args[1].signal.addEventListener('abort', () => reject(args[1].signal.reason), { once: true });
        });
      }
      return response;
    };
  });
  await bodyPage.goto('http://body.test/');
  await bodyPage.waitForFunction(() => document.getElementById('completion').textContent === 'Items remain');
  await bodyPage.waitForFunction(() => document.getElementById('completion').textContent === 'Tracking interrupted');
  await bodyPage.waitForFunction(() => document.getElementById('completion').textContent === 'Items remain');
  assert.deepEqual(errors, []);
  console.log('Map refresh checks passed: serial requests, bounded headers/body waits, stale-result rejection, recovery, retained inspection and viewport.');
} finally {
  await browser.close();
}
