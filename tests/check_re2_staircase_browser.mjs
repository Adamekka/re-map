// RE2-MAP-008. Synthetic late-room visits/access exercise production geometry.
// Keep these private renders separate from README's two observed source visits.
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
import json,sys
from pathlib import Path
from uuid import UUID
sys.path.insert(0,str(Path.cwd()/'src'))
from games.game_profile import RoomId
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import Tracker,DoorDetail
from ui.map_view import map_page,map_state
p=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json'))
fixtures=[]
for area in p.map_layout.document['areas']:
    for marker in area['doors']:
        if 'polyline' not in marker: continue
        observation=marker['observation_ids'][0]
        source,offset=observation.rsplit(':',1)
        definition=next(d for d in p.rooms[source]['doors'] if d['offset']==int(offset))
        target=RoomId(definition['stage'],definition['room'])
        stage,room=source.split('-')
        rid=RoomId(int(stage),int(room,16))
        t=Tracker(player_heading=90)
        t.mark_current(rid);t.current_region=area['id']+':'+marker['rooms'][0]
        t.region_visits[t.current_region]=source
        t.doors=(DoorDetail(rid,target,'LOCKED','Locked',key_label='Spade Key',observation_id=observation),)
        fixtures.append({'marker':marker,'state':map_state(t),'target':str(target)})
