import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
} from 'recharts';
import { SensorReading } from '../types';
import { USE_MOCK } from '../api';

interface SensorChartProps {
  title: string;
  dataKey: string;
  unit: string;
  upperLimit?: number;
  lowerLimit?: number;
  data: SensorReading[];
  strokeColor?: string;
  anomalyColor?: string;
}

const MAX_POINTS = 1500;

export const SensorChart: React.FC<SensorChartProps> = ({
  title,
  dataKey,
  unit,
  upperLimit,
  lowerLimit,
  data: allData,
  strokeColor = '#f59e0b',
  anomalyColor = '#ef4444',
}) => {
  // Large uploads: draw every n-th point, but always keep readings inside unusual periods
  const step = Math.ceil(allData.length / MAX_POINTS);
  const data =
    step <= 1 ? allData : allData.filter((d, i) => i % step === 0 || d.is_anomaly);

  // Find min and max for nice Y-axis domain
  const values = data
    .map((d) => d[dataKey])
    .filter((v) => v !== null && v !== undefined && v !== '')
    .map(Number)
    .filter(Number.isFinite);
  const minVal = values.length ? Math.min(...values) : 0;
  const maxVal = values.length ? Math.max(...values) : 1;
  const yMin = Math.floor(Math.min(minVal, lowerLimit ?? minVal) * 0.92);
  const yMax = Math.ceil(Math.max(maxVal, upperLimit ?? maxVal) * 1.08);

  // Custom Dot renderer that paints red dots on anomaly points
  const renderCustomDot = (props: any) => {
    const { cx, cy, payload } = props;
    if (!cx || !cy) return null;

    // Check if this reading has an anomaly on this sensor
    const isThisSensorAnomaly =
      payload.is_anomaly &&
      payload.anomaly_sensors &&
      payload.anomaly_sensors.includes(dataKey as string);

    // Also check direct value breach
    const isExceeded =
      (upperLimit !== undefined && payload[dataKey] > upperLimit) ||
      (lowerLimit !== undefined && payload[dataKey] < lowerLimit);

    if (isThisSensorAnomaly || isExceeded) {
      return (
        <g key={`dot-${payload.id}`}>
          <circle cx={cx} cy={cy} r={6} fill={anomalyColor} fillOpacity={0.4} />
          <circle cx={cx} cy={cy} r={3.5} fill={anomalyColor} stroke="#fff" strokeWidth={1.5} />
        </g>
      );
    }

    return null;
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex flex-col gap-2">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold text-zinc-100">{title}</span>
          <span className="text-xs font-mono text-zinc-400">({unit})</span>
          {USE_MOCK && (
            <span className="px-1.5 py-0.5 rounded bg-amber-500/15 border border-amber-500/40 text-amber-300 text-[10px] font-mono font-bold">
              SIMULATED - mock values, not dataset readings
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono">
          {upperLimit !== undefined && (
            <span className="text-red-400 flex items-center gap-1">
              <span className="w-2.5 h-0.5 bg-red-500 inline-block"></span>
              Upper Limit: {upperLimit} {unit}
            </span>
          )}
          {lowerLimit !== undefined && (
            <span className="text-red-400 flex items-center gap-1">
              <span className="w-2.5 h-0.5 bg-red-500 inline-block"></span>
              Lower Limit: {lowerLimit} {unit}
            </span>
          )}
          {upperLimit === undefined && lowerLimit === undefined && (
            <span className="text-zinc-400">No fixed limit - compared with this machine's normal pattern</span>
          )}
        </div>
      </div>

      <p className="sr-only">
        {title}: peak {Number.isFinite(maxVal) ? maxVal : '-'} {unit},{' '}
        {data.filter((d) => d.is_anomaly && d.anomaly_sensors?.includes(dataKey)).length} readings in unusual periods.
      </p>
      <div className="w-full h-56 pt-2">
        <ResponsiveContainer width="99.9%" height={210}>
          <LineChart data={data} margin={{ top: 8, right: 12, left: -10, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis
              dataKey="displayTime"
              stroke="#71717a"
              fontSize={10}
              tickLine={false}
              interval={Math.floor(data.length / 5)}
              fontFamily="monospace"
            />
            <YAxis
              domain={[yMin, yMax]}
              stroke="#71717a"
              fontSize={10}
              tickLine={false}
              fontFamily="monospace"
              width={40}
            />
            <Tooltip
              content={({ active, payload, label }) => {
                if (active && payload && payload.length) {
                  const item = payload[0].payload as SensorReading;
                  const val = item[dataKey];
                  const hasAnomaly =
                    (upperLimit !== undefined && (val as number) > upperLimit) ||
                    (lowerLimit !== undefined && (val as number) < lowerLimit) ||
                    (item.is_anomaly && item.anomaly_sensors?.includes(dataKey as string));

                  return (
                    <div className="bg-zinc-950 border border-zinc-700 p-2.5 rounded shadow-xl font-mono text-xs text-zinc-200">
                      <div className="text-zinc-400 font-semibold mb-1">
                        {label} · {item.id}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-amber-400">{title}:</span>
                        <span className="font-bold text-white">
                          {val == null || val === '' ? 'empty' : String(val)} {unit}
                        </span>
                      </div>
                      {hasAnomaly && (
                        <div className="mt-1.5 text-red-400 font-bold text-[11px] flex items-center gap-1">
                          ● {upperLimit !== undefined || lowerLimit !== undefined ? 'Outside limit' : 'Unusual reading'}
                        </div>
                      )}
                    </div>
                  );
                }
                return null;
              }}
            />
            {upperLimit !== undefined && (
              <ReferenceLine
                y={upperLimit}
                stroke="#ef4444"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{
                  value: `Max ${upperLimit}`,
                  fill: '#ef4444',
                  fontSize: 10,
                  position: 'insideTopRight',
                  fontFamily: 'monospace',
                }}
              />
            )}
            {lowerLimit !== undefined && (
              <ReferenceLine
                y={lowerLimit}
                stroke="#ef4444"
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{
                  value: `Min ${lowerLimit}`,
                  fill: '#ef4444',
                  fontSize: 10,
                  position: 'insideBottomRight',
                  fontFamily: 'monospace',
                }}
              />
            )}
            <Line
              type="monotone"
              dataKey={dataKey}
              stroke={strokeColor}
              strokeWidth={1.75}
              dot={renderCustomDot}
              activeDot={{ r: 5, fill: '#fff', stroke: strokeColor, strokeWidth: 2 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
