// Run with Bun and Playwright: bun tests/check_map_keyboard_browser.mjs <python>
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
from tracker.exploration_state import Tracker
from ui.map_view import map_page,map_state
cases=[]
for filename in ('floor_plans_slus00551.json','floor_plans_slus00748.json'):
    catalog=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json')).map_layout.document if filename=='floor_plans_slus00748.json' else json.loads((Path('data')/filename).read_text())
    area=catalog['areas'][0]
    tracker=Tracker(player_heading=90)
    for region in area['rooms'][:2]:
        source=region['room_ids'][0]
        tracker.mark_current(RoomId(*[int(part,16) for part in source.split('-')]))
        tracker.current_region=area['id']+':'+region['id']
        tracker.region_visits[tracker.current_region]=source
    cases.append({'document':map_page(catalog).decode(),'state':map_state(tracker)})
print(json.dumps(cases))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const browser = await chromium.launch();
try {
  for (const fixture of JSON.parse(setup.stdout)) {
    let state = fixture.state;
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://keyboard-map.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/client-error') {
        errors.push(route.request().postDataJSON());
        console.error('Map client error', errors.at(-1));
        return route.fulfill({ status: 204 });
      }
      assert(['/', '/state'].includes(path), 'Unexpected request: ' + path);
      return route.fulfill({ contentType: path === '/' ? 'text/html' : 'application/json', body: path === '/' ? fixture.document : JSON.stringify(state) });
    });
    await page.goto('http://keyboard-map.test/');
    const map = page.locator('#map');
    await page.waitForFunction(() => document.getElementById('map').getAttribute('tabindex') === '0');
    assert.equal(await map.getAttribute('role'), 'group', 'interactive rooms must remain accessible inside the map');
    const view = () => map.getAttribute('viewBox').then(value => value.split(' ').map(Number));
    const initial = await view(), scene = await page.locator('#map .room').count();
    await page.getByRole('button', { name: 'Fit explored rooms', exact: true }).focus();
    await page.keyboard.press('Tab');
    assert(await map.evaluate(node => node === document.activeElement), 'the map must be reachable in the normal tab order');
    assert.equal(await map.evaluate(node => getComputedStyle(node).outlineWidth), '2px', 'keyboard focus needs a visible map outline');
    assert.match(await map.ariaSnapshot(), /button/, 'assistive technology must be able to reach the room controls');
    for (const [key, axis, direction] of [['ArrowRight', 0, 1], ['ArrowLeft', 0, -1], ['ArrowDown', 1, 1], ['ArrowUp', 1, -1]]) {
      const before = await view();
      await page.keyboard.press(key);
      const after = await view();
      assert(Math.abs(after[axis] - before[axis] - direction * before[axis + 2] / 10) < 1e-8, key);
      assert.equal(after[1 - axis], before[1 - axis]);
      assert.deepEqual(after.slice(2), before.slice(2), 'panning must retain zoom');
      assert(await map.evaluate(node => node === document.activeElement));
    }
    assert.equal(await page.evaluate(() => scrollY), 0, 'map arrows must not scroll the page');
    await page.keyboard.press('Shift+Equal');
    const zoomed = await view();
    assert(zoomed[2] < initial[2]);
    await page.keyboard.press('-');
    assert(Math.abs((await view())[2] - initial[2]) < 1e-8);
    await page.keyboard.press('=');
    assert((await view())[2] < initial[2]);
    for (let i = 0; i < 12; i++) await page.keyboard.press('+');
    assert.equal(await page.locator('#zoom-level').textContent(), '800%');
    const limit = await view();
    await map.evaluate(node => node.addEventListener('keydown', event => { window.lastMapKeyPrevented = event.defaultPrevented; }));
    await page.keyboard.press('+');
    assert.deepEqual(await view(), limit, 'keyboard zoom must respect the shared limit');
    for (const key of ['Control+ArrowLeft', 'Meta+ArrowRight', 'Alt+ArrowDown', 'Control+Equal']) {
      await page.keyboard.press(key);
      assert.deepEqual(await view(), limit, 'modified keys must retain browser behavior: ' + key);
      assert.equal(await page.evaluate(() => window.lastMapKeyPrevented), false, 'modified keys must not suppress browser shortcuts');
    }
    await page.keyboard.press('0');
    assert.deepEqual(await view(), initial, 'zero must reuse fit explored rooms');
    const room = page.locator('#map .room').first();
    await room.press('Enter');
    const selected = await page.locator('.room.selected').getAttribute('aria-label');
    assert.equal(await page.locator('.room.selected').evaluate(node => getComputedStyle(node).outlineStyle), 'none', 'native SVG focus rings must not cover adjacent doors');
    assert.equal(await page.locator('.room.selected > path').first().evaluate(node => getComputedStyle(node).stroke), 'rgb(165, 239, 255)', 'focus must highlight the room wall');
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('.room.selected').getAttribute('aria-label'), selected);
    assert(await page.locator('.room.selected').evaluate(node => node === document.activeElement), 'pan must retain the focused room');
    const manual = await view();
    state.player_heading = 180;
    await page.waitForFunction(() => document.querySelector('.player path')?.getAttribute('transform')?.includes('rotate(180)'));
    assert.deepEqual(await view(), manual, 'live heading updates must retain keyboard navigation');
    assert.equal(await page.locator('#map .room').count(), scene, 'navigation must not reveal rooms');
    for (const visit of [state.current_detail, ...state.rooms, ...Object.values(state.explored_areas).flat()]) {
      if (visit.room !== state.current) continue;
      visit.items = [{ label: 'Green Herb', state: 'available', quantity: 1, quantity_is_unit_count: false }];
      visit.items_complete = true;
      visit.state = 'INCOMPLETE';
    }
    await page.waitForFunction(() => document.getElementById('remaining-items').textContent.includes('Green Herb'));
    assert(await page.locator('.room.selected').evaluate(node => node === document.activeElement), 'a live item update must retain room keyboard focus');
    const tabbedRoom = page.locator('#map .room').last();
    await tabbedRoom.focus();
    const focusedName = await tabbedRoom.getAttribute('aria-label');
    assert.equal(await tabbedRoom.locator('path').first().evaluate(node => getComputedStyle(node).stroke), 'rgb(217, 246, 255)', 'a focused current room must retain its white wall');
    state.current_detail.reason = 'A fresh room check.';
    await page.waitForFunction(() => lastState.current_detail.reason === 'A fresh room check.');
    assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')), focusedName, 'redraw must retain a tabbed room without changing selection');
    assert.equal(await page.locator('.room.selected').getAttribute('aria-label'), selected);
    state.doors = [{ source: state.explored_areas[state.area][0].room, target: state.current, target_visited: true, state: 'OPEN', label: 'Unlocked', key_label: '', observation_id: '', unlock_state: 'UNKNOWN', interaction_id: '' }];
    await page.waitForFunction(() => document.getElementById('doors').textContent.includes('Unlocked'));
    assert.equal(await page.evaluate(() => document.activeElement.getAttribute('aria-label')), focusedName, 'a live door update must retain the exact tabbed room');
    assert.deepEqual(await view(), manual);
    await page.locator('.room.selected').focus();
    state.explored_areas[state.area] = state.explored_areas[state.area].filter(visit => visit.room === state.current);
    state.rooms = state.explored_areas[state.area];
    await page.waitForFunction(() => document.querySelectorAll('#map .room').length === 1);
    assert(await map.evaluate(node => node === document.activeElement), 'when history removes a focused outline, focus must move to the map');
    const search = page.getByLabel('Find item or room', { exact: true });
    await search.fill('0-+');
    await search.press('ArrowLeft');
    state.current_detail.reason = 'Another fresh room check.';
    await page.waitForFunction(() => lastState.current_detail.reason === 'Another fresh room check.');
    assert(await search.evaluate(node => node === document.activeElement), 'live map updates must not steal focus from search');
    assert.deepEqual(await view(), manual, 'typing and editing outside the map must not navigate it');
    state = { status: 'waiting', error: 'Waiting for game.' };
    await page.waitForFunction(() => document.getElementById('map').getAttribute('tabindex') === '-1');
    await map.focus();
    for (const key of ['ArrowRight', '+', '0']) await page.keyboard.press(key);
    assert.deepEqual(await view(), manual, 'interrupted maps must ignore viewport keys');
    state = structuredClone(fixture.state);
    state.map_region = 'unoutlined';
    state.explored_areas = { [state.area]: [] };
    await page.waitForFunction(() => document.querySelectorAll('#map .room').length === 0);
    assert.equal(await map.getAttribute('tabindex'), '-1');
    for (const key of ['ArrowRight', '+', '0']) await map.press(key);
    assert.deepEqual(await view(), manual, 'empty maps must ignore viewport keys');
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log('RE1 and RE2 keyboard map navigation passed');
} finally {
  await browser.close();
}
