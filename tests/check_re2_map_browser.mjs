// Synthetic visits and RE2-PLAYER-001 heading references test the shared browser.
// RE2-MAP-003 checks interior styling and label clearance on the DualShock layout.
// NODE_PATH=<bundled node_modules> bun tests/check_re2_map_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const { measurements } = JSON.parse(readFileSync('tests/fixtures/re2/heading-movements.json', 'utf8'));
const { observations } = JSON.parse(readFileSync('tests/fixtures/re2/position-observations.json', 'utf8'));
assert(process.argv[2], 'Pass the Python executable used for tracker tests');
const setup = spawnSync(process.argv[2], ['-c', `
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from games.game_profile import RoomId
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import Tracker,RoomRecord,RoomCompletion,ItemDetail,DoorDetail
from ui.map_view import map_page,map_state
p=Re2Profile.load(Path('profiles/re2_leon_a_slus00421.json'))
floor_states={}
floor_tracker=Tracker()
for observation in json.loads(Path('tests/fixtures/re2/floor-transitions.json').read_text())['observations']:
    room=RoomId(*observation['room'])
    area,region=observation['area'],observation['region']
    floor_tracker.mark_current(room)
    floor_tracker.current_region=area+':'+region
    floor_tracker.region_visits[floor_tracker.current_region]=str(room)
    floor_tracker.player_heading=observation['published_heading']
    x,_,z=observation['world_position']
    floor_tracker.player_position=p.map_layout.project(area,region,x,z)
    floor_states[observation['label']]=map_state(floor_tracker)
t=Tracker()
counts={}
for area in p.map_layout.document['areas']:
    counts[area['id']]=len(area['rooms'])
    for room in area['rooms']:
        key=room['room_ids'][0]
        t.rooms[key]=RoomRecord(visited=True,completion=RoomCompletion.Unknown)
        t.region_visits[area['id']+':'+room['id']]=key
t.mark_current(RoomId(0,1));t.player_heading=90;t.current_region='re2-00:01'
t.rooms['00-01'].items=(ItemDetail('Handgun ammo','available',15, True),ItemDetail('Shotgun','unknown',5, False))
t.rooms['00-01'].reason='Item conditions are unresolved.'
t.rooms['00-01'].list_complete=True
t.rooms['00-01'].completion=RoomCompletion.Incomplete
markers=[door for door in p.map_layout.document['areas'][0]['doors'] if any(obs.startswith('00-01:') for obs in door['observation_ids'])]
assert len(markers)==2
# Both observations intentionally share a room pair. Only source IDs can bind
# the two different access states to their proper walls.
t.doors=tuple(DoorDetail(RoomId(0,1),RoomId(0,0),access,access,key_label='Spade Key',observation_id=next(obs for obs in marker['observation_ids'] if obs.startswith('00-01:'))) for marker,access in zip(markers,('LOCKED','OPEN')))
t.doors += (DoorDetail(RoomId(0,0),RoomId(0,1),'LOCKED','Locked',key_label='Club Key',observation_id='00-00:4246'),DoorDetail(RoomId(0,2),RoomId(0,1),'BLOCKED','Door is inactive',observation_id='00-02:6146'))
detail_profile=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json'))
detail_tracker=Tracker()
for area in detail_profile.map_layout.document['areas']:
    for room in area['rooms']:
        key=room['room_ids'][0]
        detail_tracker.rooms[key]=RoomRecord(visited=True,completion=RoomCompletion.Unknown)
        detail_tracker.region_visits[area['id']+':'+room['id']]=key
detail_tracker.mark_current(RoomId(0,2));detail_tracker.player_heading=90;detail_tracker.current_region='re2-00:02'
detail_tracker.doors=(DoorDetail(RoomId(1,0x0b),RoomId(1,0x0f),'LOCKED','Heart Key',key_label='Heart Key',observation_id='01-0b:12090'),DoorDetail(RoomId(1,0x0b),RoomId(1,0x0f),'UNCHECKED','Door conditions unresolved',observation_id='01-0b:12126'))
print(json.dumps({'document':map_page(p.map_layout.document).decode(),'state':map_state(t),'counts':counts,'markers':markers,'floorStates':floor_states,'detailDocument':map_page(detail_profile.map_layout.document).decode(),'detailState':map_state(detail_tracker),'detailCount':sum(len(area['rooms']) for area in detail_profile.map_layout.document['areas'])}))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const { document, state, counts, markers, floorStates, detailDocument, detailState, detailCount } = JSON.parse(setup.stdout);
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://re2-map.test/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: document });
    if (path === '/state') return route.fulfill({ contentType: 'application/json', body: JSON.stringify(state) });
    errors.push('Unexpected request: ' + path);
    return route.fulfill({ status: 404 });
  });
  await page.goto('http://re2-map.test/');
  const floor = page.getByLabel('Floor', { exact: true });
  await page.waitForFunction(() => document.getElementById('floor').value === 're2-00');
  assert.equal(await page.title(), 'Resident Evil 2 room map');
  for (const [area, count] of Object.entries(counts)) {
    await floor.selectOption(area);
    assert.equal(await page.locator('#map .room text').count(), count, area+' '+errors.join('; '));
  }
  await floor.selectOption('re2-00');
  for (const [index, marker] of markers.entries()) {
    const door = page.locator('[data-door="' + marker.id + '"]');
    assert((await door.getAttribute('class')).includes(index === 0 ? 'LOCKED' : 'OPEN'));
    if (index === 0) assert.equal(await door.locator('.key-symbol title').textContent(), 'Spade Key');
    else assert.equal(await door.locator('.key-symbol').count(), 0, 'an open RE2 door must hide its used-key symbol');
  }
  const entrance = page.locator('[data-observations~="00-01:6050"]');
  assert.equal(await entrance.count(), 1);
  assert.equal(await page.locator('[data-observations~="00-00:4246"]').getAttribute('data-door'), await entrance.getAttribute('data-door'), 'the two entrance observations must bind one physical marker');
  const exit = page.locator('[data-observations~="00-01:6082"]');
  assert.equal(await page.locator('[data-observations~="00-02:6146"]').getAttribute('data-door'), await exit.getAttribute('data-door'));
  await page.locator('#map').getByRole('button', { name: 'Back Street Area West', exact: true }).press('Enter');
  assert.match(await entrance.getAttribute('class'), /LOCKED/);
  assert.equal(await entrance.locator('.key-symbol title').textContent(), 'Club Key', 'selecting the other side must use its known key');
  await page.locator('#map').getByRole('button', { name: 'Basketball Court Alleyway', exact: true }).press('Enter');
  assert.match(await exit.getAttribute('class'), /BLOCKED/);
  await page.locator('#map').getByRole('button', { name: "Kendo's Gun Shop", exact: true }).press('Enter');
  assert.match(await entrance.getAttribute('class'), /LOCKED/);
  assert.equal(await entrance.locator('.key-symbol title').textContent(), 'Spade Key');
  assert.match(await exit.getAttribute('class'), /OPEN/);
  const allExploration = structuredClone(state);
  const shopVisit = state.current_detail;
  state.rooms = [shopVisit];
  state.explored_areas = { 're2-00': [shopVisit] };
  state.doors = state.doors.filter(door => door.source === '00-01').map(door => ({ ...door, target_visited: false }));
  await page.waitForFunction(() => document.querySelectorAll('#map .room').length === 1);
  assert.equal(await page.locator('#map .door').count(), 2, 'the shop must show two doors without revealing either neighbor');
  const search = page.getByLabel('Find item or room', { exact: true });
  await search.fill('Basketball Court Alleyway');
  assert.equal(await page.locator('#overview .room-link').count(), 0, 'search must not reveal an unvisited catalog room');
  assert.equal(await page.locator('#map .room').count(), 1);
  await search.press('Escape');
  assert.equal(await search.inputValue(), '');
  Object.assign(state, allExploration);
  await page.waitForFunction(() => document.querySelectorAll('#map .room').length > 1);
  assert.match(await page.locator('#items').textContent(), /Handgun ammo ×15/);
  assert.match(await page.locator('#remaining-items').textContent(), /Handgun ammo ×15/);
  assert.match(await page.locator('#incomplete-checks').textContent(), /Unresolved: Shotgun/);
  const originalVisit = structuredClone(state.current_detail);
  const roomName = await page.locator('#room-name').textContent();
  await search.fill('  shOTGUN  ');
  assert.equal(await page.locator('#remaining-items .room-link').count(), 0, 'an unresolved item must not become a remaining result');
  assert.equal(await page.locator('#incomplete-checks .room-link').count(), 1);
  assert.match(await page.locator('#incomplete-checks').textContent(), /Unresolved: Shotgun/);
  assert.equal(await page.locator('#completion').textContent(), 'Items remain');
  await page.locator('#incomplete-checks .room-link').press('Enter');
  assert.equal(await page.locator('#room-name').textContent(), roomName);
  assert.equal(await search.inputValue(), '  shOTGUN  ');
  await search.fill('no such item');
  assert.equal(await page.locator('#overview .room-link').count(), 0);
  assert.equal(await page.locator('#remaining-status').textContent(), 'No matching remaining items.');
  assert.equal(await page.locator('#checks-status').textContent(), 'No matching incomplete item checks.');
  await search.press('Escape');
  assert(await search.evaluate(input => input === document.activeElement), 'clearing search must preserve input focus');
  const visits = [state.current_detail, ...state.rooms, ...Object.values(state.explored_areas).flat()].filter(visit => visit.room === state.current);
  for (const visit of visits) {
    Object.assign(visit, {
      state: 'UNKNOWN',
      items_complete: false,
      items: [{ label: 'Collectible', state: 'taken', quantity: 'unreconstructed', quantity_is_unit_count: false }],
    });
  }
  await page.waitForFunction(() => document.getElementById('items').textContent.includes('Collected'));
  assert.match(await page.locator('#items').textContent(), /Collectible/);
  assert.equal(await page.locator('#remaining-items .room-link').count(), 0);
  const incompleteRoom = page.locator('#incomplete-checks .room-link').filter({ hasText: roomName });
  assert.equal(await incompleteRoom.count(), 1);
  assert.match(await incompleteRoom.textContent(), /Item list incomplete/);
  assert.doesNotMatch(await page.locator('#items').textContent(), /×|unreconstructed/);
  assert((await page.locator('#map .room.selected').getAttribute('class')).includes('UNKNOWN'));
  for (const visit of visits) Object.assign(visit, structuredClone(originalVisit));
  await page.waitForFunction(() => document.getElementById('items').textContent.includes('Handgun ammo'));
  const remainingRoom = page.locator('#remaining-items .room-link').filter({ hasText: roomName });
  await remainingRoom.focus();
  const focusedRoom = await remainingRoom.elementHandle();
  state.player_heading = 180;
  await page.waitForFunction(() => document.querySelector('.player path')?.getAttribute('transform').includes('rotate(180)'));
  assert(await focusedRoom.evaluate(link => link === document.activeElement), 'pose-only polls must preserve overview keyboard focus');
  for (const amount of [30, 'unreconstructed', 0, 1, 15]) {
    for (const visit of visits) visit.items[0].quantity = amount;
    const label = amount === 'unreconstructed' || amount === 1 ? 'Handgun ammo' : 'Handgun ammo ×' + amount;
    await page.waitForFunction(expected => document.querySelector('#items .entry-name')?.textContent === expected, label);
    assert.equal(await remainingRoom.locator('span').last().textContent(), label, 'overview quantities must refresh after a changed game state');
    assert.equal(await page.locator('#completion').textContent(), 'Items remain');
    assert.match(await page.locator('#incomplete-checks').textContent(), /Unresolved: Shotgun/);
  }
  for (const [label, amount, unitCount] of [
    ['Shotgun', 5, false],
    ['Spade Key', 2, false],
    ['Fuel Tank', 100, false],
    ['Small Key', 2, true],
  ]) {
    for (const itemState of ['available', 'unknown', 'taken']) {
      for (const visit of visits) Object.assign(visit.items[0], { label, quantity: amount, quantity_is_unit_count: unitCount, state: itemState });
      const expected = label + (unitCount ? ' ×' + amount : '');
      await page.waitForFunction(([name, itemState]) => document.querySelector('#items .entry-name')?.textContent === name && lastState.current_detail.items[0].state === itemState, [expected, itemState]);
      const summary = await page.locator('#overview').textContent();
      if (itemState !== 'taken') assert(summary.includes(expected));
      if (!unitCount) assert(!summary.includes(label + ' ×'), 'resource/use amounts must not become item counts');
      assert.equal(await page.locator('#completion').textContent(), 'Items remain', 'quantity units do not change clearance');
    }
  }
  for (const visit of visits) Object.assign(visit, structuredClone(originalVisit));
  await page.waitForFunction(() => document.querySelector('#items .entry-name')?.textContent === 'Handgun ammo ×15');
  await search.fill('Handgun ammo ×30');
  assert.equal(await page.locator('#remaining-items .room-link').count(), 0);
  for (const visit of visits) visit.items[0].quantity = 30;
  await page.waitForFunction(() => document.getElementById('remaining-items').textContent.includes('Handgun ammo ×30'));
  assert.equal(await page.locator('#remaining-items .room-link').count(), 1);
  for (const visit of visits) visit.items[0].quantity = 15;
  await page.waitForFunction(() => document.querySelectorAll('#remaining-items .room-link').length === 0);
  assert.equal(await search.inputValue(), 'Handgun ammo ×30', 'fresh state must retain the player\'s filter');
  assert(await search.evaluate(input => input === document.activeElement), 'fresh state must preserve search input focus');
  await search.press('Escape');
  for (const visit of visits) {
    visit.items_complete = false;
    visit.items[1].state = 'taken';
  }
  await page.waitForFunction(name => [...document.querySelectorAll('#incomplete-checks .room-link')].find(link => link.firstElementChild.textContent === name)?.textContent.includes('Item list incomplete'), roomName);
  assert.doesNotMatch(await incompleteRoom.textContent(), /Unresolved: Shotgun/);
  await incompleteRoom.press('Enter');
  assert.equal(await page.locator('#room-name').textContent(), roomName);
  assert.equal(await page.locator('#completion').textContent(), 'Items remain');
  for (const visit of visits) Object.assign(visit, structuredClone(originalVisit));
  await page.waitForFunction(name => [...document.querySelectorAll('#incomplete-checks .room-link')].find(link => link.firstElementChild.textContent === name)?.textContent.includes('Unresolved: Shotgun'), roomName);
  const visibleNavigationView = await page.locator('#map').getAttribute('viewBox');
  await remainingRoom.press('Enter');
  assert.equal(await page.locator('#map').getAttribute('viewBox'), visibleNavigationView, 'navigating to an already visible outline must preserve the view');
  for (let i = 0; i < 7; i++) await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  const navigationMap = page.locator('#map'), navigationBounds = await navigationMap.boundingBox();
  for (let i = 0; i < 4; i++) {
    await page.mouse.move(navigationBounds.x + navigationBounds.width * .8, navigationBounds.y + navigationBounds.height / 2);
    await page.mouse.down();
    await page.mouse.move(navigationBounds.x + navigationBounds.width * .2, navigationBounds.y + navigationBounds.height / 2, { steps: 4 });
    await page.mouse.up();
  }
  const beforeNavigationZoom = Number.parseInt(await page.locator('#zoom-level').textContent());
  const navigationRoomFits = await page.locator('.room.selected').evaluate(room => {
    const bounds = room.getBoundingClientRect(), map = document.getElementById('map').getBoundingClientRect();
    return bounds.width <= map.width && bounds.height <= map.height;
  });
  await remainingRoom.focus();
  await remainingRoom.press('Enter');
  assert(await page.locator('.room.selected').evaluate(room => {
    const bounds = room.getBoundingClientRect(), map = document.getElementById('map').getBoundingClientRect();
    return bounds.left >= map.left && bounds.right <= map.right && bounds.top >= map.top && bounds.bottom <= map.bottom;
  }), 'item-list navigation must bring the entire selected outline into the zoomed map');
  assert(Number.parseInt(await page.locator('#zoom-level').textContent()) <= beforeNavigationZoom, 'navigation must never zoom in past the chosen scale');
  if (navigationRoomFits) assert.equal(Number.parseInt(await page.locator('#zoom-level').textContent()), beforeNavigationZoom, 'recentring a room that fits must retain the chosen zoom');
  assert(await page.locator('.room.selected').evaluate(room => room === document.activeElement), 'keyboard navigation must focus the selected outline');
  const navigationView = await navigationMap.getAttribute('viewBox');
  state.player_heading = 270;
  await page.waitForFunction(() => document.querySelector('.player path')?.getAttribute('transform').includes('rotate(270)'));
  assert.equal(await navigationMap.getAttribute('viewBox'), navigationView, 'live updates must preserve the navigated view');
  await page.getByRole('button', { name: 'Fit explored rooms', exact: true }).click();
  for (const movement of measurements) {
    state.player_heading = movement.published_heading;
    await page.waitForFunction(heading => document.querySelector('.player path')?.getAttribute('transform').includes('rotate(' + heading + ')'), state.player_heading);
    const heading = await page.locator('.player path').evaluate(marker => {
      const matrix = marker.getScreenCTM();
      // Compare the actual arrow tip in screen coordinates, so a reversed
      // glyph or SVG transform cannot pass on the rotation attribute alone.
      const origin = new DOMPoint(0, 0).matrixTransform(matrix);
      const tip = marker.getPointAtLength(0).matrixTransform(matrix);
      return (Math.atan2(tip.x - origin.x, origin.y - tip.y) * 180 / Math.PI + 360) % 360;
    });
    const motion = (Math.atan2(movement.dx, movement.dz) * 180 / Math.PI + 360) % 360;
    assert(Math.abs((heading - motion + 540) % 360 - 180) < 2, movement.after);
  }
  const positions = ['first-earlier', 'first-later'].map(label => {
    const matches = observations.filter(row => row.label === label);
    assert.equal(matches.length, 1);
    return matches[0];
  });
  state.player_position = positions[0].marker;
  state.player_heading = positions[0].published_heading;
  await page.waitForFunction(point => document.querySelector('.player')?.getAttribute('transform') === 'translate(' + point.join(' ') + ')', positions[0].marker.point);
  assert.equal(await page.locator('#player-label').textContent(), 'You · approximate');
  assert.match(await page.locator('.player path').getAttribute('transform'), /^translate\(0 0\)/);
  const player = await page.locator('.player').elementHandle();
  assert(player);
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  const map = page.locator('#map'), bounds = await map.boundingBox();
  assert(bounds);
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width / 2 + 30, bounds.y + bounds.height / 2 + 20, { steps: 4 });
  await page.mouse.up();
  const chosenView = await map.getAttribute('viewBox');
  await search.fill('handgun ammo');
  assert.equal(await map.getAttribute('viewBox'), chosenView, 'filtering the overview must preserve manual zoom and pan');
  state.player_position = positions[1].marker;
  await page.waitForFunction(point => document.querySelector('.player')?.getAttribute('transform') === 'translate(' + point.join(' ') + ')', positions[1].marker.point);
  assert(await player.evaluate(node => node.isConnected), 'walking must retain the player node');
  assert.equal(await map.getAttribute('viewBox'), chosenView, 'walking must retain pan and zoom');
  const unplaced = observations.find(row => row.label === 'first-unplaced');
  assert(unplaced);
  state.player_position = unplaced.marker;
  await page.waitForFunction(() => document.getElementById('player-label').textContent === 'You · room only');
  assert.notEqual(await page.locator('.player').getAttribute('transform'), 'translate(' + positions[1].marker.point.join(' ') + ')');
  assert.equal(await map.getAttribute('viewBox'), chosenView, 'room-only placement must retain pan and zoom');
  state.status = 'waiting';
  state.error = 'Waiting for game.';
  await page.waitForFunction(() => !document.querySelector('.player'));
  assert(await floor.isDisabled(), 'an interrupted read must disable floor controls');
  assert(await search.isDisabled(), 'an interrupted read must disable item search');
  assert.equal(await search.inputValue(), 'handgun ammo');
  // Fresh display publications omit the interrupted-read error field.
  delete state.error;
  Object.assign(state, floorStates['native-upper-approach']);
  await page.waitForFunction(() => document.getElementById('floor').value === 're2-03');
  assert(!(await search.isDisabled()));
  assert.equal(await search.inputValue(), 'handgun ammo', 'recovery must retain the search query');
  await search.press('Escape');
  assert.equal(await floor.locator('option').count(), 1, 'another floor must stay hidden until entered');
  assert.equal(await page.locator('#map .room').count(), 1);
  assert.equal(await page.locator('[data-observations~="00-16:2554"]').count(), 1);
  assert.equal(await page.locator('[data-observations~="00-16:2522"]').count(), 0, 'a lower-floor trigger must not appear on the upper outline');
  Object.assign(state, floorStates['lower-later']);
  await page.waitForFunction(() => document.getElementById('floor').value === 're2-02');
  assert.deepEqual(await floor.locator('option').evaluateAll(options => options.map(option => option.value)), ['re2-02', 're2-03']);
  assert.equal(await page.locator('#map .room').count(), 1, 'a floor change must reveal only its visited region');
  assert.equal(await page.locator('[data-observations~="00-16:2522"]').count(), 1);
  assert.equal(await page.locator('[data-observations~="00-16:2554"]').count(), 0);
  await floor.selectOption('re2-03');
  assert.equal(await page.locator('.player').count(), 0, 'browsing another floor must hide the player');
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  const browsedView = await map.getAttribute('viewBox');
  Object.assign(state, floorStates['upper-return']);
  await page.waitForFunction(() => document.querySelector('.player path')?.getAttribute('transform').includes('rotate(270)'));
  Object.assign(state, floorStates['lower-restore']);
  await page.waitForFunction(() => !document.querySelector('.player'));
  assert.equal(await floor.inputValue(), 're2-03', 'floor browsing must survive a player floor change');
  assert.equal(await map.getAttribute('viewBox'), browsedView);
  const follow = page.getByRole('button', { name: 'Follow player', exact: true });
  assert.equal(await follow.getAttribute('aria-pressed'), 'false');
  await follow.click();
  await page.waitForFunction(() => document.getElementById('floor').value === 're2-02');
  assert.equal(await follow.getAttribute('aria-pressed'), 'true');
  Object.assign(state, floorStates['upper-restore']);
  await page.waitForFunction(() => document.getElementById('floor').value === 're2-03');
  assert.equal(await page.locator('#map .room').count(), 1);
  assert.equal(await floor.locator('option').count(), 2);
  assert.equal(await page.locator('[data-observations~="00-16:2554"]').count(), 1);
  assert.equal(await page.locator('[data-observations~="00-16:2522"]').count(), 0);
  assert.deepEqual(errors, []);
  const detailPage = await browser.newPage();
  detailPage.on('pageerror', error => errors.push(error.message));
  await detailPage.route('http://re2-details.test/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/') return route.fulfill({ contentType: 'text/html', body: detailDocument });
    if (path === '/state') return route.fulfill({ contentType: 'application/json', body: JSON.stringify(detailState) });
    errors.push('Unexpected detail request: ' + path);
    return route.fulfill({ status: 404 });
  });
  await detailPage.goto('http://re2-details.test/');
  await detailPage.waitForFunction(() => document.querySelector('.room.current text'));
  const detailLabels = await detailPage.evaluate(fixture => {
    floorView = { mode: 'follow' };
    selected = null;
    let count = 0;
    for (const plan of catalog.areas) {
      const visits = fixture.explored_areas[plan.id].map(visit => ({ ...visit, state: 'INCOMPLETE', items: [{ label: 'Valve Handle', state: 'available', quantity: 1, quantity_is_unit_count: false }] }));
      for (const visit of visits) {
        // Bold current-room labels must also fit beside the interior geometry.
        draw({ ...fixture, area: plan.id, map_region: visit.id, current: visit.room, current_detail: visit, rooms: visits, explored_areas: { ...fixture.explored_areas, [plan.id]: visits } });
        const group = document.querySelector('.room.current');
        const label = group.querySelector('text'), outline = group.querySelector('path');
        const core = group.querySelector('.map-detail-core'), border = group.querySelector('.map-detail-border');
        if (Boolean(core) !== Boolean(border)) throw new Error('Incomplete interior outline');
        if (core && (core.getAttribute('d') !== border.getAttribute('d') || getComputedStyle(core).stroke !== 'rgb(23, 35, 45)' || getComputedStyle(core).fill !== 'none' || getComputedStyle(border).strokeWidth !== '1.4px')) throw new Error('Interior structure lost its dark core, transparent fill or thin border');
        const matrix = outline.getCTM().inverse().multiply(label.getCTM());
        for (const span of label.querySelectorAll('tspan')) {
          for (let index = 0; index < span.getNumberOfChars(); index++) {
            const box = span.getExtentOfChar(index);
            for (const x of [box.x, box.x + box.width / 2, box.x + box.width]) {
              for (const y of [box.y, box.y + box.height / 2, box.y + box.height]) {
                const point = new DOMPoint(x, y).matrixTransform(matrix);
                if (!outline.isPointInFill(point) || border?.isPointInStroke(point)) throw new Error('Room label overlaps a boundary: ' + group.getAttribute('aria-label'));
              }
            }
          }
        }
        count++;
      }
    }
    return count;
  }, detailState);
  assert.equal(detailLabels, detailCount);
  await detailPage.evaluate(fixture => {
    const visits = fixture.explored_areas['re2-02'];
    for (const id of ['00', '0B']) {
      const current = visits.find(visit => visit.id === (id === '00' ? '0B' : '00'));
      selected = id;
      selectedArea = 're2-02';
      floorView = { mode: 'follow' };
      draw({ ...fixture, area: 're2-02', map_region: current.id, current: current.room, current_detail: current, rooms: visits, explored_areas: { 're2-02': visits } });
      const room = document.querySelector('.room.selected:not(.current)');
      const core = room?.querySelector('.map-detail-core');
      if (!core || getComputedStyle(core).stroke !== 'rgb(23, 35, 45)' || getComputedStyle(core).fill !== 'none') throw new Error('Inspecting a room overwrites its interior styling');
      if (getComputedStyle(room.firstElementChild).stroke !== 'rgb(240, 207, 140)') throw new Error('The selected outer outline lost its highlight');
    }
  }, detailState);
  const doorLocations = await detailPage.evaluate(fixture => {
    const results = [];
    for (const [region, expected] of [
      ['00', ['127,118,127,120', '127,150,127,152', '154,174,156,174', '183,166,183,168']],
      ['02', ['127,118,127,120', '86,115,88,115']],
    ]) {
      const visit = fixture.explored_areas['re2-02'].find(visit => visit.id === region);
      floorView = { mode: 'follow' };
      selected = null;
      draw({ ...fixture, area: 're2-02', map_region: region, current: visit.room, current_detail: visit, rooms: [visit], explored_areas: { 're2-02': [visit] } });
      if (document.querySelectorAll('#map .room').length !== 1) throw new Error('Door placement revealed an unexplored neighbor');
      const actual = [...new Set([...document.querySelectorAll('.door > line:not(.door-border)')].map(line => ['x1', 'y1', 'x2', 'y2'].map(key => line.getAttribute(key)).join(',')))].sort();
      if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error('Incorrect native doorway positions in region ' + region + ': ' + actual);
      results.push({ region, positions: actual });
    }
    return results;
  }, detailState);
  assert.equal(doorLocations.length, 2);
  const keyVisibility = await detailPage.evaluate(fixture => {
    const visit = fixture.explored_areas['re2-02'].find(visit => visit.id === '0B');
    const lock = fixture.doors.find(door => door.observation_id === '01-0b:12090');
    const results = [];
    for (const access of ['LOCKED', 'OPEN', 'LOCKED']) {
      lock.state = access;
      floorView = { mode: 'follow' };
      selected = null;
      draw({ ...fixture, area: 're2-02', map_region: visit.id, current: visit.room, current_detail: visit, rooms: [visit], explored_areas: { 're2-02': [visit] } });
      const symbol = document.querySelector('[data-observations~="01-0b:12090"] .key-symbol');
      if (access === 'OPEN') {
        if (symbol) throw new Error('An unlocked door retained its key symbol');
      } else {
        if (!symbol || symbol.getAttribute('aria-label') !== 'Heart Key') throw new Error('The known key symbol disappeared');
        const center = new DOMPoint(0, 0).matrixTransform(symbol.getScreenCTM());
        if (document.elementFromPoint(center.x, center.y)?.closest('.key-symbol') !== symbol) throw new Error('Another doorway covers the key symbol');
      }
      results.push(Boolean(symbol));
    }
    return results;
  }, detailState);
  assert.deepEqual(keyVisibility, [true, false, true]);
  const itemPresentation = await detailPage.evaluate(fixture => {
    const visit = fixture.explored_areas['re2-02'].find(visit => visit.id === '0B');
    const cases = [
      ['INCOMPLETE', 'available', 'available', 'rgb(104, 83, 49)'],
      ['INCOMPLETE', 'taken', 'available', 'rgb(116, 62, 64)'],
      ['INCOMPLETE', 'unknown', 'available', 'rgb(116, 62, 64)'],
      ['CLEARED', 'taken', 'taken', 'rgb(36, 76, 110)'],
      ['UNKNOWN', 'unknown', 'unknown', 'rgb(66, 81, 93)'],
      ['INCOMPLETE', 'available', 'available', 'rgb(104, 83, 49)'],
    ];
    for (const [state, keyState, supplyState, fill] of cases) {
      const current = { ...visit, state, items: [{ label: 'Valve Handle', state: keyState, quantity: 1, quantity_is_unit_count: false }, { label: 'Shotgun shells', state: supplyState, quantity: 6, quantity_is_unit_count: true }] };
      floorView = { mode: 'follow' };
      selected = null;
      draw({ ...fixture, area: 're2-02', map_region: visit.id, current: visit.room, current_detail: current, rooms: [current], explored_areas: { 're2-02': [current] } });
      if (getComputedStyle(document.querySelector('.room > path')).fill !== fill) throw new Error('Incorrect item-category room color');
      const names = [...document.querySelectorAll('#items .entry-name')];
      if (names[0].textContent !== 'Valve Handle' || names[1].textContent !== 'Shotgun shells ×6') throw new Error('Item symbols replaced the item names or quantities');
      if (!names[0].classList.contains('story') || !names[1].classList.contains('supplies')) throw new Error('Item categories lost their distinct colors');
      if (getComputedStyle(names[0]).color === getComputedStyle(names[1]).color) throw new Error('Item category colors are identical');
      for (const row of document.querySelectorAll('#items li,#doors li')) {
        if (row.querySelectorAll('svg[aria-hidden="true"]').length !== 2 || !row.querySelector('.entry-status').textContent) throw new Error('List symbols lost their adjacent text or accessibility treatment');
        if ([...row.querySelectorAll('svg')].some(icon => icon.getBoundingClientRect().height !== 18)) throw new Error('List symbols inherited the map dimensions');
      }
    }
    return cases.length;
  }, detailState);
  assert.equal(itemPresentation, 6);
  assert.deepEqual(errors, []);
  await detailPage.close();
  console.log('RE2 browser checks passed for all ' + Object.values(counts).reduce((sum, count) => sum + count, 0) + ' outlines, door bindings, headings, moving markers and floor following/browsing/restores.');
} finally {
  await browser.close();
}
