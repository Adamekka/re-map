// RE2-DOOR-006: identical slot alternatives share a list row, not map bindings.
// NODE_PATH=<runtime node_modules> bun tests/check_door_variants_browser.mjs <python> <private-output-directory>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { chromium } from 'playwright';
import { mapHeaders } from './map_browser_response.mjs';

assert(process.argv[2] && process.argv[3], 'Pass Python and a private output directory');
const output = resolve(process.argv[3]);
mkdirSync(output, { recursive: true });
const setup = spawnSync(process.argv[2], ['-c', `
import sys,json
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path.cwd()/'src'))
from games.game_profile import RoomId
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import Tracker,DoorDetail
from ui.map_view import map_page,map_state
p=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json'))
t=Tracker(player_heading=90)
for number in (0,1,4):
    t.mark_current(RoomId(1,number))
    t.region_visits[f're2-02:{number:02X}']=str(t.current)
t.current_region='re2-02:04'
t.doors=tuple(
    DoorDetail(RoomId(1,1),RoomId(d['stage'],d['room']),'UNCHECKED','Door conditions unresolved',observation_id=f'01-01:{d["offset"]}',interaction_id=f'01-01:{d["slot"]}')
    for d in p.rooms['01-01']['doors']
)
print(json.dumps({'html':map_page(p.map_layout.document,uuid4()).decode(),'state':map_state(t)}))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const fixture = JSON.parse(setup.stdout);
const browser = await chromium.launch();
const report = [];
try {
  for (const [name, width, height] of [['desktop', 1280, 916], ['mobile', 390, 1100]]) {
    const page = await browser.newPage({ viewport: { width, height } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://door-variants.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/') return route.fulfill({ headers: mapHeaders(fixture.html), contentType: 'text/html', body: fixture.html });
      if (path === '/state') return route.fulfill({ headers: mapHeaders(fixture.html), contentType: 'application/json', body: JSON.stringify(fixture.state) });
      errors.push('Unexpected request: ' + path);
      return route.fulfill({ status: 404 });
    });
    await page.goto('http://door-variants.test/');
    await page.waitForFunction(() => document.querySelector('.room.current'));
    const result = await page.evaluate(base => {
      selected = '01'; selectedArea = base.area; floorView = { mode: 'follow' };
      draw(base);
      const rows = () => [...document.querySelectorAll('#doors li')];
      if (rows().length !== 2) throw new Error('Identical Waiting Room alternatives were duplicated');
      if (!rows()[0].textContent.includes('1F RPD Main Hall') || !rows()[1].textContent.includes('1F RPD Licker Corridor')) throw new Error('The two destinations were not retained');
      if (!rows().every(row => row.querySelector('.entry-status').textContent === 'Door conditions unresolved')) throw new Error('Grouping invented access knowledge');
      const bound = [...document.querySelectorAll('[data-observations]')].flatMap(marker => marker.dataset.observations.split(' '));
      if (!base.doors.every(door => bound.includes(door.observation_id))) throw new Error('Grouping dropped a wall observation');
      const before = svg.getAttribute('viewBox');
      zoomMap(.8, new DOMPoint(...viewport.box.slice(0, 2)));
      const zoomed = svg.getAttribute('viewBox');
      const checks = [];
      for (const [field, value] of [
        ['interaction_id', '01-01:9'],
        ['target', '01-04'],
        ['state', 'OPEN'],
        ['label', 'Access unconfirmed'],
        ['key_label', 'Spade Key'],
        ['unlock_state', 'LOCKED'],
      ]) {
        const doors = structuredClone(base.doors);
        doors[2][field] = value;
        draw({ ...base, doors });
        if (rows().length !== 3) throw new Error('Distinct door field was collapsed: ' + field);
        if (svg.getAttribute('viewBox') !== zoomed || before === zoomed) throw new Error('Grouping changed the chosen view');
        checks.push(field);
      }
      draw({ ...base, doors: base.doors.map(door => ({ ...door, interaction_id: '' })) });
      if (rows().length !== 4) throw new Error('Doors without a slot identity were collapsed');
      const waiting = base.rooms.find(room => room.room === '01-01');
      for (const [indexes, access, label] of [
        [[0, 1], 'OPEN', 'Open'],
        [[2, 3], 'LOCKED', 'Locked'],
        [[0, 1], 'OPEN', 'Open'],
      ]) {
        const doors = indexes.map(index => ({ ...base.doors[index], state: access, label }));
        draw({ ...base, current: waiting.room, map_region: waiting.id, current_detail: waiting, doors });
        if (rows().length !== 2 || !rows().every(row => row.querySelector('.entry-status').textContent === label)) throw new Error('Current creator reversal lost a door or access state');
        for (const door of doors) {
          const marker = [...document.querySelectorAll('[data-observations]')].find(element => element.dataset.observations.split(' ').includes(door.observation_id));
          if (!marker?.classList.contains(access)) throw new Error('Current wall binding did not follow its source offset');
        }
      }
      draw(base);
      if (rows().length !== 2) throw new Error('Restoring the departed state changed grouping');
      return { groupedRows: rows().length, preservedObservations: base.doors.length, distinctFields: checks };
    }, fixture.state);
    const overflow = await page.evaluate(() => ({
      page: document.documentElement.scrollWidth > innerWidth,
      rows: [...document.querySelectorAll('#doors li')].filter(row => row.scrollWidth > row.clientWidth).length,
    }));
    assert.equal(overflow.page, false);
    assert.equal(overflow.rows, 0);
    assert.deepEqual(errors, []);
    report.push({ name, ...result, overflow, pageErrors: errors });
    await page.close();
  }
} finally {
  await browser.close();
}
writeFileSync(`${output}/door-variants-browser.json`, JSON.stringify(report, null, 2) + '\n');
console.log('Door variant list and wall-binding checks passed on desktop and mobile');
