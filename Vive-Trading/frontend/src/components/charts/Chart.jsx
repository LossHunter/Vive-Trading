import React, { useState, useEffect, useMemo } from "react";
import Chart from "react-apexcharts";
import Loading from "../../components/common/Loading";

export default function RealTimeCandleChart({ bot, data }) {
    const [isPercent, setIsPercent] = useState(false);
    const [loading, setLoading] = useState(true);

    const getPercentChanges = (arr) => {
        return arr.map((v, idx) => {
            if (v == null) return null;
            if (v === 0) return 0;  // 0이면 0%
            const prev = idx === 0 ? v : arr[idx - 1];
            if (prev === 0) return 0; // 이전 값이 0이면 변화율 0%
            return ((v - prev) / prev) * 100; // 직전 값 대비 %
        });
    };

    const parseYYYYMMDDHHMM = (str) => {
        if (typeof str !== "string" || str.length !== 12) return null;

        const year = parseInt(str.slice(0, 4), 10);
        const month = parseInt(str.slice(4, 6), 10) - 1;
        const day = parseInt(str.slice(6, 8), 10);
        const hour = parseInt(str.slice(8, 10), 10);
        const min = parseInt(str.slice(10, 12), 10);

        return new Date(year, month, day, hour, min);
    };

    const datamapping = useMemo(() => data.map(item => ({
        userId: item.userId,
        username: item.username,
        total_asset: item.total ?? [],
        colors: item.colors ?? "#3b82f6",
        logo: item.logo ?? "",
        time: (item.time ?? []).map(t => {
            const parsed = parseYYYYMMDDHHMM(t);
            return parsed ? parsed.getTime() : null;
        }).filter(t => t !== null)
    })), [data]);

    const botStr = String(bot);

    const filteredSeries = useMemo(() => {
        return datamapping
            .filter(user => bot === "all" || user.userId === botStr)
            .map(user => {
                const yValuesRaw = isPercent
                    ? getPercentChanges(user.total_asset)
                    : user.total_asset;

                const dataPoints = user.time
                    .map((t, idx) => {
                        const yVal = yValuesRaw[idx];
                        return (yVal == null || isNaN(yVal)) ? null : { x: t, y: yVal };
                    })
                    .filter(d => d !== null);

                return {
                    name: user.username,
                    color: user.colors,
                    logo: user.logo,
                    data: dataPoints
                };
            })
            .filter(s => s.data.length > 0);
    }, [datamapping, botStr, isPercent]);

    useEffect(() => {
        if (filteredSeries.length > 0) setLoading(false);
    }, [filteredSeries]);

    const yValuesAll = filteredSeries.flatMap(s => s.data.map(d => d.y));
    const yMinTick = isPercent
        ? (filteredSeries[0]?.data[0]?.y ?? 0) - 30
        : Math.floor(Math.min(...yValuesAll, 10_000_000) * 0.7 / 1_000_000) * 1_000_000;
    const yMaxTick = isPercent
        ? (filteredSeries[0]?.data[0]?.y ?? 0) + 30
        : Math.ceil(Math.max(...yValuesAll, 10_000_000) * 1.3 / 1_000_000) * 1_000_000;

    const allTimes = filteredSeries.flatMap(s => s.data.map(d => d.x));
    const minTime = allTimes.length > 0 ? Math.min(...allTimes) : Date.now();
    const maxTime = allTimes.length > 0 ? Math.max(...allTimes) : Date.now();

    const options = {
        chart: { type: "line", height: 350, animations: { enabled: true, easing: "linear", speed: 800 } },
        stroke: { width: 3, curve: "straight" },
        markers: { size: 0, hover: { size: 5 } },
        xaxis: {
            type: "datetime",
            min: minTime,
            max: maxTime,
            labels: {
                rotate: -45,
                style: { fontSize: "12px", colors: "black" },
                formatter: val => {
                    const date = new Date(val);
                    return `${date.getMonth() + 1}/${date.getDate()}`;
                }
            }
        },
        yaxis: {
            min: yMinTick,
            max: yMaxTick,
            tickAmount: isPercent ? 6 : Math.floor((yMaxTick - yMinTick) / 1_000_000),
            forceNiceScale: false,
            labels: {
                style: { fontSize: "12px", colors: "black" },
                formatter: value => (value == null || isNaN(value) ? "" : isPercent ? `${value.toFixed(1)}%` : Math.round(value))
            }
        },
        grid: { show: true, borderColor: "#90A4AE", strokeDashArray: 1, xaxis: { lines: { show: true } }, yaxis: { lines: { show: true } } },
        legend: { position: "top", labels: { colors: "inherit", useSeriesColors: false } },
        tooltip: {
            enabled: true,
            x: {
                show: true,
                formatter: val => {
                    const date = new Date(val);
                    const month = date.getMonth() + 1;
                    const day = date.getDate();
                    const hour = String(date.getHours()).padStart(2, '0');
                    const min = String(date.getMinutes()).padStart(2, '0');
                    return `${month}/${day} ${hour}:${min}`;
                }
            },
            y: {
                formatter: val => val == null ? "-" : isPercent ? `${val.toFixed(1)}%` : val.toLocaleString()
            }
        },
        fill: { type: "solid" }
    };

    return (
        <>
            {(loading || filteredSeries.length === 0) ? (
                <Loading />
            ) : (
                <div className="chart-container">
                    <div className="chart-title">
                        <button onClick={() => setIsPercent(prev => !prev)}>
                            {isPercent ? "₩ View" : "% View"}
                        </button>
                        <p>Real-Time Bot Account Asset</p>
                    </div>
                    <Chart options={options} series={filteredSeries} type="line" height="90%" />
                </div>
            )}
        </>
    );
}
