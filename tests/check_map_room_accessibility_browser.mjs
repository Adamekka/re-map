// Run with Bun and Playwright: bun tests/check_map_room_accessibility_browser.mjs <python>
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
from tracker.exploration_state import Tracker,ItemDetail
from ui.map_view import map_page,map_state
cases=[]
for filename in ('floor_plans_slus00551.json','floor_plans_slus00748.json'):
    catalog=Re2Profile.load(Path('profiles/re2_leon_a_slus00748.json')).map_layout.document if filename=='floor_plans_slus00748.json' else json.loads((Path('data')/filename).read_text())
    area,other=catalog['areas'][:2]
    tracker=Tracker(player_heading=90)
    rooms=[]
    for index,region in enumerate(area['rooms'][:3]):
        source=region['room_ids'][0]
        room=RoomId(*[int(part,16) for part in source.split('-')])
        tracker.mark_current(room)
        tracker.current_region=area['id']+':'+region['id']
        tracker.region_visits[tracker.current_region]=source
        tracker.update_room_items(room,int(index!=1),0,index!=2,index==0,index==2)
        if index==0:
            tracker.rooms[source].items=(ItemDetail('Green Herb','available',1,False),)
        rooms.append({'id':region['id'],'name':region['name'],'room':source})
    current=tracker.current
    current_region=tracker.current_region
    other_region=other['rooms'][0]
    other_room=RoomId(*[int(part,16) for part in other_region['room_ids'][0].split('-')])
    tracker.mark_current(other_room)
    tracker.region_visits[other['id']+':'+other_region['id']]=str(other_room)
    tracker.update_room_items(other_room,0,0,True,False,False)
    tracker.mark_current(current)
    tracker.current_region=current_region
    initial=map_state(tracker)
    first=RoomId(*[int(part,16) for part in rooms[0]['room'].split('-')])
    tracker.rooms[str(first)].items=(ItemDetail('Green Herb','taken',1,False),)
    tracker.update_room_items(first,1,1,True,False,False)
    collected=map_state(tracker)
    tracker.rooms[str(first)].items=(ItemDetail('Green Herb','available',1,False),)
    tracker.update_room_items(first,1,0,True,True,False)
    tracker.mark_current(first)
    tracker.current_region=area['id']+':'+rooms[0]['id']
    cases.append({'document':map_page(catalog,uuid4()).decode(),'initial':initial,'collected':collected,'moved':map_state(tracker),'rooms':rooms,'otherArea':other['id'],'otherRoom':{'id':other_region['id'],'name':other_region['name']}})
