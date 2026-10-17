// Explicit synthetic visits test the RE2 catalog and shared browser, not gameplay.
// NODE_PATH=<bundled node_modules> bun tests/check_re2_map_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chromium } from 'playwright';

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
print(json.dumps({'document':map_page(p.map_layout.document).decode(),'state':map_state(t),'counts':counts,'markers':markers}))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const { document, state, counts, markers } = JSON.parse(setup.stdout);
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
  assert.deepEqual(errors, []);
  console.log('RE2 browser checks passed for all ' + Object.values(counts).reduce((sum, count) => sum + count, 0) + ' outlines and exact door bindings.');
} finally {
  await browser.close();
}
