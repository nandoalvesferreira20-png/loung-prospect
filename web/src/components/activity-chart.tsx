"use client";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
export function ActivityChart({
  data,
}: {
  data: { stage: string; count: number }[];
}) {
  return (
    <>
      <div
        className="min-w-0"
        style={{ height: Math.max(240, data.length * 40) }}
        aria-hidden="true"
      >
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 0, right: 20, top: 10, bottom: 0 }}
          >
            <CartesianGrid horizontal={false} stroke="#e8edf5" />
            <XAxis
              type="number"
              allowDecimals={false}
              tick={{ fontSize: 11 }}
            />
            <YAxis
              type="category"
              dataKey="stage"
              width={125}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip />
            <Bar
              dataKey="count"
              name="Leads"
              fill="#2563eb"
              radius={[0, 4, 4, 0]}
              maxBarSize={20}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="sr-only" aria-label="Leads por etapa">
        {data.map((row) => (
          <li key={row.stage}>
            {row.stage}: {row.count}
          </li>
        ))}
      </ul>
    </>
  );
}
