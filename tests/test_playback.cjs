const test = require('node:test');
const assert = require('node:assert/strict');
const {endTime, advance, truckState} = require('../src/dashboard/components/simulation_assets/playback.js');

const without = {berth: 2, pickup: 4.2327, arrival: 10.3327, delivery: 15.3327};
const fastest = {berth: 2, pickup: 4.2327, arrival: 10.3327, intake: 10.3327, delivery: 11.3327};
const cheapest = {...fastest, intake: 23, delivery: 24};

test('Fastest finishes before unmitigated delivery at the same playback rate', () => {
  const elapsed = fastest.delivery / .5;
  assert.equal(advance(0, elapsed, .5, fastest), endTime(fastest));
  assert.ok(advance(0, elapsed, .5, without) < endTime(without));
  assert.equal(truckState(fastest, advance(0, elapsed, .5, fastest)).stage, 'delivered');
  assert.equal(truckState(without, advance(0, elapsed, .5, without), {warehouseDelay:4}).stage, 'warehouse_wait');
  assert.ok(endTime(cheapest) > endTime(without));
});

test('each schedule clamps playback to its own delivery, not the slowest plan', () => {
  assert.equal(advance(0, 1000, .5, fastest), fastest.delivery);
  assert.equal(advance(0, 1000, .5, without), without.delivery);
  assert.equal(advance(0, 1000, .5, cheapest), cheapest.delivery);
});

test('warehouse disruption holds the truck rather than stretching final-mile travel', () => {
  assert.equal(truckState(without, 11, {warehouseDelay:4}).stage, 'warehouse_wait');
  assert.equal(truckState(fastest, 11).stage, 'final_mile');
  assert.equal(truckState(without, 14.5, {warehouseDelay:4}).stage, 'warehouse_handling');
  assert.equal(truckState(cheapest, 22).stage, 'warehouse_wait');
  assert.equal(truckState(cheapest, 23.5).stage, 'warehouse_handling');
  assert.equal(truckState(cheapest, 24).stage, 'delivered');
});

test('road incident stops existing truck, while replacement clears the interruption', () => {
  const delayed = {pickup:3, arrival:10.5, delivery:12.5};
  const replacement = {pickup:3, arrival:6.5, intake:6.5, delivery:7.5};
  const stopped1 = truckState(delayed, 5, {roadDelay:4});
  const stopped2 = truckState(delayed, 7, {roadDelay:4});
  assert.deepEqual(stopped1, {stage:'road_hold', progress:.45});
  assert.deepEqual(stopped2, stopped1);
  assert.equal(truckState(replacement, 7.5).stage, 'delivered');
});

test('port recovery departs before the unmitigated truck is released', () => {
  const delayed = {pickup:6, arrival:9.5, delivery:11.5};
  const expedited = {pickup:3, arrival:6.5, intake:6.5, delivery:7.5};
  assert.equal(truckState(delayed, 4).stage, 'port_wait');
  assert.equal(truckState(expedited, 4).stage, 'road_transit');
});
