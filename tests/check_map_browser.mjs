// Run with Bun, Playwright and Chromium installed: bun tests/check_map_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

assert(process.argv[2], 'Pass the Python executable used for the tracker tests');
const setup = spawnSync(process.argv[2], ['-c', `
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))
from games.game_profile import RoomId
from tracker.exploration_state import Tracker, ItemDetail, DoorDetail
from ui.map_view import map_page, map_state

tracker = Tracker()
def enter(stage, room, area, region, outlined=True):
    rid = RoomId(stage, room)
    tracker.mark_current(rid)
    tracker.current_region = area + ':' + region
    if outlined:
        tracker.region_visits[tracker.current_region] = str(rid)

enter(0, 9, 'mansion1f', '09')
tracker.update_room_items(RoomId(0, 9), 1, 0, True, True, False)
tracker.rooms['00-09'].items = (
    ItemDetail('Green Herb', 'available', 1),
    ItemDetail('Red Herb', 'taken', 1),
    ItemDetail('Battery', 'unavailable', 1),
)
tracker.rooms['00-09'].reason = 'One item remains.'
tracker.rooms['00-09'].door_reason = 'Door is locked.'
tracker.doors = (DoorDetail(RoomId(0, 9), RoomId(0, 8), 'LOCKED', 'Locked'),)
enter(1, 3, 'mansion2f', '03')
states = {'initial': map_state(tracker)}
tracker.rooms['00-09'].list_complete = False
tracker.rooms['00-09'].reason = 'Other item conditions remain unresolved.'
states['partial'] = map_state(tracker)
tracker.rooms['00-09'].list_complete = True
tracker.rooms['00-09'].reason = 'One item remains.'
enter(3, 0, 'guardhouse1f', '00')
states['crossing'] = map_state(tracker)
tracker.update_room_items(RoomId(0, 9), 1, 1, True, False, False)
tracker.rooms['00-09'].items = (ItemDetail('Green Herb', 'taken', 1),)
tracker.rooms['00-09'].reason = 'All available items collected.'
tracker.rooms['00-09'].door_reason = 'Door is unlocked.'
tracker.doors = (DoorDetail(RoomId(0, 9), RoomId(0, 8), 'OPEN', 'Unlocked'),)
states['collected'] = map_state(tracker)
tracker.update_room_items(RoomId(0, 9), 1, 0, True, True, False)
tracker.rooms['00-09'].items = (ItemDetail('Green Herb', 'available', 1),)
tracker.rooms['00-09'].reason = 'One item remains.'
states['rewound'] = map_state(tracker)
tracker = Tracker()
enter(1, 3, 'mansion2f', '03')
states['new_history'] = map_state(tracker)
enter(4, 0x15, 'laboratoryb4', '15', outlined=False)
states['unoutlined'] = map_state(tracker)
tracker = Tracker()
enter(5, 0x10, 'mansionb1', '1E')
enter(5, 0x10, 'mansion1f', '10')
tracker.update_room_items(RoomId(5, 0x10), 1, 0, True, True, False)
tracker.rooms['05-10'].items = (ItemDetail('Green Herb', 'available', 1),)
states['camera_alias'] = map_state(tracker)
catalog = json.loads(Path('data/floor_plans_slus00551.json').read_text())
# Explicit test exploration checks label placement across every native outline.
tracker = Tracker()
for plan in catalog['areas']:
    for region in plan['rooms']:
        stage, room = region['room_ids'][0].split('-')
        enter(int(stage), int(room, 16), plan['id'], region['id'])
states['labels'] = map_state(tracker)
document = map_page(catalog).decode()
print(json.dumps({'document': document, 'states': states}))
`], {
  cwd: fileURLToPath(new URL('..', import.meta.url)),
  encoding: 'utf8',
});
assert.equal(setup.status, 0, setup.stderr);
const { document, states } = JSON.parse(setup.stdout);
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let state = states.initial;
  // Explicit test responses exercise the production page without booting a game.
  await page.route('http://map.test/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: document });
    if (path === '/state') return route.fulfill({ contentType: 'application/json', body: JSON.stringify(state) });
    errors.push('Unexpected request: ' + path);
    return route.fulfill({ status: 404 });
  });
  await page.goto('http://map.test/');
  const floor = page.getByLabel('Floor', { exact: true });
  const current = page.getByRole('button', { name: 'Current room', exact: true });
  const remaining = page.locator('#remaining-items');
  const checks = page.locator('#incomplete-checks');
  await page.waitForFunction(() => document.getElementById('floor').value === 'mansion2f');
  assert.equal(await page.locator('#map .room text').count(), 1, 'names must not reveal unvisited rooms');
  assert.equal(await page.locator('#map .room text').textContent(), 'Main Hall 2F');
  assert.match(await remaining.textContent(), /Mansion · 1FWinding PassageGreen Herb/);
  assert.doesNotMatch(await remaining.textContent(), /Red Herb|Battery|Main Hall/);
  assert.match(await checks.textContent(), /Main Hall 2F/);
  assert.doesNotMatch(await checks.textContent(), /Winding Passage/);
  const remainingLink = remaining.getByRole('button', { name: /^Winding Passage/ });
  await remainingLink.focus();
  const focusedLink = await remainingLink.elementHandle();
  await page.waitForTimeout(1100);
  assert(await focusedLink.evaluate(element => element.isConnected && element === document.activeElement), 'unchanged polling must preserve focused overview links');
  await page.keyboard.press('Enter');
  assert.equal(await floor.inputValue(), 'mansion1f');
  assert.equal(await page.locator('#room-id').textContent(), 'Room 00-09');
  assert.equal(await page.locator('.room.selected').count(), 1);
  await current.click();
  state = states.partial;
  await page.waitForFunction(() => document.getElementById('incomplete-checks').textContent.includes('Winding Passage'));
  assert.match(await remaining.textContent(), /Green Herb/);
  state = states.initial;
  await page.waitForFunction(() => !document.getElementById('incomplete-checks').textContent.includes('Winding Passage'));
  assert.deepEqual(await floor.locator('option').evaluateAll(options => options.map(option => option.value)), ['mansion1f', 'mansion2f']);
  await page.locator('#map').getByRole('button', { name: 'Main Hall 2F', exact: true }).click();
  assert(!(await current.isDisabled()));
  state = states.crossing;
  await page.waitForFunction(() => document.getElementById('floor').value === 'guardhouse1f');
  assert(await current.isDisabled(), 'following a new floor must clear the old room selection before updating controls');
  state = states.initial;
  await page.waitForFunction(() => document.getElementById('floor').value === 'mansion2f');
  await floor.selectOption('mansion1f');
  assert.equal(await page.locator('#room-id').textContent(), 'Room 00-09');
  assert.equal(await page.locator('.room').count(), 1);
  assert.equal(await page.locator('.room text').locator('tspan').allTextContents().then(lines => lines.join(' ')), 'Winding Passage');
  assert.equal(await page.locator('.room.current').count(), 0);
  assert.equal(await page.locator('.door.LOCKED').count(), 1);
  assert.match(await page.locator('#items').textContent(), /Green HerbRemaining/);
  const option = await floor.locator('option').first().elementHandle();
  await page.waitForTimeout(1100);
  assert(await option.evaluate(element => element.isConnected), 'unchanged polling must preserve select options');

  state = states.crossing;
  await page.waitForFunction(() => document.querySelectorAll('#floor option').length === 3);
  assert.equal(await floor.inputValue(), 'mansion1f');
  await current.click();
  assert.equal(await floor.inputValue(), 'guardhouse1f');
  assert.equal(await page.locator('.room.current').count(), 1);
  await floor.selectOption('mansion1f');
  state = states.collected;
  await page.waitForFunction(() => document.getElementById('items').textContent.includes('Green HerbCollected'));
  assert.equal(await remaining.getByRole('button').count(), 0);
  assert.equal(await page.locator('#remaining-status').textContent(), 'No known remaining items.');
  assert.match(await checks.textContent(), /Guardhouse/);
  assert.match(await page.locator('#doors').textContent(), /Unlocked/);
  assert.equal(await page.locator('.door.OPEN').count(), 1);
  state = states.rewound;
  await page.waitForFunction(() => document.getElementById('items').textContent.includes('Remaining'));
  assert.match(await remaining.textContent(), /Green Herb/);

  state = { status: 'waiting', error: 'Test connection interruption' };
  await page.waitForFunction(() => document.getElementById('floor').disabled);
  assert(await current.isDisabled());
  assert.equal(await page.locator('.room.CLEARED,.room.INCOMPLETE,.room.current,.door').count(), 0);
  assert.equal(await page.locator('#items li,#doors li').count(), 0);
  assert.equal(await page.locator('#note').textContent(), '', 'interruption must clear stale verdict explanations');
  assert.equal(await page.locator('#overview button').count(), 0);
  assert.equal(await page.locator('#remaining-status').textContent(), 'Tracking interrupted.');
  state = states.collected;
  await page.waitForFunction(() => !document.getElementById('floor').disabled);
  assert.equal(await floor.inputValue(), 'mansion1f');
  assert.match(await page.locator('#items').textContent(), /Collected/);

  state = states.new_history;
  await page.waitForFunction(() => document.getElementById('floor').value === 'mansion2f');
  assert.equal(await page.locator('.room').count(), 1);
  assert.doesNotMatch(await remaining.textContent(), /Green Herb|Winding Passage/);
  state = states.unoutlined;
  await page.waitForFunction(() => document.getElementById('floor').value === 'laboratoryb4');
  assert.equal(await page.locator('.room').count(), 0);
  assert.match(await page.locator('#room-id').textContent(), /04-15.*Current room/);
  const unoutlinedLink = checks.getByRole('button', { name: 'Elevator B3/B4', exact: true });
  assert(await unoutlinedLink.isVisible());
  await floor.selectOption('mansion2f');
  assert.equal(await page.locator('.room.current').count(), 0);
  await unoutlinedLink.click();
  assert.equal(await floor.inputValue(), 'laboratoryb4');
  assert.match(await page.locator('#room-id').textContent(), /04-15.*Current room/);
  assert.equal(await page.locator('.room').count(), 0);
  await current.click();

  state = states.camera_alias;
  await page.waitForFunction(() => document.getElementById('floor').value === 'mansion1f');
  assert.equal(await remaining.getByRole('button').count(), 1, 'camera aliases must not duplicate a logical room\'s items');
  assert.equal(await checks.getByRole('button').count(), 0);
  assert.equal(await page.locator('#checks-status').textContent(), 'No incomplete item checks.');
  await floor.selectOption('mansionb1');
  assert.equal(await page.locator('.room.current').count(), 0);
  assert.equal(await page.locator('#room-id').textContent(), 'Room 05-10');
  await current.click();
  assert.equal(await page.locator('.room.current').count(), 1);
  state = states.labels;
  const labelCount = await page.evaluate(fixture => {
    let count = 0;
    floorView = { mode: 'follow' };
    selected = null;
    for (const plan of catalog.areas) {
      const visits = fixture.explored_areas[plan.id];
      // Every outline is checked as current too, since bold names need more room.
      for (const visit of visits) {
        draw({ ...fixture, area: plan.id, map_region: visit.id, current: visit.room, current_detail: visit, rooms: visits });
        const group = document.querySelector('.room.current');
        const text = group.querySelector('text');
        const name = [...text.querySelectorAll('tspan')].map(span => span.textContent).join(' ');
        if (name !== group.getAttribute('aria-label')) throw new Error('Missing visible room name: ' + name);
        const outline = group.querySelector('path');
        const matrix = outline.getCTM().inverse().multiply(text.getCTM());
        // Check actual glyph rectangles, independently of the layout's box scan.
        for (const span of text.querySelectorAll('tspan')) {
          for (let index = 0; index < span.getNumberOfChars(); index++) {
            const box = span.getExtentOfChar(index);
            for (const x of [box.x, box.x + box.width / 2, box.x + box.width]) {
              for (const y of [box.y, box.y + box.height / 2, box.y + box.height]) {
                const point = new DOMPoint(x, y).matrixTransform(matrix);
                if (!outline.isPointInFill(point)) throw new Error('Room name crosses its wall: ' + name);
              }
            }
          }
        }
        count++;
      }
    }
    return count;
  }, states.labels);
  assert(labelCount > 100, 'label checks must cover all floor plans');
  assert.deepEqual(errors, []);
  console.log('Browser checks passed: room names on ' + labelCount + ' outlines, floor browsing, remaining-items overview and navigation, incomplete checks, fresh state, interruption, new history, unoutlined rooms and camera aliases.');
} finally {
  await browser.close();
}
