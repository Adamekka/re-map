// Run with Bun and Playwright: bun tests/check_map_history_browser.mjs <python>
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
from tracker.exploration_state import Tracker,DoorDetail
from ui.map_view import map_page,map_state
cases=[]
for filename in ('floor_plans_slus00551.json','floor_plans_slus00748.json'):
    catalog=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json')).map_layout.document if filename=='floor_plans_slus00748.json' else json.loads((Path('data')/filename).read_text())
    tracker=Tracker(player_heading=90)
    for area in catalog['areas'][:2]:
        for region in area['rooms'][:2]:
            source=region['room_ids'][0]
            tracker.mark_current(RoomId(*[int(part,16) for part in source.split('-')]))
            tracker.region_visits[area['id']+':'+region['id']]=source
    first,second=catalog['areas'][:2]
    current=first['rooms'][1]
    tracker.mark_current(RoomId(*[int(part,16) for part in current['room_ids'][0].split('-')]))
    tracker.current_region=first['id']+':'+current['id']
    # This synthetic connection exercises published-view navigation, not native passage.
    tracker.doors=(DoorDetail(tracker.current,RoomId(*[int(part,16) for part in second['rooms'][0]['room_ids'][0].split('-')]),'OPEN','Open'),)
    cases.append({'document':map_page(catalog).decode(),'state':map_state(tracker),'first':first['id'],'second':second['id'],'initialId':current['id'],'otherId':first['rooms'][0]['id']})
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
    await page.route('http://map-history.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      assert(['/', '/state'].includes(path), 'Unexpected request: ' + path);
      return route.fulfill({ contentType: path === '/' ? 'text/html' : 'application/json', body: path === '/' ? fixture.document : JSON.stringify(state) });
    });
    await page.goto('http://map-history.test/');
    await page.waitForFunction(() => !document.getElementById('floor').disabled);
    const back = page.getByRole('button', { name: 'Back to previous room', exact: true });
    assert.equal(await back.count(), 1);
    assert(await back.isDisabled());
    const map = page.locator('#map'), floor = page.getByLabel('Floor', { exact: true });
    const follow = page.getByRole('button', { name: 'Follow player', exact: true });
    const initial = page.locator('.room[data-region="' + fixture.initialId + '"]');
    const other = page.locator('.room[data-region="' + fixture.otherId + '"]');
    await map.focus();
    await page.keyboard.press('+');
    await page.keyboard.press('ArrowRight');
    const chosenView = await map.getAttribute('viewBox');
    assert(await back.isDisabled(), 'zoom and pan alone must not add inspection history');
    await other.press('Enter');
    assert(await back.isEnabled());
    for (const visit of [state.current_detail, ...state.rooms, ...Object.values(state.explored_areas).flat()]) {
      if (visit.room === state.current) Object.assign(visit, { state: 'CLEARED', items_complete: true, items: [] });
    }
    await page.waitForFunction(() => lastState.current_detail.state === 'CLEARED');
    await back.press('Enter');
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), fixture.initialId);
    assert.equal(await page.locator('#completion').textContent(), 'Cleared', 'Back must display fresh verdicts');
    assert.equal(await map.getAttribute('viewBox'), chosenView, 'Back must restore chosen zoom and pan');
    assert(await initial.evaluate(node => node === document.activeElement));
    assert(await back.isDisabled());
    await follow.click();
    await initial.press('Enter');
    assert(await back.isDisabled(), 'reselecting the same view must not create a redundant Back entry');
    await other.press('Enter');
    await floor.selectOption(fixture.second);
    await back.press('Space');
    assert.equal(await floor.inputValue(), fixture.first);
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), fixture.otherId);
    await back.press('Enter');
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), fixture.initialId);
    assert(await back.isDisabled());
    await follow.click();
    await page.locator('#doors .door-room-link').press('Enter');
    assert.equal(await floor.inputValue(), fixture.second);
    assert(await back.isEnabled());
    await back.focus();
    const beforeInterruption = state;
    state = { status: 'waiting', error: 'Tracking interrupted.' };
    await page.waitForFunction(() => document.getElementById('floor').disabled);
    assert(await back.isDisabled());
    assert(await page.locator('#room-name').evaluate(node => node === document.activeElement), 'interruption must not strand focus on disabled Back');
    state = beforeInterruption;
    await page.waitForFunction(() => !document.getElementById('floor').disabled);
    assert(await back.isEnabled(), 'recovery must retain valid view history');
    await back.click();
    assert.equal(await floor.inputValue(), fixture.first);
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), fixture.initialId);
    const otherName = await other.getAttribute('aria-label');
    await page.locator('#incomplete-checks .room-link').filter({ has: page.getByText(otherName, { exact: true }) }).press('Enter');
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), fixture.otherId);
    await back.press('Enter');
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), fixture.initialId, 'item results must participate in the same Back path');
    await follow.click();
    await page.locator('#doors .door-room-link').press('Enter');
    await follow.click();
    assert(await back.isDisabled(), 'Follow player must reset manual inspection history');
    await page.locator('#doors .door-room-link').press('Enter');
    await back.focus();
    const onlyVisit = state.explored_areas[fixture.second][0];
    state = { ...state, area: fixture.second, current: onlyVisit.room, current_detail: onlyVisit, map_region: onlyVisit.id, rooms: [onlyVisit], explored_areas: { [fixture.second]: [onlyVisit] }, doors: [] };
    await page.waitForFunction(() => document.querySelectorAll('#map .room').length === 1);
    assert(await back.isDisabled(), 'removed exploration must not be reachable through Back');
    assert(await page.locator('#room-name').evaluate(node => node === document.activeElement), 'removing the last Back entry must move focus to room details');
    const unmappedDetails = { ...fixture.state.current_detail, id: '' };
    const mappedOther = fixture.state.explored_areas[fixture.first][0];
    state = { ...fixture.state, area: 'unmapped', map_region: '', current: unmappedDetails.room, current_detail: unmappedDetails, rooms: [], explored_areas: { ...fixture.state.explored_areas, unmapped: [] }, map_error: 'No room outline is available.' };
    await page.waitForFunction(() => lastState.area === 'unmapped');
    await follow.click();
    assert.equal(await page.locator('#map .room').count(), 0);
    await floor.selectOption(fixture.second);
    assert(await back.isEnabled(), 'a current room without an outline can be returned to while it stays current');
    await back.press('Enter');
    assert.equal(await floor.inputValue(), 'unmapped');
    assert(await page.locator('#room-name').evaluate(node => node === document.activeElement), 'Back to an unoutlined room must focus its details');
    await floor.selectOption(fixture.second);
    const unmappedOption = await floor.locator('option[value="unmapped"]').elementHandle();
    await floor.focus();
    state = { ...state, current: mappedOther.room, current_detail: { ...mappedOther, id: '' } };
    await page.waitForFunction(current => lastState.current === current, mappedOther.room);
    assert(await back.isDisabled(), 'distinct unmapped rooms must not share one Back identity');
    assert.equal(await floor.locator('option[value="unmapped"]').textContent(), 'Room ' + mappedOther.room, 'unmapped floor labels must follow the fresh room identity');
    assert(await unmappedOption.evaluate(node => node.isConnected), 'updating a room label must preserve the native option');
    assert(await floor.evaluate(node => node === document.activeElement), 'updating a room label must preserve selector focus');
    await follow.click();
    await floor.focus();
    state = { ...state, current: unmappedDetails.room, current_detail: unmappedDetails };
    await page.waitForFunction(current => lastState.current === current, unmappedDetails.room);
    assert.equal(await floor.inputValue(), 'unmapped');
    assert.equal(await floor.locator('option[value="unmapped"]').textContent(), 'Room ' + unmappedDetails.room);
    assert(await unmappedOption.evaluate(node => node.isConnected));
    assert(await floor.evaluate(node => node === document.activeElement), 'a selected unmapped option must also retain focus while its label changes');
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log('RE1 and RE2 inspection history checks passed');
} finally {
  await browser.close();
}