print(json.dumps(cases))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const browser = await chromium.launch();
try {
  for (const fixture of JSON.parse(setup.stdout)) {
    let state = structuredClone(fixture.initial);
    const page = await browser.newPage({ viewport: { width: 1280, height: 1060 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://room-accessibility.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/client-error') {
        errors.push(route.request().postDataJSON());
        return route.fulfill({ status: 204 });
      }
      assert(['/', '/state'].includes(path), 'Unexpected request: ' + path);
      return route.fulfill({ headers: mapHeaders(fixture.document), contentType: path === '/' ? 'text/html' : 'application/json', body: path === '/' ? fixture.document : JSON.stringify(state) });
    });
    await page.goto('http://room-accessibility.test/');
    await page.waitForFunction(() => document.querySelectorAll('#map .room').length === 3);
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Accessibility.enable');
    const room = entry => page.locator('#map .room[data-region="' + entry.id + '"]');
    async function checkDescription(entry, description) {
      const { root } = await cdp.send('DOM.getDocument');
      const { nodeId } = await cdp.send('DOM.querySelector', { nodeId: root.nodeId, selector: '#map .room[data-region="' + entry.id + '"]' });
      const { nodes } = await cdp.send('Accessibility.getPartialAXTree', { nodeId, fetchRelatives: false });
      assert.equal(nodes.length, 1);
      assert.equal(nodes[0].role.value, 'button');
      assert.equal(nodes[0].name.value, entry.name, 'room names must remain stable accessible names');
      // The computed browser description is the assistive-technology seam;
      // checking the attribute alone would miss SVG title naming behavior.
      assert.equal(nodes[0].description?.value, description, entry.name);
      assert.equal(await room(entry).locator(':scope > title').textContent(), description, 'native hover text must agree with the accessible description');
    }
    const [first, second, third] = fixture.rooms;
    const map = page.locator('#map');
    await map.focus();
    for (const [entry, description] of [[first, 'Items remain'], [second, 'Cleared'], [third, 'Item check incomplete · Current room · Selected room']]) {
      await page.keyboard.press('Tab');
      assert(await room(entry).evaluate(node => node === document.activeElement), 'normal Tab must reach each named room');
      await checkDescription(entry, description);
    }
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Enter');
    assert(await room(second).evaluate(node => node === document.activeElement));
    await checkDescription(second, 'Cleared · Selected room');
    await checkDescription(third, 'Item check incomplete · Current room');
    assert.equal(await page.locator('#completion').textContent(), 'Cleared');
    await page.keyboard.press('=');
    const chosenView = await map.getAttribute('viewBox');
    const chosenHistory = await page.evaluate(() => structuredClone(viewHistory));

    state = structuredClone(fixture.collected);
    await page.waitForFunction(source => lastState.rooms.find(visit => visit.room === source).items[0].state === 'taken', first.room);
    await checkDescription(first, 'Cleared');
    assert(await room(second).evaluate(node => node === document.activeElement), 'collection updates must retain focused room');
    state = structuredClone(fixture.initial);
    await page.waitForFunction(source => lastState.rooms.find(visit => visit.room === source).items[0].state === 'available', first.room);
    await checkDescription(first, 'Items remain');

    state = structuredClone(fixture.moved);
    await page.waitForFunction(source => lastState.current === source, first.room);
    await checkDescription(first, 'Items remain · Current room');
    await checkDescription(second, 'Cleared · Selected room');
    await checkDescription(third, 'Item check incomplete');
    assert(await room(second).evaluate(node => node === document.activeElement), 'player movement must not replace the inspected room');
    assert.equal(await map.getAttribute('viewBox'), chosenView);
    assert.deepEqual(await page.evaluate(() => viewHistory), chosenHistory);

    // VISITED is a supported legacy publication, outside Tracker's current
    // completion enum. Exercise it explicitly without changing real defaults.
    for (const visit of [state.current_detail, ...state.rooms, ...Object.values(state.explored_areas).flat()]) {
      if (visit.room === third.room) visit.state = 'VISITED';
    }
    await page.waitForFunction(source => lastState.rooms.find(visit => visit.room === source).state === 'VISITED', third.room);
    await checkDescription(third, 'Visited');
    state = { status: 'waiting', error: 'Tracking interrupted.' };
    await page.waitForFunction(() => lastState.status === 'waiting');
    for (const entry of fixture.rooms) await checkDescription(entry, 'Tracking interrupted');
    const details = page.locator('#room-name');
    assert(await details.evaluate(node => node === document.activeElement));
    assert.equal(await map.getAttribute('viewBox'), chosenView);
    assert.deepEqual(await page.evaluate(() => viewHistory), chosenHistory);

    state = structuredClone(fixture.collected);
    await page.waitForFunction(() => lastState.status === 'display');
    await checkDescription(first, 'Cleared');
    await checkDescription(second, 'Cleared · Selected room');
    await checkDescription(third, 'Item check incomplete · Current room');
    assert(await details.evaluate(node => node === document.activeElement), 'fresh descriptions must not steal recovery focus');
    assert.equal(await map.getAttribute('viewBox'), chosenView);
    assert.deepEqual(await page.evaluate(() => viewHistory), chosenHistory);

    await page.getByLabel('Floor', { exact: true }).selectOption(fixture.otherArea);
    assert.equal(await page.locator('#map .room').count(), 1);
    await checkDescription(fixture.otherRoom, 'Cleared · Selected room');
    assert.equal(await page.locator('#completion').textContent(), 'Cleared');
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log('RE1 and RE2 room accessibility checks passed: native AX descriptions, keyboard inspection, fresh/reversed status, independent current room, interruption and browsed floors.');
} finally {
  await browser.close();
}
