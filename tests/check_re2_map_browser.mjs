// Synthetic visits and RE2-PLAYER-001 heading references test the shared browser.
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
t.rooms['00-01'].items=(ItemDetail('Handgun ammo','available',15),ItemDetail('Shotgun','unknown',5))
t.rooms['00-01'].reason='Item conditions are unresolved.'
t.rooms['00-01'].list_complete=True
t.rooms['00-01'].completion=RoomCompletion.Incomplete
markers=[door for door in p.map_layout.document['areas'][0]['doors'] if door['observation_id'].startswith('00-01:')]
assert len(markers)==2
# Both observations intentionally share a room pair. Only source IDs can bind
# the two different access states to their proper walls.
t.doors=tuple(DoorDetail(RoomId(0,1),RoomId(0,0),access,access,key_label='Spade Key',observation_id=marker['observation_id']) for marker,access in zip(markers,('LOCKED','OPEN')))
print(json.dumps({'document':map_page(p.map_layout.document).decode(),'state':map_state(t),'counts':counts,'markers':markers,'floorStates':floor_states}))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const { document, state, counts, markers, floorStates } = JSON.parse(setup.stdout);
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
    assert.equal(await page.locator('#map .room text').count(), count, area);
  }
  await floor.selectOption('re2-00');
  for (const [index, marker] of markers.entries()) {
    const door = page.locator('[data-door="' + marker.id + '"]');
    assert((await door.getAttribute('class')).includes(index === 0 ? 'LOCKED' : 'OPEN'));
    if (index === 0) assert.equal(await door.locator('.key-symbol title').textContent(), 'Spade Key');
    else assert.equal(await door.locator('.key-symbol').count(), 0, 'an open RE2 door must hide its used-key symbol');
  }
  assert.match(await page.locator('#remaining-items').textContent(), /Handgun ammo/);
  assert.match(await page.locator('#incomplete-checks').textContent(), /Gun/);
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
  // Fresh display publications omit the interrupted-read error field.
  delete state.error;
  Object.assign(state, floorStates['native-upper-approach']);
  await page.waitForFunction(() => document.getElementById('floor').value === 're2-03');
  assert.equal(await floor.locator('option').count(), 1, 'another floor must stay hidden until entered');
  assert.equal(await page.locator('#map .room').count(), 1);
  Object.assign(state, floorStates['lower-later']);
  await page.waitForFunction(() => document.getElementById('floor').value === 're2-02');
  assert.deepEqual(await floor.locator('option').evaluateAll(options => options.map(option => option.value)), ['re2-02', 're2-03']);
  assert.equal(await page.locator('#map .room').count(), 1, 'a floor change must reveal only its visited region');
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
  assert.deepEqual(errors, []);
  console.log('RE2 browser checks passed for all ' + Object.values(counts).reduce((sum, count) => sum + count, 0) + ' outlines, door bindings, headings, moving markers and floor following/browsing/restores.');
} finally {
  await browser.close();
}
