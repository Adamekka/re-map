// NODE_PATH=<runtime node_modules> bun tests/check_map_label_index_browser.mjs <python>
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';
import { mapHeaders } from './map_browser_response.mjs';

assert(process.argv[2], 'Pass the Python executable used for tracker tests');
const setup = spawnSync(process.argv[2], ['-c', `
import json,sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path.cwd()/'src'))
from games.game_profile import RoomId
from tracker.exploration_state import Tracker
from ui.map_view import map_page,map_state
catalog={'profile_id':'re2_test_label_index','stage_modulus':256,'areas':[{
    'id':'test','name':'Test floor','unoutlined_rooms':[],'doors':[],'rooms':[
        {'id':'00','name':'Test room','room_ids':['00-00'],'label':[0,12],
         'rings':[[[-20,-20],[20,-20],[20,20],[-20,20]]],
         'detail_segments':[[[-12,-8],[8,-8]],[[-8,-12],[-8,8]],[[-4,-4],[8,8]],[[12,12],[12,12]]]},
        {'id':'01','name':'Empty room','room_ids':['00-01'],'label':[50,0],
         'rings':[[[30,-20],[70,-20],[70,20],[30,20]]],'detail_segments':[]},
    ]}]}
tracker=Tracker(player_heading=90)
for number in (0,1):
    tracker.mark_current(RoomId(0,number))
    tracker.current_region=f'test:{number:02X}'
    tracker.region_visits[tracker.current_region]=str(tracker.current)
print(json.dumps({'document':map_page(catalog,uuid4()).decode(),'state':map_state(tracker)}))
`], { cwd: fileURLToPath(new URL('..', import.meta.url)), encoding: 'utf8' });
assert.equal(setup.status, 0, setup.stderr);
const fixture = JSON.parse(setup.stdout);
let html = fixture.document;
function injectOnce(before, after) {
  assert.equal(html.split(before).length, 2, 'Production instrumentation boundary changed');
  html = html.replace(before, after);
}
// Capture actual local predicates without adding a production testing API.
injectOnce('      const points=room.rings.flat()', `      window.labelIndexCaptures.push({id,contains:interior,paths:[...group.querySelectorAll('.map-detail-core')]});
      const points=room.rings.flat()`);
// Invalid SVG attributes must reach the mandatory constructor on a cache miss.
injectOnce("      const outline=group.querySelector('path');", `      const outline=group.querySelector('path');
      for(const path of group.querySelectorAll('.map-detail-core')) {
        if(window.labelIndexMutation==='path') path.setAttribute('transform','translate(1 0)');
        if(window.labelIndexMutation==='path-data') path.setAttribute('d','M0,0L1,1');
      }
      if(window.labelIndexMutation==='group') group.setAttribute('transform','translate(1 0)');`);