assert len(fixtures)==10
print(json.dumps({'document':map_page(p.map_layout.document,UUID('aa177f48-1bac-4867-8d3e-7bcbf8c57056')).decode(),'fixtures':fixtures}))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const fixture = JSON.parse(setup.stdout);
const browser = await chromium.launch();
const report = { basis: 'Synthetic visits/access, production catalog and page. No gameplay.', chromium: browser.version(), layouts: [] };
try {
  for (const [name, viewport] of [['desktop', { width: 1440, height: 1000 }], ['mobile', { width: 390, height: 844 }], ['tablet-portrait', { width: 768, height: 1024 }], ['tablet-landscape', { width: 1024, height: 768 }]]) {
    const page = await browser.newPage({ viewport, isMobile: name === 'mobile', hasTouch: name !== 'desktop' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let publication = fixture.fixtures[0].state;
    await page.route('http://staircase.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/') return route.fulfill({ headers: mapHeaders(fixture.document), contentType: 'text/html', body: fixture.document });
      if (path === '/state') return route.fulfill({ headers: mapHeaders(fixture.document), contentType: 'application/json', body: JSON.stringify(publication) });
      errors.push(route.request().postDataJSON());
      return route.fulfill({ status: 204 });
    });
    await page.goto('http://staircase.test/');
    await page.waitForFunction(() => lastState?.status === 'display');
    // Drive explicit synthetic scene transitions below. An independent polling
    // response must not race those deliberate before/after publications.
    await page.evaluate(() => { reloading = true; });
    for (const entry of fixture.fixtures) {
      publication = structuredClone(entry.state);
      await page.evaluate(state => { selected = null; floorView = { mode: 'follow' }; draw(state); }, publication);
      const group = page.locator('.door[data-door="' + entry.marker.id + '"]');
      assert.equal(await group.locator('polyline').count(), 2, 'outline and access strokes retain every corner');
      assert.equal(await group.locator('line').count(), 0, 'no diagonal chord');
      assert.equal(await group.locator('polyline:not(.door-border)').getAttribute('points'), entry.marker.polyline.map(p => p.join(',')).join(' '));
      assert.equal(await group.locator('polyline:not(.door-border)').evaluate(node => getComputedStyle(node).stroke), 'rgb(237, 105, 101)');
      assert.equal(await group.locator('.key-symbol').getAttribute('transform'), 'translate(' + entry.marker.polyline[1].join(' ') + ')');
      assert.deepEqual(await page.locator('#map .room').evaluateAll(nodes => nodes.map(node => node.dataset.region)), entry.marker.rooms, 'only owning outline is explored');
      assert.equal(await page.locator('#doors .door-room-link').count(), 0, 'hidden target has no navigation or name');
      assert((await page.locator('#doors').textContent()).includes('Unexplored room'));
      const room = page.locator('#map .room');
      await room.focus();
      await page.keyboard.press('Enter');
      assert.equal(await room.getAttribute('tabindex'), '0');
      await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
      await page.locator('#map').focus();
      await page.keyboard.press('ArrowRight');
      const view = await page.locator('#map').getAttribute('viewBox');
      const changed = structuredClone(publication);
      changed.doors[0].unlock_state = 'UNLOCKED';
      changed.doors[0].state = 'UNCHECKED';
      publication = changed;
      await page.evaluate(state => draw(state), changed);
      assert.equal(await page.locator('#map').getAttribute('viewBox'), view, 'live update retains manual view');
      assert.equal(await group.locator('.key-symbol').count(), 0);
      assert.equal(await group.locator('.unlock-symbol').getAttribute('transform'), 'translate(' + entry.marker.polyline[1].join(' ') + ')');
      assert.equal(await group.locator('polyline:not(.door-border)').evaluate(node => getComputedStyle(node).strokeDasharray), '1.5px, 1px');
      await page.evaluate(state => draw(state), entry.state);
      assert.equal(await group.locator('.unlock-symbol').count(), 0);
      assert.equal(await group.locator('.key-symbol').count(), 1, 'earlier state reverses access symbols');
      const hit = await group.locator('polyline:not(.door-border)').evaluate(node => {
        const point = node.ownerSVGElement.createSVGPoint();
        [point.x, point.y] = node.points.getItem(1) ? [node.points.getItem(1).x, node.points.getItem(1).y] : [NaN, NaN];
        return node.isPointInStroke(point);
      });
      assert(hit, 'the middle contour turn remains in the SVG hit area');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    }
    // Same native region has multiple source aliases. Selection cannot borrow
    // the other creator's key, and alias visits must publish only one outline.
    const alias = fixture.fixtures.find(entry => entry.marker.observation_ids[0].startsWith('05-08:'));
    publication = structuredClone(alias.state);
    const visit = publication.rooms[0];
    publication.current = '05-11';
    publication.current_detail = { ...visit, room: '05-11' };
    publication.rooms = [publication.current_detail];
    publication.explored_areas[publication.area] = publication.rooms;
    await page.evaluate(state => { selected = null; draw(state); }, publication);
    const aliasMarker = page.locator('.door[data-door="' + alias.marker.id + '"]');
    assert.equal(await aliasMarker.locator('.key-symbol').count(), 0);
    assert(await aliasMarker.evaluate(node => node.classList.contains('UNCHECKED')));
    assert.equal(await page.locator('#map .room').count(), 1);
    // An inspected departed wall still uses fresh state, while the current
    // source moves to a different explored region on the same floor.
    const departed = fixture.fixtures[0];
    const arrived = fixture.fixtures.find(entry => entry.state.map_region !== departed.state.map_region);
    publication = structuredClone(departed.state);
    publication.current = arrived.state.current;
    publication.map_region = arrived.state.map_region;
    publication.current_detail = arrived.state.current_detail;
    publication.rooms.push(arrived.state.rooms[0]);
    publication.explored_areas[publication.area] = publication.rooms;
    await page.evaluate(({ state, region }) => { draw(state); inspectRoom(state.area, region); }, { state: publication, region: departed.state.map_region });
    const departedMarker = page.locator('.door[data-door="' + departed.marker.id + '"]');
    assert.equal(await departedMarker.locator('.key-symbol').count(), 1);
    const departedView = await page.locator('#map').getAttribute('viewBox');
    publication.doors[0].state = 'OPEN';
    await page.evaluate(state => draw(state), publication);
    assert.equal(await departedMarker.locator('.key-symbol').count(), 0);
    assert(await departedMarker.evaluate(node => node.classList.contains('OPEN')));
    assert.equal(await page.locator('#map').getAttribute('viewBox'), departedView);
    await page.screenshot({ path: resolve(output, name + '.png'), fullPage: true });
    assert.deepEqual(errors, []);
    report.layouts.push({ name, viewport, checked_markers: fixture.fixtures.length, errors, overflow: false });
    await page.close();
  }
} finally {
  await browser.close();
}
writeFileSync(resolve(output, 'report.json'), JSON.stringify(report, null, 2) + '\n');
console.log('Ten contour markers passed four layouts, source-side symbols, hit areas, keyboard and manual view checks.');
