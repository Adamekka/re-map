// A real loopback server restart must replace the page before using a new profile.
// Run with Bun and Playwright: bun tests/check_map_restart_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { chromium } from 'playwright';

assert(process.argv[2], 'Pass the Python executable used for tracker tests');
const child = spawn(process.argv[2], ['-u', '-c', `
import json,sys
from pathlib import Path
from threading import Thread
sys.path.insert(0,str(Path.cwd()/'src'))
from games.game_profile import RoomId
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import Tracker
from ui.map_view import MapServer,map_state
catalogs={name:Re2Profile.load(Path(path)).map_layout.document for name,path in (
    ('leon','profiles/re2_leon_a_slus00748.json'),('claire','profiles/re2_claire_b_slus00756.json'))}
catalogs['jill']=json.loads(Path('data/floor_plans_slus00551.json').read_text())
server=None
thread=None
port=0
snapshot=b''
def start(name,count):
    global server,thread,port,snapshot
    graph=catalogs[name]
    tracker=Tracker(player_heading=90)
    area=graph['areas'][0]
    for region in area['rooms'][:count]:
        room=RoomId(*[int(part,16) for part in region['room_ids'][0].split('-')])
        tracker.mark_current(room)
        tracker.current_region=area['id']+':'+region['id']
        tracker.region_visits[tracker.current_region]=str(room)
    server=MapServer(port,graph)
    port=server.server_port
    snapshot=json.dumps(map_state(tracker)).encode()
    server.snapshot=snapshot
    thread=Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True)
    thread.start()
    print(json.dumps({'port':port,'profile':graph['profile_id'],'current':str(tracker.current)}),flush=True)
def stop():
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)
try:
    start('leon',2)
    for line in sys.stdin:
        command=json.loads(line)
        if command['op']=='restart':
            stop()
            start(command['profile'],command['count'])
        elif command['op']=='waiting':
            server.snapshot=json.dumps({'status':'waiting','error':'Game connection interrupted.'}).encode()
            print('{}',flush=True)
        elif command['op']=='restore':
            server.snapshot=snapshot
            print('{}',flush=True)
        else:
            raise AssertionError(command)
finally:
    if server is not None:
        stop()
`], { stdio: ['pipe', 'pipe', 'pipe'] });
let stderr = '';
child.stderr.on('data', data => { stderr += data; });
const exited = new Promise(resolve => child.once('exit', resolve));
const lines = createInterface({ input: child.stdout })[Symbol.asyncIterator]();
async function next() {
  const result = await lines.next();
  assert(!result.done, stderr);
  return JSON.parse(result.value);
}
async function command(value) {
  child.stdin.write(JSON.stringify(value) + '\n');
  return next();
}
let browser;
try {
  const first = await next();
  browser = await chromium.launch();
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const url = 'http://127.0.0.1:' + first.port + '/';
  await page.goto(url);
  await page.waitForFunction(() => typeof lastState !== 'undefined' && lastState.status === 'display');
  assert.equal(await page.locator('#map .room').count(), 2);
  await page.getByLabel('Find item or room', { exact: true }).fill('no such result');
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  const second = await command({ op: 'restart', profile: 'jill', count: 1 });
  assert.equal(second.port, first.port);
  await page.waitForFunction(current => typeof lastState !== 'undefined' && lastState?.current === current, second.current);
  assert.equal(await page.evaluate(() => catalog.profile_id), second.profile, 'an old tab must load the new server\'s catalog');
  assert.equal(await page.title(), 'Resident Evil room map');
  assert.equal(await page.locator('#map .room').count(), 1);
  assert.equal(await page.getByLabel('Find item or room', { exact: true }).inputValue(), '');
  assert.equal(await page.locator('#zoom-level').textContent(), '100%');

  // Hold the replacement page to inspect what the old tab exposes during navigation.
  let rootHeld;
  const heldRoot = new Promise(resolve => { rootHeld = resolve; });
  await page.route(url, route => { rootHeld(route); });
  const transition = page.waitForEvent('console', {
    predicate: message => message.text().startsWith('Map transition: '), timeout: 5000,
  });
  await page.evaluate(() => {
    // Mutation observers run before navigation; animation-frame polling can pause during reload.
    new MutationObserver(() => {
      if (document.body.textContent.trim() !== 'Updating map...') return;
      console.log('Map transition: ' + JSON.stringify({
        oldContent: document.querySelectorAll('#map, #overview, aside, header, #map-controls').length,
        status: document.querySelector('[role="status"]').textContent,
      }));
    }).observe(document.body, { childList: true });
  });
  const third = await command({ op: 'restart', profile: 'claire', count: 2 });
  assert.deepEqual(JSON.parse((await transition).text().slice('Map transition: '.length)), { oldContent: 0, status: 'Updating map...' });
  const replacement = await heldRoot;
  await replacement.continue();
  await page.waitForFunction(profile => typeof catalog !== 'undefined' && catalog.profile_id === profile && lastState?.status === 'display', third.profile);
  await page.unroute(url);
  assert.equal(await page.title(), 'Resident Evil 2 room map');
  assert.equal(await page.locator('#map .room').count(), 2);
  const instance = await page.locator('meta[name="map-instance"]').getAttribute('content');

  // Same-profile restarts also reset page-local state for a potentially different playthrough.
  await page.getByLabel('Find item or room', { exact: true }).fill('no such result');
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  await command({ op: 'restart', profile: 'claire', count: 1 });
  await page.waitForFunction(previous => {
    const identity = document.querySelector('meta[name="map-instance"]');
    return identity !== null && identity.content !== previous && typeof lastState !== 'undefined' && lastState?.status === 'display';
  }, instance);
  assert.equal(await page.locator('#map .room').count(), 1);
  assert.equal(await page.getByLabel('Find item or room', { exact: true }).inputValue(), '');
  assert.equal(await page.locator('#zoom-level').textContent(), '100%');
  const currentInstance = await page.locator('meta[name="map-instance"]').getAttribute('content');
  await page.getByLabel('Find item or room', { exact: true }).fill('keep query');
  await page.getByRole('button', { name: 'Zoom in', exact: true }).click();
  const chosenView = await page.locator('#map').getAttribute('viewBox');

  await command({ op: 'waiting' });
  await page.waitForFunction(() => lastState?.status === 'waiting');
  assert.equal(await page.locator('#status').textContent(), 'Game connection interrupted.');
  assert.equal(await page.locator('meta[name="map-instance"]').getAttribute('content'), currentInstance);
  await command({ op: 'restore' });
  await page.waitForFunction(() => lastState?.status === 'display');
  assert.equal(await page.getByLabel('Find item or room', { exact: true }).inputValue(), 'keep query');
  assert.equal(await page.locator('#map').getAttribute('viewBox'), chosenView);

  let headerMode = 'missing';
  await page.route(url + 'state', async route => {
    const response = await route.fetch();
    const headers = { ...response.headers() };
    if (headerMode === 'missing') delete headers['x-map-instance'];
    else if (headerMode === 'invalid') headers['x-map-instance'] = 'wrong';
    return route.fulfill({ response, headers });
  });
  for (const mode of ['missing', 'invalid']) {
    headerMode = mode;
    await page.waitForFunction(() => document.getElementById('status').textContent === 'Reload the map to reconnect to the tracker.');
    assert.equal(await page.locator('#remaining-items .room-link, #doors button').count(), 0);
    assert.equal(await page.locator('meta[name="map-instance"]').getAttribute('content'), currentInstance);
    headerMode = 'valid';
    await page.waitForFunction(() => lastState?.status === 'display');
    assert.equal(await page.getByLabel('Find item or room', { exact: true }).inputValue(), 'keep query');
    assert.equal(await page.locator('#map').getAttribute('viewBox'), chosenView);
  }
  await page.unroute(url + 'state');
  assert.deepEqual(errors, []);
  await page.close();
  console.log('Map restart browser checks passed');
} finally {
  if (browser) await browser.close();
  if (child.exitCode === null) child.stdin.end();
  assert.equal(await exited, 0, stderr);
}
