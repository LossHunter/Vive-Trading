import React, { useState, useEffect, useMemo, useRef } from "react";
import { createChart } from "lightweight-charts";
import "../../styles/Chart.css";

export default function RealTimeCandleChart({ bot, data }) {
  const chartContainerRef = useRef();
  const chartRef = useRef();
  const seriesRefs = useRef([]);
  const [isPercent, setIsPercent] = useState(false);

  // 데이터 매핑
  const datamapping = useMemo(() => {
    return data.map(item => ({
      userId: item.userId,
      username: item.username,
      total_asset: item.total,
      colors: item.colors,
      logo: item.logo,
      time: item.time.map(t => new Date(t).getTime() / 1000),
    }));
  }, [data]);

  // 필터링된 series
  const filteredSeries = useMemo(() => {
    return datamapping
      .filter(user => bot === "all" || user.userId === bot)
      .map(user => {
        const yValues = isPercent
          ? (() => {
              const validArr = user.total_asset.filter(v => v != null);
              const startValue = validArr[0] ?? 1000;
              return user.total_asset.map(v =>
                v == null ? null : ((v - startValue) / startValue) * 100
              );
            })()
          : user.total_asset;

        const timeMap = new Map(user.time.map((t, i) => [t, yValues[i]]));
        const seriesData = Array.from(timeMap.entries()).map(([time, value]) => ({ time, value }));
        return { name: user.username, color: user.colors, data: seriesData };
      });
  }, [datamapping, bot, isPercent]);

  useEffect(() => {
    if (!chartContainerRef.current || filteredSeries.length === 0) return;

    const { clientWidth, clientHeight } = chartContainerRef.current;

    // 차트 생성
    if (!chartRef.current) {
      chartRef.current = createChart(chartContainerRef.current, {
        width: clientWidth,
        height: clientHeight,
        layout: { background: { color: 'transparent' }, textColor: "#000" },
        grid: { vertLines: { color: "#eee" }, horzLines: { color: "#eee" } },
        rightPriceScale: { visible: false },
        leftPriceScale: { visible: true, position: 'left', autoScale: false },
        timeScale: { borderVisible: false },
      });
    }

    // 기존 series 제거
    seriesRefs.current.forEach(s => chartRef.current?.removeSeries(s));
    seriesRefs.current = [];

    // 새 series 추가
    filteredSeries.forEach(user => {
      const lineSeries = chartRef.current.addLineSeries({ color: user.color, lineWidth: 2 });
      lineSeries.setData(user.data);
      seriesRefs.current.push(lineSeries);
    });

    // Y축: 최소 0, 최대 = 데이터 최대 +20%
    const allYValues = filteredSeries.flatMap(s => s.data.map(d => d.value));
    if (allYValues.length > 0) {
      const yMin = 0;
      const yMax = Math.max(...allYValues) * 1.2;

      chartRef.current.applyOptions({
        leftPriceScale: {
          position: 'left',
          autoScale: false,
          minValue: yMin,
          maxValue: yMax,
        }
      });
    }

    // X축: 왼쪽 고정, 오른쪽 최대 +20%
    const allTimes = filteredSeries.flatMap(s => s.data.map(d => d.time));
    if (allTimes.length > 0) {
      const minTime = Math.min(...allTimes);
      const maxTime = Math.max(...allTimes);
      const extra = (maxTime - minTime) * 0.2;

      chartRef.current.timeScale().setVisibleRange({ from: minTime, to: maxTime + extra });
      chartRef.current.timeScale().applyOptions({
        fixLeftEdge: true,
        fixRightEdge: false,
      });

      // 마우스 드래그로 X축 범위 벗어나지 않도록 제한
      chartRef.current.timeScale().subscribeVisibleTimeRangeChange((range) => {
        if (!range) return; // null 체크
        const { from, to } = range;
        if (from < minTime || to > maxTime + extra) {
          chartRef.current.timeScale().setVisibleRange({ from: minTime, to: maxTime + extra });
        }
      });
    }

    // Resize 처리
    const handleResize = () => {
      if (chartRef.current && chartContainerRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
          height: chartContainerRef.current.clientHeight,
        });
      }
    };
    window.addEventListener("resize", handleResize);
    handleResize();

    return () => window.removeEventListener("resize", handleResize);

  }, [filteredSeries]);

  return (
    <div className="chart-container" style={{ width: '100%', height: '100%' }}>
      <div className="chart-title">
        <button onClick={() => setIsPercent(prev => !prev)}>
          {isPercent ? "₩ View" : "% View"}
        </button>
        <p>Real-Time Bot Account Asset</p>
      </div>
      <div ref={chartContainerRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
}
