import type { PingDetail } from '../types';

export function calculatePingMetrics(details: PingDetail[]) {
  const responseTimes = details.filter((item) => item.status === 'online' && item.response_time !== null).map((item) => item.response_time as number);
  const successCount = responseTimes.length;
  const failureCount = details.length - successCount;
  const jitterValues = responseTimes.slice(1).map((value, index) => Math.abs(value - responseTimes[index]));

  return {
    success_count: successCount,
    failure_count: failureCount,
    loss_rate: details.length ? Math.round((failureCount / details.length) * 100) : 0,
    average_response_time: responseTimes.length ? Math.round(responseTimes.reduce((sum, value) => sum + value, 0) / responseTimes.length) : null,
    min_response_time: responseTimes.length ? Math.min(...responseTimes) : null,
    max_response_time: responseTimes.length ? Math.max(...responseTimes) : null,
    jitter: jitterValues.length ? Math.round(jitterValues.reduce((sum, value) => sum + value, 0) / jitterValues.length) : null,
    total_count: details.length,
  };
}

export function buildPingChart(details: PingDetail[], averageResponseTime: number | null) {
  const width = 860;
  const height = 190;
  const padding = { top: 18, right: 12, bottom: 32, left: 46 };
  const visible = details.slice(-60);
  const responseValues = visible.map((item) => item.response_time).filter((value): value is number => value !== null);
  const maxResponse = Math.max(10, ...responseValues, averageResponseTime ?? 0);
  const maxValue = Math.max(80, Math.ceil(maxResponse / 20) * 20);
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const yTicks = Array.from({ length: 5 }, (_, index) => {
    const value = Math.round((maxValue / 4) * (4 - index));
    const y = padding.top + index * (plotHeight / 4);
    return { value, y };
  });
  const points = visible.map((item, index) => {
    const x = visible.length <= 1 ? padding.left : padding.left + (index / (visible.length - 1)) * plotWidth;
    const value = item.response_time ?? maxValue;
    const y = padding.top + plotHeight - (Math.min(value, maxValue) / maxValue) * plotHeight;
    return { x, y, item };
  });
  const latencyPath = points.map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(1)} ${point.y.toFixed(1)}`).join(' ');
  const averageY = averageResponseTime === null ? null : padding.top + plotHeight - (averageResponseTime / maxValue) * plotHeight;
  return { width, height, padding, plotWidth, plotHeight, points, latencyPath, averageY, yTicks };
}
