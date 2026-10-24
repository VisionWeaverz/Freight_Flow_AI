/* Pure schedule-to-animation rules. Shared by the browser and Node regression tests. */
(function (root) {
  'use strict';
  const clamp = value => Math.max(0, Math.min(1, value));
  function endTime(schedule) {
    return Math.max(0, schedule.delivery);
  }
  function advance(time, elapsedSeconds, hoursPerSecond, schedule) {
    return Math.min(endTime(schedule), time + Math.max(0, elapsedSeconds) * hoursPerSecond);
  }
  function truckState(schedule, time, {roadDelay = 0, warehouseDelay = 0} = {}) {
    if (time < schedule.pickup) return {stage: 'port_wait', progress: 0};
    if (time >= schedule.delivery) return {stage: 'delivered', progress: 1};
    if (time < schedule.arrival) {
      const drive = schedule.arrival - schedule.pickup - roadDelay;
      const elapsed = time - schedule.pickup;
      const stopAt = Math.max(0, drive) * 0.45;
      if (roadDelay > 0 && elapsed >= stopAt && elapsed < stopAt + roadDelay) {
        return {stage: 'road_hold', progress: 0.45};
      }
      const movingTime = elapsed < stopAt ? elapsed : elapsed - roadDelay;
      return {stage: 'road_transit', progress: drive > 0 ? clamp(movingTime / drive) : 1};
    }
    const intake = Math.max(schedule.arrival, schedule.intake ?? schedule.arrival + warehouseDelay);
    if (time < intake) return {stage: 'warehouse_wait', progress: 0};
    // Delay is spent waiting/handling at the dock, not moving slowly toward the
    // nearby customer. Only the final 0.35 simulated hours are final-mile travel.
    const finalMile = Math.min(0.35, Math.max(0, schedule.delivery - intake));
    const departure = schedule.delivery - finalMile;
    if (time < departure) return {stage: 'warehouse_handling', progress: 0};
    return {stage: 'final_mile', progress: finalMile > 0 ? clamp((time - departure) / finalMile) : 1};
  }
  const api = {endTime, advance, truckState};
  root.ReplayMath = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(globalThis);
