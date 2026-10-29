// RE2-DOOR-005: synthetic shared-renderer checks, with private screenshots.
// NODE_PATH=<runtime node_modules> bun tests/check_door_unlock_browser.mjs <python> <private-output-directory>
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
from tracker.exploration_state import Tracker,DoorDetail,DoorUnlockState
from ui.map_view import map_page,map_state
p=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json'))
plan=p.map_layout.document['areas'][0]
t=Tracker(player_heading=90)
for room in plan['rooms']:
    source=room['room_ids'][0]
    if source not in ('00-00','00-01','00-02'): continue
    t.mark_current(RoomId(0,int(source.split('-')[1],16)))
    t.region_visits[plan['id']+':'+room['id']]=source
t.mark_current(RoomId(0,2));t.current_region=plan['id']+':02'
marker=next(door for door in plan['doors'] if any(obs.startswith('00-01:') for obs in door['observation_ids']) and any(obs.startswith('00-00:') for obs in door['observation_ids']))
forward=next(obs for obs in marker['observation_ids'] if obs.startswith('00-01:'))
reverse=next(obs for obs in marker['observation_ids'] if obs.startswith('00-00:'))
t.doors=(
    DoorDetail(RoomId(0,1),RoomId(0,0),'UNCHECKED','Unlocked; access unconfirmed',observation_id=forward,unlock_state=DoorUnlockState.Unlocked),
    DoorDetail(RoomId(0,0),RoomId(0,1),'LOCKED','Club Key',key_label='Club Key',observation_id=reverse,unlock_state=DoorUnlockState.Locked),
)
print(json.dumps({'html':map_page(p.map_layout.document,uuid4()).decode(),'state':map_state(t),'marker':marker,'forward':forward,'reverse':reverse}))
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
    let state = structuredClone(fixture.state);
    await page.route('http://door-unlock.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/') return route.fulfill({ headers: mapHeaders(fixture.html), contentType: 'text/html', body: fixture.html });
      if (path === '/state') return route.fulfill({ headers: mapHeaders(fixture.html), contentType: 'application/json', body: JSON.stringify(state) });
      errors.push('Unexpected request: ' + path);
      return route.fulfill({ status: 404 });
    });
    await page.goto('http://door-unlock.test/');
    await page.waitForFunction(() => document.querySelector('.room.current'));
    const result = await page.evaluate(fixture => {
      const base = fixture.state, area = base.area;
      const shop = base.explored_areas[area].find(visit => visit.room === '00-01');
      const street = base.explored_areas[area].find(visit => visit.room === '00-00');
      const forward = base.doors.find(door => door.observation_id === fixture.forward);
      const reverse = base.doors.find(door => door.observation_id === fixture.reverse);
      const selector = '[data-door="' + fixture.marker.id + '"]';
      const cases = [
        ['UNCHECKED', 'UNKNOWN', 'Unlocked; access unconfirmed', false],
        ['UNCHECKED', 'LOCKED', 'Door conditions unresolved', false],
        ['UNCHECKED', 'UNLOCKED', 'Access unconfirmed', true],
        ['UNCHECKED', 'LOCKED', 'Door conditions unresolved', false],
        ['UNCHECKED', 'UNLOCKED', 'Unlocked; access unconfirmed', true],
        ['BLOCKED', 'UNLOCKED', 'Unlocked; door inactive', true],
        ['BLOCKED', 'LOCKED', 'Door is inactive', false],
        ['OPEN', 'UNLOCKED', 'Unlocked', true],
      ];
      const results = [];
      for (const [access, unlock, label, unlocked] of cases) {
        const current = access === 'BLOCKED' || access === 'OPEN' ? shop : base.current_detail;
        selected = shop.id; selectedArea = area; floorView = { mode: 'follow' };
        // Keep a stale key name deliberately: only the typed knowledge may
        // hide it or display an unlocked cue, regardless of label wording.
        const door = { ...forward, state: access, unlock_state: unlock, label, key_label: 'Spade Key' };
        draw({ ...base, current: current.room, map_region: current.id, current_detail: current, doors: [door, reverse] });
        const marker = document.querySelector(selector);
        if (!marker.classList.contains(access) || marker.classList.contains('unlocked') !== unlocked) throw new Error('Unlock knowledge changed access or was lost');
        if (Boolean(marker.querySelector('.unlock-symbol')) !== unlocked) throw new Error('Incorrect open-padlock cue');
        if (Boolean(marker.querySelector('.key-symbol')) === unlocked) throw new Error('Key emblem did not reverse with unlock knowledge');
        if (unlocked) {
          // The badge occludes the bar, so inspect the visible frame too.
          const frame = getComputedStyle(marker.querySelector('.unlock-symbol rect'));
          const stroke = access === 'BLOCKED' ? 'rgb(237, 105, 101)' : access === 'OPEN' ? 'rgb(113, 182, 207)' : 'rgb(165, 213, 172)';
          if (frame.stroke !== stroke || (frame.strokeDasharray !== 'none') !== (access === 'UNCHECKED')) throw new Error('Unlocked badge hides the door access state');
        }
        const status = document.querySelector('#doors .entry-status');
        if (Boolean(status.querySelector('.unlocked')) !== unlocked || status.textContent !== label + (unlocked ? '' : ' · Spade Key')) throw new Error('Door list lost independent knowledge or its label');
        if (access === 'BLOCKED' && (!status.querySelector('.blocked') || getComputedStyle(marker.querySelector('line:not(.door-border)')).stroke !== 'rgb(237, 105, 101)')) throw new Error('Unlock cue hid inactive access');
        if (access === 'UNCHECKED' && unlocked) {
          const line = marker.querySelector('line:not(.door-border)');
          if (getComputedStyle(line).stroke !== 'rgb(165, 213, 172)' || getComputedStyle(line).strokeDasharray === 'none' || !status.querySelector('.neutral')) throw new Error('Unconfirmed access became visually Open');
          const border = getComputedStyle(marker.querySelector('.door-border'));
          if (border.stroke !== 'rgb(16, 21, 27)' || border.strokeDasharray !== 'none') throw new Error('Unlock styling overwrote the dark doorway border');
        }
        results.push({ access, unlock, cue: unlocked });
      }
      // Selecting the opposite source must restore that side's own key.
      selected = street.id;
      draw(base);
      let marker = document.querySelector(selector);
      if (marker.querySelector('.unlock-symbol') || marker.querySelector('.key-symbol')?.getAttribute('aria-label') !== 'Club Key') throw new Error('Unlock knowledge crossed sides');
      selected = shop.id;
      draw({ ...base, doors: [reverse] });
      marker = document.querySelector(selector);
      if (!marker.classList.contains('UNCHECKED') || marker.querySelector('.unlock-symbol,.key-symbol')) throw new Error('Missing selected side borrowed an opposite observation');
      // No side is selected here. Equal access does not resolve conflicting
      // unlock knowledge or two creators on one observation identity.
      for (const doors of [
        [forward, { ...reverse, state: 'UNCHECKED' }],
        [forward, { ...forward }],
        [forward, { ...forward, unlock_state: 'UNKNOWN' }],
      ]) {
        selected = null;
        draw({ ...base, doors });
        if (document.querySelector(selector + ' .unlock-symbol')) throw new Error('Ambiguous observations acquired guessed unlock knowledge');
      }
      // An overlapping unresolved variant must not cover the known cue.
      const plan = areas.get(area), duplicate = { ...fixture.marker, id: 'synthetic-overlap', observation_ids: ['synthetic-unbound'] };
      plan.doors.push(duplicate);
      selected = shop.id;
      draw(base);
      const symbol = document.querySelector(selector + ' .unlock-symbol');
      const center = new DOMPoint(0, 0).matrixTransform(symbol.getScreenCTM());
      if (document.elementFromPoint(center.x, center.y)?.closest('.unlock-symbol') !== symbol) throw new Error('Overlapping marker covers unlocked cue');
      plan.doors.pop();
      // Only the entered shop remains visible. Knowing an unlocked boundary
      // must never reveal its destination outline, name, or visit history.
      const hidden = { ...base, current: shop.room, map_region: shop.id, current_detail: shop, rooms: [shop], explored_areas: { [area]: [shop] }, doors: [{ ...forward, target_visited: false }] };
      draw(hidden);
      if (document.querySelectorAll('#map .room').length !== 1 || !document.querySelector(selector + ' .unlock-symbol') || !document.querySelector('#doors .entry-name').textContent.includes('Unexplored room')) throw new Error('Unlock knowledge revealed an unexplored room');
      const box = svg.getAttribute('viewBox');
      zoomMap(.8, new DOMPoint(...viewport.box.slice(0, 2)));
      const zoomed = svg.getAttribute('viewBox');
      draw({ ...hidden, doors: [{ ...hidden.doors[0], unlock_state: 'LOCKED', key_label: 'Spade Key', label: 'Door conditions unresolved' }] });
      if (svg.getAttribute('viewBox') !== zoomed || box === zoomed) throw new Error('Flag reversal reset the chosen map view');
      return { cases: results, screenshotState: hidden };
    }, fixture);
    state = result.screenshotState;
    await page.evaluate(state => { viewport = { mode: 'empty' }; draw(state); }, state);
    const overflow = await page.evaluate(() => ({
      page: document.documentElement.scrollWidth > innerWidth,
      rows: [...document.querySelectorAll('#doors li')].filter(row => row.scrollWidth > row.clientWidth).length,
    }));
    assert.equal(overflow.page, false);
    assert.equal(overflow.rows, 0);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: `${output}/unlocked-${name}.png`, fullPage: true });
    report.push({ name, cases: result.cases, overflow, pageErrors: errors });
    await page.close();
  }
} finally {
  await browser.close();
}
writeFileSync(`${output}/browser-result.json`, JSON.stringify(report, null, 2) + '\n');
console.log('Door unlock browser checks passed on desktop and mobile; private renders: ' + output);
