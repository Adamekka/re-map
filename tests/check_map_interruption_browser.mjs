// Run with Bun and Playwright: bun tests/check_map_interruption_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { chromium } from 'playwright';
import { mapHeaders } from './map_browser_response.mjs';

assert(process.argv[2], 'Pass the Python executable used for tracker tests');
const setup = spawnSync(process.argv[2], ['-c', `
import json,sys
from pathlib import Path
from uuid import uuid4
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
    cases.append({'document':map_page(catalog,uuid4()).decode(),'state':map_state(tracker)})
print(json.dumps(cases))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const browser = await chromium.launch();
try {
  for (const fixture of JSON.parse(setup.stdout)) for (const viewport of [{ width: 1280, height: 1060 }, { width: 390, height: 844 }]) {
    let state = structuredClone(fixture.state);
    const page = await browser.newPage({ viewport });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://interrupted-map.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/client-error') {
        errors.push(route.request().postDataJSON());
        return route.fulfill({ status: 204 });
      }
      assert(['/', '/state'].includes(path), 'Unexpected request: ' + path);
      return route.fulfill({ headers: mapHeaders(fixture.document), contentType: path === '/' ? 'text/html' : 'application/json', body: path === '/' ? fixture.document : JSON.stringify(state) });
    });
    await page.goto('http://interrupted-map.test/');
    await page.waitForFunction(() => document.getElementById('map').tabIndex === 0);
    const map = page.locator('#map'), rooms = page.locator('#map .room');
    const details = page.locator('#room-name');
    assert.equal(await rooms.count(), 2);
    for (const room of await rooms.all()) {
      assert.equal(await room.getAttribute('tabindex'), '0');
      assert(await room.isEnabled());
    }
    const ids = await rooms.evaluateAll(nodes => nodes.map(node => node.dataset.region));
    const first = page.locator('#map .room[data-region="' + ids[0] + '"]');
    const second = page.locator('#map .room[data-region="' + ids[1] + '"]');
    await first.press('Enter');
    await map.press('=');
    await first.focus();
    const inspection = () => page.evaluate(() => ({
      selected, selectedArea, floorView, viewHistory, viewport,
      name: document.getElementById('room-name').textContent,
      roomId: document.getElementById('room-id').textContent,
      selectedOutline: document.querySelector('#map .room.selected').dataset.region,
      box: document.getElementById('map').getAttribute('viewBox'),
    }));
    const chosen = await inspection();
    assert.equal(chosen.selected, ids[0]);
    assert.equal(chosen.viewport.mode, 'manual');
    assert(chosen.viewport.zoom > 1);
    assert.equal(chosen.viewHistory.length, 1);
    const geometry = await rooms.evaluateAll(nodes => nodes.map(node => [node.dataset.region, node.querySelector('path').getAttribute('d')]));

    state = { status: 'waiting', error: 'Tracking interrupted.' };
    await page.waitForFunction(() => lastState.status === 'waiting');
    assert.deepEqual(await rooms.evaluateAll(nodes => nodes.map(node => [node.dataset.region, node.querySelector('path').getAttribute('d')])), geometry);
    assert.equal(await map.getAttribute('tabindex'), '-1');
    for (const room of await rooms.all()) {
      assert.equal(await room.getAttribute('tabindex'), '-1', 'retained outlines must leave the tab order');
      assert.equal(await room.getAttribute('aria-disabled'), 'true');
      assert(await room.isDisabled());
    }
    assert(await details.evaluate(node => node === document.activeElement), 'interruption must move outline focus to room details');
    assert(await details.evaluate(node => { const box = node.getBoundingClientRect(); return box.top >= 0 && box.bottom <= innerHeight; }), 'replacement focus must be visible');
    for (let tabs = 0; tabs < 3; tabs++) {
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(() => document.activeElement.matches('#map, #map .room')), false, 'normal Tab must skip the interrupted map and its rooms');
    }
    await second.focus();
    for (const key of ['Enter', 'Space']) await page.keyboard.press(key);
    assert.deepEqual(await inspection(), chosen, 'real keyboard activation must not change an interrupted inspection');
    // aria-disabled on SVG does not enforce behavior; dispatch also exercises
    // the actual room handlers without depending on browser pointer suppression.
    await second.evaluate(node => {
      for (const key of ['Enter', ' ']) node.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }));
      node.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    });
    assert.deepEqual(await inspection(), chosen, 'room handlers must reject interrupted activation');
    await map.scrollIntoViewIfNeeded();
    const label = await second.locator('text').boundingBox();
    assert(label);
    // Label layout places this point inside the real room outline. A raw mouse
    // click can reach disabled SVG, unlike Playwright's guarded locator.click.
    await page.evaluate(() => document.addEventListener('click', event => {
      window.interruptedRoomClick = { trusted: event.isTrusted, region: event.target.closest('.room')?.dataset.region };
    }, { capture: true, once: true }));
    await page.mouse.click(label.x + label.width / 2, label.y + label.height / 2);
    assert.deepEqual(await page.evaluate(() => window.interruptedRoomClick), { trusted: true, region: ids[1] });
    assert.deepEqual(await inspection(), chosen, 'a real pointer click must not change an interrupted inspection');
    state = { status: 'waiting', error: 'Still waiting for game.' };
    await page.waitForFunction(() => lastState.error === 'Still waiting for game.');
    assert.deepEqual(await inspection(), chosen, 'repeated waiting must retain selection, history and viewport');
    await details.focus();

    state = structuredClone(fixture.state);
    await page.waitForFunction(() => lastState.status === 'display');
    assert.deepEqual(await inspection(), chosen, 'recovery must restore the chosen inspection');
    assert(await details.evaluate(node => node === document.activeElement), 'recovery must retain replacement focus');
    for (const room of await rooms.all()) {
      assert.equal(await room.getAttribute('tabindex'), '0');
      assert(await room.isEnabled());
    }
    await second.press('Enter');
    assert.equal((await inspection()).selected, ids[1]);
    assert(await second.evaluate(node => node === document.activeElement));
    await first.press('Space');
    assert.equal((await inspection()).selected, ids[0]);
    assert(await first.evaluate(node => node === document.activeElement));
    const recoveredLabel = await second.locator('text').boundingBox();
    assert(recoveredLabel);
    await page.mouse.click(recoveredLabel.x + recoveredLabel.width / 2, recoveredLabel.y + recoveredLabel.height / 2);
    assert.equal((await inspection()).selected, ids[1], 'ordinary pointer selection must work after recovery');
    assert(await second.evaluate(node => node === document.activeElement));
    state.current_detail.reason = 'Fresh room observation.';
    await page.waitForFunction(() => lastState.current_detail.reason === 'Fresh room observation.');
    assert(await second.evaluate(node => node === document.activeElement), 'fresh polls must retain restored outline focus');

    await map.focus();
    const beforeMapInterruption = await inspection();
    const readable = state;
    state = { status: 'waiting', error: 'Map focus interrupted.' };
    await page.waitForFunction(() => lastState.status === 'waiting');
    assert(await details.evaluate(node => node === document.activeElement), 'interruption must also recover focus from the SVG parent');
    assert(await details.evaluate(node => { const box = node.getBoundingClientRect(); return box.top >= 0 && box.bottom <= innerHeight; }));
    // Interrupted tracking removes the live-current annotation, while the
    // inspected room identity and chosen view remain available for recovery.
    assert.deepEqual(await inspection(), { ...beforeMapInterruption, roomId: 'Room ' + fixture.state.current });
    state = readable;
    await page.waitForFunction(() => lastState.status === 'display');
    assert.deepEqual(await inspection(), beforeMapInterruption);
    assert(await details.evaluate(node => node === document.activeElement));
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log('RE1 and RE2 interrupted map checks passed on desktop/mobile: disabled outlines, stable inspection, focus recovery and resumed activation.');
} finally {
  await browser.close();
}
