import React, { useState, useEffect, useMemo } from "react";
import ReactECharts from "echarts-for-react";
import "../../styles/Chart.css";

export default function RealTimeCandleChart({ bot, data }) {
  const [isPercent, setIsPercent] = useState(false);

  // ① 기본 날짜 생성
  const days = useMemo(() => {
    const arr = [];
    const start = new Date(2025, 10, 1).getTime();
    const end = new Date(2025, 11, 31).getTime();
    const DAY = 1000 * 60 * 60 * 24;

    for (let t = start; t <= end; t += DAY) arr.push(t);

    if (!data.length) return arr;

    // 데이터에서 가장 큰 시간
    const maxTime = Math.max(
      ...data.flatMap((item) => item.time.map((t) => new Date(t).getTime()))
    );
    for (let t = end + DAY; t <= maxTime + DAY; t += DAY) arr.push(t);

    return arr;
  }, [data]);

  // ② 퍼센트 변화 계산
  const getPercentChanges = (arr) => {
    const validArr = arr.filter((v) => v != null);
    const startValue = validArr[0] ?? 1000;
    return arr.map((v) => (v == null ? null : ((v - startValue) / startValue) * 100));
  };

  // ③ 데이터 필터링 및 매핑
  const series = useMemo(() => {
    return data
      .filter((u) => bot === "all" || u.userId === bot)
      .map((user) => {
        const yValues = isPercent ? getPercentChanges(user.total) : user.total;
        const dataWithNulls = days.map((day) => {
          const index = user.time.findIndex((t) => new Date(t).getTime() === day);
          return index >= 0 ? [day, yValues[index]] : [day, null];
        });
        return {
          name: user.username,
          type: "line",
          data: dataWithNulls,
          showSymbol: false,
          smooth: false,
          lineStyle: { color: user.colors }
        };
      });
  }, [data, bot, days, isPercent]);

  // ④ Y축 계산
  const yValuesAll = series.flatMap((s) => s.data.map((d) => d[1]).filter((v) => v != null));
  const yMin = Math.min(...yValuesAll, isPercent ? -50 : 8_000_000) * 0.9;
  const yMax = Math.max(...yValuesAll, isPercent ? 50 : 12_000_000) * 1.1;

  // ⑤ ECharts 옵션
  const options = {
    tooltip: { trigger: "axis" },
    legend: { top: 0 },
    grid: { left: 50, right: 20, top: 50, bottom: 50 },
    xAxis: {
      type: "time",
      axisLabel: {
        formatter: (value) => {
          const d = new Date(value);
          return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, "0")}/${String(
            d.getDate()
          ).padStart(2, "0")}`;
        },
        rotate: -45
      }
    },
    yAxis: {
      min: yMin,
      max: yMax,
      axisLabel: {
        formatter: (val) => (isPercent ? `${val.toFixed(1)}%` : `${Math.round(val).toLocaleString()} ₩`)
      }
    },
    series
  };

  return (
    <div className="chart-container">
      <div className="chart-title">
        <button onClick={() => setIsPercent((prev) => !prev)}>
          {isPercent ? "₩ View" : "% View"}
        </button>
        <p>Real-Time Bot Account Asset</p>
      </div>
      <ReactECharts option={options} style={{ height: "90%", width: "100%" }} notMerge={true} lazyUpdate={true} />
    </div>
  );
}
