// Run with Bun and Playwright: bun tests/check_map_touch_browser.mjs <python>
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
    other=next(plan for plan in catalog['areas'] if plan['id']!=area['id'] and plan['rooms'])
    region=other['rooms'][0]
    source=region['room_ids'][0]
    tracker.mark_current(RoomId(*[int(part,16) for part in source.split('-')]))
    tracker.region_visits[other['id']+':'+region['id']]=source
    source=area['rooms'][1]['room_ids'][0]
    tracker.mark_current(RoomId(*[int(part,16) for part in source.split('-')]))
    tracker.current_region=area['id']+':'+area['rooms'][1]['id']
    cases.append({'document':map_page(catalog,uuid4()).decode(),'state':map_state(tracker)})
print(json.dumps(cases))
`], { encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const browser = await chromium.launch();
try {
  for (const fixture of JSON.parse(setup.stdout)) {
    let state = structuredClone(fixture.state);
    const page = await browser.newPage({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('http://touch-map.test/**', route => {
      const path = new URL(route.request().url()).pathname;
      if (path === '/client-error') {
        errors.push(route.request().postDataJSON());
        return route.fulfill({ status: 204 });
      }
      assert(['/', '/state'].includes(path), 'Unexpected request: ' + path);
      return route.fulfill({ headers: mapHeaders(fixture.document), contentType: path === '/' ? 'text/html' : 'application/json', body: path === '/' ? fixture.document : JSON.stringify(state) });
    });
    await page.goto('http://touch-map.test/');
    await page.waitForFunction(() => document.getElementById('map').getAttribute('tabindex') === '0');
    const map = page.locator('#map');
    await map.evaluate(node => {
      window.mapTouchIds = [];
      node.addEventListener('pointerdown', event => {
        if (event.pointerType === 'touch') window.mapTouchIds.push(event.pointerId);
      });
    });
    const client = await page.context().newCDPSession(page);
    const touch = (type, touchPoints) => client.send('Input.dispatchTouchEvent', { type, touchPoints });
    const frame = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
    const view = () => map.getAttribute('viewBox').then(value => value.split(' ').map(Number));
    const world = (x, y) => map.evaluate((node, point) => {
      const value = new DOMPoint(...point).matrixTransform(node.getScreenCTM().inverse());
      return [value.x, value.y];
    }, [x, y]);
    const center = async () => {
      const box = await map.boundingBox();
      return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
    };
    const roomPoint = room => room.evaluate(node => {
      // A concave room's bounding-box center can lie outside its floor plan.
      const box = node.getBoundingClientRect();
      for (let y = box.top + 1; y < box.bottom; y += 2) for (let x = box.left + 1; x < box.right; x += 2) {
        if (document.elementFromPoint(x, y)?.closest('.room') === node) return { x, y };
      }
      throw new Error('The explored room has no visible touch surface');
    });
    const { x: cx, y: cy } = await center();
    const original = await view(), selected = await page.locator('.room.selected').getAttribute('data-region');
    const anchor = await world(cx, cy), scene = await page.locator('#map .room').count();
    await touch('touchStart', [{ id: 1, x: cx - 40, y: cy }, { id: 2, x: cx + 40, y: cy }]);
    await touch('touchMove', [{ id: 1, x: cx - 80, y: cy }, { id: 2, x: cx + 80, y: cy }]);
    await frame();
    assert.equal(await page.locator('#zoom-level').textContent(), '200%', 'spreading two fingers must zoom the map');
    const zoomed = await view();
    assert(Math.abs(zoomed[2] * 2 - original[2]) < 1e-8);
    // Chromium rounds touch coordinates with fractional CSS pixels.
    for (const [index, value] of (await world(cx, cy)).entries()) assert(Math.abs(value - anchor[index]) < 1e-4, 'pinching must retain the world point beneath the midpoint');
    await touch('touchMove', [{ id: 1, x: cx - 65, y: cy + 15 }, { id: 2, x: cx + 95, y: cy + 15 }]);
    await frame();
    for (const [index, value] of (await world(cx + 15, cy + 15)).entries()) assert(Math.abs(value - anchor[index]) < 1e-4, 'the anchor must follow a moving pinch midpoint');
    const chosen = await view();
    state.player_heading = 180;
    await page.waitForFunction(() => document.querySelector('.player path')?.getAttribute('transform').includes('rotate(180)'));
    assert.deepEqual(await view(), chosen, 'live updates must retain a pinch view');
    // Explicit ending contact IDs let the first finger remain on the screen.
    await touch('touchEnd', [{ id: 2, x: cx + 95, y: cy + 15 }]);
    await frame();
    assert.deepEqual(await view(), chosen, 'lifting one finger must not jump');
    const remainingAnchor = await world(cx - 65, cy + 15);
    await touch('touchMove', [{ id: 1, x: cx - 45, y: cy + 25 }]);
    await frame();
    for (const [index, value] of (await world(cx - 45, cy + 25)).entries()) assert(Math.abs(value - remainingAnchor[index]) < 1e-4, 'the remaining finger must continue panning');
    assert.equal(await page.locator('#zoom-level').textContent(), '200%');
    await touch('touchEnd', []);
    await frame();
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), selected, 'pinching must not inspect a room');
    const releasedRoom = page.locator('.room:not(.selected)').first();
    for (let click = 0; click < 2; click++) await releasedRoom.dispatchEvent('click', { bubbles: true, cancelable: true, detail: 1 });
    assert.equal(await page.locator('.room.selected').getAttribute('data-region'), selected, 'released contacts must remain suppressed until a new pointerdown');
    assert.equal(await page.locator('#map .room').count(), scene, 'touch navigation must not reveal rooms');
    assert.deepEqual(await page.evaluate(() => lastState), state);
    await page.getByRole('button', { name: 'Fit explored rooms', exact: true }).click();
    const start = { id: 1, x: cx - 60, y: cy };
    await touch('touchStart', [start]);
    await touch('touchMove', [{ ...start, x: cx - 40 }]);
    await frame();
    const panned = await view();
    await touch('touchStart', [{ ...start, x: cx - 40 }, { id: 2, x: cx + 40, y: cy }]);
    await frame();
    assert.deepEqual(await view(), panned, 'adding a finger during a pan must not jump');
    await touch('touchMove', [{ ...start, x: cx - 80 }, { id: 2, x: cx + 80, y: cy }]);
    await frame();
    assert.equal(await page.locator('#zoom-level').textContent(), '200%');
    await touch('touchEnd', []);
    for (const cause of ['cancel', 'capture', 'blur', 'resize', 'interruption', 'empty', 'floor', 'zoom']) {
      await page.getByRole('button', { name: 'Follow player', exact: true }).click();
      const { x, y } = await center();
      await page.evaluate(() => { window.mapTouchIds = []; });
      await touch('touchStart', [{ id: 1, x: x - 40, y }, { id: 2, x: x + 40, y }]);
      await touch('touchMove', [{ id: 1, x: x - 70, y }, { id: 2, x: x + 70, y }]);
      await frame();
      if (cause === 'cancel') await touch('touchCancel', []);
      else if (cause === 'capture') {
        await map.evaluate(node => node.releasePointerCapture(window.mapTouchIds[0]));
        await touch('touchMove', [{ id: 1, x: x - 75, y }, { id: 2, x: x + 75, y }]);
      } else if (cause === 'blur') await page.evaluate(() => window.dispatchEvent(new Event('blur')));
      else if (cause === 'resize') await page.setViewportSize({ width: 400, height: 844 });
      else if (cause === 'interruption') {
        state = { status: 'waiting', error: 'Interrupted during pinch' };
        await page.waitForFunction(() => document.getElementById('floor').disabled);
      } else if (cause === 'empty') {
        state = structuredClone(fixture.state);
        state.map_region = 'unoutlined';
        state.explored_areas = { [state.area]: [] };
        await page.waitForFunction(() => document.getElementById('map').getAttribute('tabindex') === '-1');
      } else if (cause === 'floor') {
        const otherArea = Object.keys(state.explored_areas).find(area => area !== state.area);
        await page.getByLabel('Floor', { exact: true }).selectOption(otherArea);
      } else await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
      await frame();
      assert(await map.evaluate(node => window.mapTouchIds.every(id => !node.hasPointerCapture(id))), cause + ' must release every captured finger');
      assert(!await map.evaluate(node => node.classList.contains('panning')), cause + ' must clear the gesture cursor');
      if (cause !== 'cancel') await touch('touchEnd', []);
      if (cause === 'resize') await page.setViewportSize({ width: 390, height: 844 });
      if (cause === 'interruption' || cause === 'empty') {
        state = structuredClone(fixture.state);
        await page.waitForFunction(() => document.getElementById('map').getAttribute('tabindex') === '0');
      }
      if (cause === 'floor') await page.getByRole('button', { name: 'Follow player', exact: true }).click();
      await page.getByRole('button', { name: 'Fit explored rooms', exact: true }).click();
      const other = page.locator('.room:not(.selected)').first();
      const id = await other.getAttribute('data-region');
      const point = await roomPoint(other);
      await page.touchscreen.tap(point.x, point.y);
      assert.equal(await page.locator('.room.selected').getAttribute('data-region'), id, cause + ' must allow the next normal room tap');
    }
    for (const limit of ['minimum', 'maximum']) {
      await page.getByRole('button', { name: 'Follow player', exact: true }).click();
      const { x, y } = await center();
      const start = limit === 'minimum' ? 100 : 2, end = limit === 'minimum' ? 1 : 120;
      await touch('touchStart', [{ id: 1, x: x - start, y }, { id: 2, x: x + start, y }]);
      await touch('touchMove', [{ id: 1, x: x - end, y }, { id: 2, x: x + end, y }]);
      await frame();
      const label = limit === 'minimum' ? '100%' : '800%';
      assert.equal(await page.locator('#zoom-level').textContent(), label, 'pinching must respect the ' + limit + ' zoom');
      const anchor = await world(x, y);
      for (const shift of [-10, 10]) {
        await touch('touchMove', [{ id: 1, x: x - end + shift, y: y + shift }, { id: 2, x: x + end + shift, y: y + shift }]);
        await frame();
        assert.equal(await page.locator('#zoom-level').textContent(), label, 'parallel movement at a bound must retain scale');
        for (const [index, value] of (await world(x + shift, y + shift)).entries()) assert(Math.abs(value - anchor[index]) < 1e-4, 'the midpoint must still move the map at a zoom bound');
      }
      await touch('touchEnd', []);
    }
    for (const separation of ['one contact', 'both contacts']) {
      await page.getByRole('button', { name: 'Follow player', exact: true }).click();
      const { x, y } = await center(), before = await view();
      await touch('touchStart', [{ id: 1, x, y }, { id: 2, x, y }]);
      await touch('touchMove', separation === 'one contact' ? [{ id: 2, x: x + 40, y }] : [{ id: 1, x: x - 40, y }, { id: 2, x: x + 40, y }]);
      await frame();
      assert.deepEqual(await view(), before, 'coincident contacts must wait for a real scale baseline');
      await touch('touchMove', separation === 'one contact' ? [{ id: 2, x: x + 80, y }] : [{ id: 1, x: x - 80, y }, { id: 2, x: x + 80, y }]);
      await frame();
      assert.equal(await page.locator('#zoom-level').textContent(), '200%');
      assert((await view()).every(Number.isFinite));
      await touch('touchEnd', []);
    }
    for (const ending of ['release without move', 'release', 'cancel']) {
      await page.getByRole('button', { name: 'Follow player', exact: true }).click();
      const { x, y } = await center(), before = await view();
      const anchor = await world(x, y);
      await page.evaluate(() => {
        // Hold browser frames to exercise a release/cancel before painting.
        window.touchFrameControl = { next: 1, callbacks: new Map(), request: requestAnimationFrame, cancel: cancelAnimationFrame };
        window.requestAnimationFrame = callback => {
          const id = window.touchFrameControl.next++;
          window.touchFrameControl.callbacks.set(id, callback);
          return id;
        };
        window.cancelAnimationFrame = id => window.touchFrameControl.callbacks.delete(id);
      });
      await touch('touchStart', [{ id: 1, x: x - 40, y }, { id: 2, x: x + 40, y }]);
      if (ending !== 'release without move') await touch('touchMove', [{ id: 1, x: x - 80, y }, { id: 2, x: x + 80, y }]);
      assert.equal(await page.locator('#zoom-level').textContent(), '100%', 'held frames must defer pinch rendering');
      if (ending !== 'cancel') {
        await touch('touchEnd', [{ id: 2, x: x + (ending === 'release' ? 120 : 80), y }]);
        assert.equal(await page.locator('#zoom-level').textContent(), ending === 'release' ? '250%' : '150%', 'a release must apply its final coordinates with or without a queued move');
        for (const [index, value] of (await world(x + 20, y)).entries()) assert(Math.abs(value - anchor[index]) < 1e-4, 'the release midpoint must retain its world anchor');
        const remainingX = x - (ending === 'release' ? 80 : 40);
        const remainingAnchor = await world(remainingX, y);
        await touch('touchMove', [{ id: 1, x: remainingX + 10, y: y + 10 }]);
        // Let Chromium deliver coalesced input while our map frame stays held.
        await page.evaluate(() => new Promise(resolve => window.touchFrameControl.request.call(window, resolve)));
        for (const [index, value] of (await world(remainingX + 10, y + 10)).entries()) assert(Math.abs(value - remainingAnchor[index]) < 1e-4, 'the remaining pan must start from the final release view');
      } else {
        await page.evaluate(() => window.dispatchEvent(new Event('blur')));
        assert.deepEqual(await view(), before, 'cancellation must discard an unpainted movement');
      }
      assert.equal(await page.evaluate(() => window.touchFrameControl.callbacks.size), 0, 'ending a pinch must release the scheduled frame');
      await touch('touchEnd', []);
      await page.evaluate(() => {
        window.requestAnimationFrame = window.touchFrameControl.request;
        window.cancelAnimationFrame = window.touchFrameControl.cancel;
        delete window.touchFrameControl;
      });
    }
    await page.getByRole('button', { name: 'Follow player', exact: true }).click();
    {
      const { x, y } = await center();
      await touch('touchStart', [{ id: 1, x: x - 40, y }, { id: 2, x: x + 40, y }]);
      await touch('touchStart', [{ id: 3, x, y: y + 50 }]);
      await touch('touchMove', [{ id: 1, x: x - 80, y }, { id: 2, x: x + 80, y }]);
      await frame();
      assert.equal(await page.locator('#zoom-level').textContent(), '200%', 'an extra finger must not replace the owned pair');
      const before = await view();
      await touch('touchEnd', [{ id: 3, x, y: y + 50 }]);
      await frame();
      assert.deepEqual(await view(), before, 'lifting an ignored finger must not end the pinch');
      await touch('touchMove', [{ id: 1, x: x - 100, y }, { id: 2, x: x + 100, y }]);
      await frame();
      assert.equal(await page.locator('#zoom-level').textContent(), '250%');
      await touch('touchEnd', []);
    }
    for (const releaseOrder of ['during drag', 'touch first', 'mouse first']) {
      await page.getByRole('button', { name: 'Follow player', exact: true }).click();
      const selectedBefore = await page.locator('.room.selected').getAttribute('data-region');
      const { x, y } = await roomPoint(page.locator('.room.selected'));
      await page.mouse.move(x, y);
      await page.mouse.down();
      // Keep the mouse pending so its own release permits a normal click.
      // An ignored touch must remain ignored after that owner has ended.
      if (releaseOrder === 'during drag') await page.mouse.move(x + 20, y);
      const other = page.locator('.room:not(.selected)').first();
      const otherId = await other.getAttribute('data-region');
      const point = await roomPoint(other);
      await touch('touchStart', [{ id: 1, ...point }]);
      if (releaseOrder === 'mouse first') await page.mouse.up();
      await touch('touchEnd', []);
      assert.equal(await page.locator('.room.selected').getAttribute('data-region'), selectedBefore, 'an unowned touch must not inspect a room: ' + releaseOrder);
      if (releaseOrder !== 'mouse first') await page.mouse.up();
      await page.touchscreen.tap(point.x, point.y);
      assert.equal(await page.locator('.room.selected').getAttribute('data-region'), otherId, 'the next owned touch must inspect a room');
    }
    assert.equal(await page.locator('#map .room').count(), scene);
    assert.deepEqual(await page.evaluate(() => lastState), state);
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log('RE1 and RE2 touch map navigation passed');
} finally {
  await browser.close();
}
