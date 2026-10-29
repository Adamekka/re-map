import assert from 'node:assert/strict';

export function mapHeaders(document) {
  const match = /<meta name="map-instance" content="([0-9a-f]{32})">/.exec(document);
  assert(match, 'Map fixture has no instance identity');
  return { 'X-Map-Instance': match[1] };
}
