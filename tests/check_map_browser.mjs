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
    tracker.player_heading = 90.0
    tracker.current_region = area + ':' + region
    if outlined:
        tracker.region_visits[tracker.current_region] = str(rid)

enter(0, 9, 'mansion1f', '09')
tracker.update_room_items(RoomId(0, 9), 1, 0, True, True, False)
tracker.rooms['00-09'].items = (
    ItemDetail('Green Herb', 'available', 1, False),
    ItemDetail('Sun Crest', 'uncollected', 1, False),
    ItemDetail('Red Herb', 'taken', 1, False),
    ItemDetail('Battery', 'unavailable', 1, False),
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
tracker.rooms['00-09'].items = (ItemDetail('Green Herb', 'taken', 1, False),)
tracker.rooms['00-09'].reason = 'All available items collected.'
tracker.rooms['00-09'].door_reason = 'Door is unlocked.'
tracker.doors = (DoorDetail(RoomId(0, 9), RoomId(0, 8), 'OPEN', 'Unlocked'),)
states['collected'] = map_state(tracker)
tracker.update_room_items(RoomId(0, 9), 1, 0, True, True, False)
tracker.rooms['00-09'].items = (ItemDetail('Green Herb', 'available', 1, False),)
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
tracker.rooms['05-10'].items = (ItemDetail('Green Herb', 'available', 1, False),)
states['camera_alias'] = map_state(tracker)
tracker = Tracker()
enter(0, 9, 'mansion1f', '09')
enter(1, 3, 'mansion2f', '03')
enter(0, 5, 'mansion1f', '05')
states['expanded'] = map_state(tracker)
tracker = Tracker()
enter(0, 10, 'mansion1f', '0A')
enter(1, 11, 'mansion2f', '0B')
# RE1-MAP-018: original-stage doors can target returned-Mansion outline aliases.
tracker.doors = (
    DoorDetail(RoomId(0, 10), RoomId(0, 25), 'LOCKED', 'Locked · Helmet Key', key_label='Helmet Key'),
    DoorDetail(RoomId(1, 11), RoomId(1, 12), 'LOCKED', 'Locked · Helmet Key', key_label='Helmet Key'),
)
states['helmet_doors'] = map_state(tracker)
tracker.doors = tuple(DoorDetail(d.source, d.target, 'OPEN', 'Unlocked', key_label=d.key_label) for d in tracker.doors)
states['helmet_unlocked'] = map_state(tracker)
tracker = Tracker()
for room in (3, 0x0e, 9, 0x15, 0x0c):
    enter(0, room, 'mansion1f', f'{room:02X}')
# RE1-MAP-021: both sides are open despite different lock descriptions.
tracker.doors = (
    DoorDetail(RoomId(0, 3), RoomId(0, 0x0e), 'OPEN', 'Unlocked', key_label='Sword Key'),
    DoorDetail(RoomId(0, 0x0e), RoomId(0, 3), 'OPEN', 'No lock'),
    DoorDetail(RoomId(0, 9), RoomId(0, 0x15), 'OPEN', 'No lock'),
    DoorDetail(RoomId(0, 0x15), RoomId(0, 9), 'OPEN', 'Unlocked'),
)
states['open_door_descriptions'] = map_state(tracker)
tracker.doors = tuple(DoorDetail(d.source, d.target, 'LOCKED', 'Locked', key_label=d.key_label) for d in tracker.doors)
states['locked_door_descriptions'] = map_state(tracker)
tracker = Tracker()
enter(3, 0, 'guardhouse1f', '00')
states['before_room002'] = map_state(tracker)
enter(3, 6, 'guardhouse1f', '06')
states['room002'] = map_state(tracker)
catalog = json.loads(Path('data/floor_plans_slus00551.json').read_text())
upper = next(area for area in catalog['areas'] if area['id'] == 'mansion2f')
point = next(room['label'] for room in upper['rooms'] if room['id'] == '03')
states['position'] = {**states['initial'], 'player_position': {'kind': 'approximate', 'point': point}}
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
  const current = page.getByRole('button', { name: 'Follow player', exact: true });
  const remaining = page.locator('#remaining-items');
  const checks = page.locator('#incomplete-checks');
  await page.waitForFunction(() => document.getElementById('floor').value === 'mansion2f');
  assert.equal(await page.locator('#map .room text').count(), 1, 'names must not reveal unvisited rooms');
  assert.equal(await page.locator('#map .room text').textContent(), 'Main Hall 2F');
  assert.equal(await page.locator('.player').getAttribute('aria-label'), 'You · Main Hall 2F');
  assert.equal(await page.locator('#key-legend').count(), 0);
  assert.match(await page.locator('#legend').textContent(), /Check incomplete/);
  assert.equal(await page.locator('#map .room.UNKNOWN').count(), 1, 'an unresolved room must keep its explicit state');
  const initialRoom = await page.locator('.room.current').elementHandle();
  for (const heading of [0, 90, 180, 270]) {
    state = { ...states.initial, player_heading: heading };
    await page.waitForFunction(heading => document.querySelector('.player path')?.getAttribute('transform').includes('rotate(' + heading + ')'), heading);
    assert(await initialRoom.evaluate(node => node.isConnected), 'turning must preserve room controls');
  }
  state = states.initial;
  await page.waitForFunction(() => document.querySelector('.player path')?.getAttribute('transform').includes('rotate(90)'));
  state = states.position;
  await page.waitForFunction(() => document.querySelector('.player')?.getAttribute('aria-label') === 'Approximate position · Main Hall 2F');
  const positionRoom = await page.locator('.room.current').elementHandle();
  const positionBox = await page.locator('#map').getAttribute('viewBox');
  assert.equal(await page.locator('#player-label').textContent(), 'You · approximate');
  for (const delta of [0, .5, 1, 0]) {
    const point = [states.position.player_position.point[0] + delta, states.position.player_position.point[1]];
    state = { ...states.position, player_position: { kind: 'approximate', point } };
    await page.waitForFunction(point => document.querySelector('.player')?.getAttribute('transform') === 'translate(' + point.join(' ') + ')', point);
    assert(await positionRoom.evaluate(node => node.isConnected), 'walking must preserve room controls');
    assert.equal(await page.locator('#map').getAttribute('viewBox'), positionBox, 'walking must preserve the chosen view');
    assert.match(await page.locator('.player path').getAttribute('transform'), /^translate\(0 0\) rotate\(90\)/, 'a positioned marker must rotate around its actual estimate');
  }
  state = states.initial;
  await page.waitForFunction(() => document.querySelector('.player')?.getAttribute('aria-label') === 'You · Main Hall 2F');
  assert.equal(await page.locator('#player-label').textContent(), 'You · room only');
  assert.equal(await page.locator('.map-detail').count(), 1, 'the explored Main Hall must retain its stairs');
  const map = page.locator('#map');
  const zoomIn = page.getByRole('button', { name: 'Zoom in', exact: true });
  const zoomOut = page.getByRole('button', { name: 'Zoom out', exact: true });
  const fit = page.getByRole('button', { name: 'Fit explored rooms', exact: true });
  const initialBox = await map.getAttribute('viewBox');
  const arrowSize = await page.locator('.player path').boundingBox();
  assert(arrowSize.width < 24 && arrowSize.height < 24, 'the locator must not become a large badge on a small explored area');
  assert(await zoomOut.isDisabled());
  await zoomIn.focus();
  await page.keyboard.press('Enter');
  assert.equal(await page.locator('#zoom-level').textContent(), '125%');
  const zoomedArrowSize = await page.locator('.player path').boundingBox();
  assert(Math.abs(arrowSize.width - zoomedArrowSize.width) < .1 && Math.abs(arrowSize.height - zoomedArrowSize.height) < .1, 'zooming must preserve the arrow size');
  assert(Number((await map.getAttribute('viewBox')).split(' ')[2]) < Number(initialBox.split(' ')[2]));
  assert(!(await current.isDisabled()), 'Current room must be available after zooming');
  await zoomOut.click();
  assert.equal(await page.locator('#zoom-level').textContent(), '100%');
  await fit.focus();
  await page.keyboard.press('Space');
  assert.equal(await map.getAttribute('viewBox'), initialBox);

  const bounds = await map.boundingBox();
  const cursor = { x: Math.round(bounds.x + bounds.width * .6), y: Math.round(bounds.y + bounds.height * .4) };
  const before = await map.evaluate((svg, point) => {
    const world = new DOMPoint(point.x, point.y).matrixTransform(svg.getScreenCTM().inverse());
    return [world.x, world.y];
  }, cursor);
  await page.mouse.move(cursor.x, cursor.y);
  await page.mouse.wheel(0, -200);
  await page.waitForFunction(() => document.getElementById('zoom-level').textContent !== '100%');
  const after = await map.evaluate((svg, point) => {
    const world = new DOMPoint(point.x, point.y).matrixTransform(svg.getScreenCTM().inverse());
    return [world.x, world.y];
  }, cursor);
  assert(before.every((value, index) => Math.abs(value - after[index]) < 1e-5), 'wheel zoom must keep the point under the cursor');
  const wheelBox = await map.getAttribute('viewBox');
  await map.dispatchEvent('wheel', { deltaY: -200, ctrlKey: true, clientX: cursor.x, clientY: cursor.y });
  assert.equal(await map.getAttribute('viewBox'), wheelBox, 'Ctrl+wheel belongs to browser zoom');
  for (let count = 0; count < 6; count++) await map.dispatchEvent('wheel', { deltaY: -1000, clientX: cursor.x, clientY: cursor.y });
  assert.equal(await page.locator('#zoom-level').textContent(), '800%');
  assert(await zoomIn.isDisabled());
  for (let count = 0; count < 6; count++) await map.dispatchEvent('wheel', { deltaY: 1000, clientX: cursor.x, clientY: cursor.y });
  assert.equal(await page.locator('#zoom-level').textContent(), '100%');
  assert(await zoomOut.isDisabled());
  await fit.click();
  assert.equal(await map.getAttribute('viewBox'), initialBox);
  await floor.selectOption('mansion1f');
  const firstFloorBox = await map.getAttribute('viewBox');
  assert.equal(await page.locator('.player').count(), 0, 'browsing another floor must hide the player');
  assert.notEqual(firstFloorBox, initialBox, 'a floor switch must fit the displayed floor');
  await zoomIn.click();
  const chosenBox = await map.getAttribute('viewBox');
  await page.waitForTimeout(1100);
  assert.equal(await map.getAttribute('viewBox'), chosenBox, 'polling must preserve zoom');
  state = states.expanded;
  await page.waitForFunction(() => document.querySelectorAll('#map .room').length === 2);
  assert.equal(await map.getAttribute('viewBox'), chosenBox, 'entering another room on the same floor must preserve the chosen view');
  await fit.click();
  const expandedBox = await map.getAttribute('viewBox');
  assert(Number(expandedBox.split(' ')[2]) > Number(firstFloorBox.split(' ')[2]), 'Fit must include newly entered rooms');

  const herbName = map.getByRole('button', { name: 'Winding Passage', exact: true }).locator('text');
  const herbBounds = await herbName.boundingBox();
  await page.mouse.move(herbBounds.x + herbBounds.width / 2, herbBounds.y + herbBounds.height / 2);
  await page.mouse.down();
  await page.mouse.move(herbBounds.x + herbBounds.width / 2 - 50, herbBounds.y + herbBounds.height / 2 + 20, { steps: 5 });
  const draggedBox = await map.getAttribute('viewBox');
  assert.notEqual(draggedBox, expandedBox);
  assert.equal(draggedBox.split(' ').slice(2).join(' '), expandedBox.split(' ').slice(2).join(' '), 'panning must preserve scale');
  await page.waitForTimeout(1100);
  assert.equal(await map.getAttribute('viewBox'), draggedBox, 'polling must preserve an active drag');
  await page.mouse.up();
  assert.equal(await page.locator('#room-id').textContent(), 'Room 00-05 · Current room', 'dragging a different room must not select it');
  assert.equal(await map.evaluate(() => pan.mode), 'idle');
  await fit.click();
  const nextHerbBounds = await herbName.boundingBox();
  await page.mouse.move(nextHerbBounds.x + nextHerbBounds.width / 2, nextHerbBounds.y + nextHerbBounds.height / 2);
  await page.mouse.down();
  await page.mouse.move(nextHerbBounds.x + nextHerbBounds.width / 2 + 25, nextHerbBounds.y + nextHerbBounds.height / 2 + 10);
  await page.mouse.wheel(0, -60);
  await page.waitForFunction(() => pan.mode === 'idle');
  await page.mouse.up();
  assert.equal(await page.locator('#room-id').textContent(), 'Room 00-05 · Current room', 'zooming during a drag must not turn its release into a room click');
  await fit.click();
  await map.getByRole('button', { name: 'Winding Passage', exact: true }).click();
  assert.equal(await page.locator('#room-id').textContent(), 'Room 00-09', 'a normal click after dragging must still select a room');
  assert.equal(await current.getAttribute('aria-pressed'), 'false');
  await zoomIn.click();
  await current.click();
  assert.equal(await map.getAttribute('viewBox'), expandedBox, 'Current room must restore a view containing the current room');
  assert(await current.isDisabled());
  assert.equal(await current.getAttribute('aria-pressed'), 'true');
  state = { ...states.expanded, current: '00-09', map_region: '09', current_detail: states.expanded.rooms.find(room => room.id === '09') };
  await page.waitForFunction(() => document.getElementById('room-id').textContent === 'Room 00-09 · Current room');
  assert.equal(await current.getAttribute('aria-pressed'), 'true', 'following must select newly entered rooms');
  state = states.expanded;
  await page.waitForFunction(() => document.getElementById('room-id').textContent === 'Room 00-05 · Current room');

  await page.mouse.move(bounds.x + 20, bounds.y + 20);
  await page.mouse.down();
  await page.mouse.move(bounds.x + 40, bounds.y + 40);
  state = { status: 'waiting', error: 'Interrupted during drag' };
  await page.waitForFunction(() => document.getElementById('floor').disabled);
  assert.equal(await map.evaluate(() => pan.mode), 'idle');
  assert.equal(await page.locator('#map.panning').count(), 0);
  assert(await zoomIn.isDisabled());
  assert(await zoomOut.isDisabled());
  assert(await fit.isDisabled());
  await page.mouse.up();
  state = states.initial;
  await page.waitForFunction(() => document.getElementById('floor').value === 'mansion2f' && !document.getElementById('floor').disabled);
  assert.equal(await map.getAttribute('viewBox'), initialBox);
  assert.match(await remaining.textContent(), /Mansion · 1FWinding PassageGreen Herb/);
  assert.match(await remaining.textContent(), /Sun Crest/);
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
  assert.match(await page.locator('#items').textContent(), /Sun CrestRemaining/);
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
  assert.equal(await page.locator('.player').count(), 0, 'an interrupted read must clear the player marker');
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
  assert.equal(await page.locator('.player').count(), 0, 'an unoutlined room must not get an invented player location');
  assert(await zoomIn.isDisabled());
  assert(await zoomOut.isDisabled());
  assert(await fit.isDisabled());
  assert.match(await page.locator('#room-id').textContent(), /04-15.*Current room/);
  const unoutlinedLink = checks.getByRole('button', { name: /^Elevator B3\/B4/ });
  assert(await unoutlinedLink.isVisible());
  assert.match(await unoutlinedLink.textContent(), /Item list incomplete/);
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
  assert.equal(await page.locator('.player').getAttribute('aria-label'), 'You · Elevator Stairway');
  state = states.helmet_doors;
  await page.waitForFunction(() => document.getElementById('room-id').textContent.includes('01-0b'));
  assert.equal(await page.locator('.door[data-door="0B-0C"].LOCKED').count(), 1, 'Lesson Room must match its returned-Mansion outline before the return');
  assert.equal(await page.locator('.door .key-symbol').getAttribute('aria-label'), 'Helmet Key');
  assert.equal(await page.locator('.room').count(), 1, 'a locked target must stay hidden');
  await floor.selectOption('mansion1f');
  assert.equal(await page.locator('.door[data-door="0A-19"].LOCKED').count(), 1, 'Back Passage must match its returned-Mansion destination');
  state = states.helmet_unlocked;
  await page.waitForFunction(() => document.querySelector('.door[data-door="0A-19"].OPEN'));
  assert.equal(await page.locator('.door .key-symbol').count(), 0, 'unlocking must remove the used-key emblem');
  state = states.helmet_doors;
  await page.waitForFunction(() => document.querySelector('.door[data-door="0A-19"].LOCKED'));
  assert.equal(await page.locator('.door .key-symbol').getAttribute('aria-label'), 'Helmet Key', 'rewinding the unlock must restore the emblem');
  await current.click();
  assert.equal(await page.locator('.door[data-door="0B-0C"].LOCKED').count(), 1);
  for (const key of ['Sword Key', 'Armor Key', 'Shield Key', 'Helmet Key', 'Small Key']) {
    await page.evaluate(key => {
      const fixture = lastState;
      draw({ ...fixture, doors: fixture.doors.map(door => ({ ...door, label: 'Locked', key_label: key })) });
    }, key);
    assert.equal(await page.locator('.door .key-symbol').getAttribute('aria-label'), key);
    assert.match(await page.locator('#doors').textContent(), new RegExp(key));
  }
  await page.evaluate(() => draw({ ...lastState, doors: lastState.doors.map(door => ({ ...door, key_label: '', label: 'Locked by a puzzle or event' })) }));
  assert.equal(await page.locator('.door .key-symbol').count(), 0, 'a puzzle lock must not acquire an invented key emblem');
  state = states.open_door_descriptions;
  await page.waitForFunction(() => document.getElementById('room-id').textContent.includes('00-0c'));
  const keeperDoor = page.locator('.door[data-door="03-0E"]');
  const trapDoor = page.locator('.door[data-door="09-15"]');
  for (const door of [keeperDoor, trapDoor]) {
    assert.match(await door.getAttribute('class'), /\bOPEN\b/, 'matching access must survive different descriptions on opposite sides');
    assert.equal(await door.locator('line:not(.door-border)').evaluate(line => getComputedStyle(line).stroke), 'rgb(113, 182, 207)');
    assert.match(await door.locator(':scope > title').textContent(), /No lock/);
    assert.match(await door.locator(':scope > title').textContent(), /Unlocked/);
  }
  assert.equal(await keeperDoor.locator('.key-symbol').count(), 0, 'an open door must not retain its key emblem');
  assert.equal(await trapDoor.locator('.key-symbol').count(), 0);
  assert.equal(await page.locator('.unlock-symbol,#doors .list-symbol.unlocked').count(), 0, 'RE1 access and label wording must not fabricate separate unlock knowledge');
  await page.evaluate(() => draw({ ...lastState, doors: [...lastState.doors].reverse() }));
  assert.match(await keeperDoor.getAttribute('class'), /\bOPEN\b/);
  assert.equal(await keeperDoor.locator('.key-symbol').count(), 0);
  state = { ...states.locked_door_descriptions, doors: [...states.locked_door_descriptions.doors].reverse() };
  await page.waitForFunction(() => document.querySelector('.door[data-door="03-0E"] .key-symbol')?.getAttribute('aria-label') === 'Sword Key');
  assert.match(await keeperDoor.getAttribute('class'), /\bLOCKED\b/);
  state = { ...states.locked_door_descriptions, doors: states.locked_door_descriptions.doors.map(door => door.source === '00-03' ? { ...door, key_label: 'Armor Key' } : door.source === '00-0e' ? { ...door, key_label: 'Sword Key' } : door) };
  await page.waitForFunction(() => document.querySelector('.door[data-door="03-0E"] .key-symbol') === null);
  assert.match(await keeperDoor.getAttribute('class'), /\bLOCKED\b/);
  assert.equal(await keeperDoor.locator('.key-symbol').count(), 0, 'conflicting key identities must not invent an emblem');
  for (const name of ["Keeper's Room", 'Central Corridor']) {
    await map.getByRole('button', { name, exact: true }).focus();
    await page.keyboard.press('Enter');
    assert(await map.getByRole('button', { name, exact: true }).evaluate(room => room === document.activeElement), 'Enter must retain map keyboard focus after selecting a room');
    await page.keyboard.press('Space');
    assert(await map.getByRole('button', { name, exact: true }).evaluate(room => room === document.activeElement), 'Space must remain usable after the selection redraw');
    await page.keyboard.press('Tab');
    assert(await map.evaluate(svg => svg.contains(document.activeElement) && document.activeElement.classList.contains('room')), 'Tab must continue to the next map room');
    assert.equal(await keeperDoor.locator('.key-symbol').count(), 0, 'selecting a direction must not hide conflicting key metadata');
  }
  await current.click();
  state = { ...states.open_door_descriptions, doors: states.open_door_descriptions.doors.map(door => door.source === '00-03' ? { ...door, state: 'LOCKED', label: 'Locked' } : door) };
  await page.waitForFunction(() => document.querySelector('.door[data-door="03-0E"].UNCHECKED'));
  assert.match(await keeperDoor.getAttribute('class'), /\bUNCHECKED\b/, 'conflicting access must remain unresolved while neither side is selected');
  await map.getByRole('button', { name: "Keeper's Room", exact: true }).focus();
  await page.keyboard.press('Enter');
  assert.match(await keeperDoor.getAttribute('class'), /\bOPEN\b/, 'selecting a side must retain its directional access');
  assert.equal(await keeperDoor.locator('.key-symbol').count(), 0, 'an open direction must not display a key requirement');
  await map.getByRole('button', { name: 'Central Corridor', exact: true }).focus();
  await page.keyboard.press('Enter');
  assert.match(await keeperDoor.getAttribute('class'), /\bLOCKED\b/);
  assert.equal(await keeperDoor.locator('.key-symbol').getAttribute('aria-label'), 'Sword Key');
  state = states.before_room002;
  await page.waitForFunction(() => document.getElementById('floor').value === 'guardhouse1f');
  assert.equal(await map.getByRole('button', { name: 'Room 002', exact: true }).count(), 0, 'a ladder must not reveal an unentered room');
  state = states.room002;
  const room002 = map.getByRole('button', { name: 'Room 002', exact: true });
  await room002.waitFor();
  assert(await room002.locator('.map-detail').evaluate(path => {
    // Singleton shade runs must paint both rails, with gaps between the rungs.
    const painted = (x, y) => path.isPointInStroke(new DOMPoint(x, y));
    return painted(89.5, 28.5) && painted(91.5, 28.5)
      && painted(90.5, 29.5) && !painted(90.5, 28.5);
  }), 'Room 002 must visibly retain the native ladder rails and rungs');
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
        const detail = group.querySelector('.map-detail');
        const region = plan.rooms.find(room => room.id === visit.id);
        if (Boolean(detail) !== Boolean(region.detail_segments.length)) throw new Error('Missing room interior geometry');
        if (detail && (getComputedStyle(detail).fill !== 'none' || getComputedStyle(detail).strokeWidth !== '1px')) throw new Error('Current-room styling obscures stairs');
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
  console.log('Browser checks passed: player indicator, stair geometry, key symbols and Helmet Key door states, zoom, pan, fit, stable views, room names on ' + labelCount + ' outlines, floor browsing, remaining-items overview and navigation, incomplete checks, fresh state, interruption, new history, unoutlined rooms and camera aliases.');
} finally {
  await browser.close();
}