// Manual draws isolate cache misses and oracle probes from live polling.
injectOnce('\nrefresh();\n', '\n// Polling disabled in this isolated fixture.\n');

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('http://label-index.test/**', route => {
    assert.equal(new URL(route.request().url()).pathname, '/', 'The isolated test must not poll');
    return route.fulfill({ headers: mapHeaders(html), contentType: 'text/html', body: html });
  });
  await page.goto('http://label-index.test/');
  const report = await page.evaluate(base => {
    const room = catalog.areas[0].rooms[0], segments = structuredClone(room.detail_segments);
    const currentVisit = base.rooms.find(visit => visit.id === '00');
    const rule = document.createElement('style');
    document.head.append(rule);
    window.labelIndexCaptures = [];
    window.labelIndexMutation = 'none';
    const nativeStroke = SVGGeometryElement.prototype.isPointInStroke;
    let nativeCalls = 0;
    SVGGeometryElement.prototype.isPointInStroke = function(point) {
      nativeCalls++;
      return nativeStroke.call(this, point);
    };
    const cases = [];
    try {
      // A fractional width exercises noninteger bucket edges and padding.
      for (const width of [1, .75]) {
        rule.textContent = '.room path.map-detail-core { stroke-width:' + width + 'px; }';
        const probes = [];
        for (let x = -48; x <= 48; x++) {
          for (let y = -48; y <= 48; y++) probes.push(new DOMPoint(x / 2, y / 2));
        }
        const half = width / 2, epsilon = 1e-6;
        // Probe both sides of cap and side boundaries; native SVG decides ties.
        for (const [a, b] of segments) {
          const length = Math.hypot(b[0] - a[0], b[1] - a[1]);
          const offsets = [-half - epsilon, -half, -half + epsilon, 0, half - epsilon, half, half + epsilon];
          if (length === 0) {
            for (const x of offsets) {
              for (const y of offsets) probes.push(new DOMPoint(a[0] + x, a[1] + y));
            }
          } else {
            const tx = (b[0] - a[0]) / length, ty = (b[1] - a[1]) / length;
            for (const along of [...offsets.slice(0, 3), length / 2, ...offsets.slice(4).map(offset => length + offset)]) {
              for (const across of offsets) probes.push(new DOMPoint(a[0] + along * tx - across * ty, a[1] + along * ty + across * tx));
            }
          }
        }
        for (const mode of ['plain', 'current', 'selected']) {
          selected = mode === 'selected' ? '00' : null;
          selectedArea = base.area;
          floorView = { mode: 'follow' };
          labelLayouts.clear();
          labelIndexCaptures.length = 0;
          const state = mode === 'current' ? { ...base, current: currentVisit.room, map_region: currentVisit.id, current_detail: currentVisit } : base;
          draw(state);
          const target = labelIndexCaptures.find(capture => capture.id === '00');
          const empty = labelIndexCaptures.find(capture => capture.id === '01');
          if (target.contains.length !== 1 || target.paths.length !== 1 || empty.contains.length !== 0 || empty.paths.length !== 0) throw new Error('Unexpected interior capture');
          if (getComputedStyle(target.paths[0]).strokeWidth !== width + 'px') throw new Error('Requested stroke width was not applied');
          const group = target.paths[0].parentElement;
          if (group.classList.contains('current') !== (mode === 'current') || group.classList.contains('selected') !== (mode !== 'plain')) throw new Error('Requested room style was not applied');
          nativeCalls = 0;
          let hits = 0;
          for (const point of probes) {
            const expected = nativeStroke.call(target.paths[0], point);
            if (target.contains[0](point) !== expected) throw new Error('Index differs from native SVG at ' + point.x + ',' + point.y);
            if (empty.contains.some(contains => contains(point))) throw new Error('Empty interior reported a hit');
            if (expected) hits++;
          }
          if (hits === 0 || hits === probes.length || nativeCalls === 0 || nativeCalls >= probes.length / 4) throw new Error('Spatial rejection did not avoid most native queries');
          cases.push({ mode, width, probes: probes.length, hits, nativeCalls });
        }
      }
    } finally {
      SVGGeometryElement.prototype.isPointInStroke = nativeStroke;
    }
    const failures = [];
    for (const [name, prepare, expected] of [
      ['zero width', () => { rule.textContent = '.room path.map-detail-core { stroke-width:0px; }'; }, 'stroke width'],
      ['nonpixel width', () => { rule.textContent = '.room path.map-detail-core { stroke-width:10%; }'; }, 'stroke width'],
      ['round caps', () => { rule.textContent = '.room path.map-detail-core { stroke-linecap:round; }'; }, 'square caps'],
      ['vector effect', () => { rule.textContent = '.room path.map-detail-core { vector-effect:non-scaling-stroke; }'; }, 'square caps'],
      ['CSS path transform', () => { rule.textContent = '.room path.map-detail-core { transform:translateX(1px); }'; }, 'square caps'],
      ['CSS group transform', () => { rule.textContent = '.room { transform:translateX(1px); }'; }, 'square caps'],
      ['SVG path transform', () => { labelIndexMutation = 'path'; }, 'square caps'],
      ['SVG group transform', () => { labelIndexMutation = 'group'; }, 'square caps'],
      ['changed path data', () => { labelIndexMutation = 'path-data'; }, 'emitted independent segments'],
      ['NaN coordinate', () => { room.detail_segments[0][0][0] = NaN; }, 'precision bound'],
      ['infinite coordinate', () => { room.detail_segments[0][0][0] = Infinity; }, 'precision bound'],
      ['huge coordinate', () => { room.detail_segments[0][0][0] = 1e9; }, 'precision bound'],
    ]) {
      rule.textContent = '';
      labelIndexMutation = 'none';
      room.detail_segments = structuredClone(segments);
      prepare();
      labelLayouts.clear();
      let message = '';
      try { draw(base); } catch (error) { message = error.message; }
      if (!message.includes(expected)) throw new Error(name + ' did not reject its invalid invariant: ' + message);
      failures.push(name);
    }
    return { cases, failures };
  }, fixture.state);
  assert.equal(report.cases.length, 6);
  assert.equal(report.failures.length, 12);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify(report));
  await page.close();
} finally {
  await browser.close();
}
