import React, { useState, useEffect } from "react";
import Chart from "react-apexcharts";
import "../styles/Chart.css";

export default function RealTimeCandleChart({ bot, data }) {
    const [isPercent, setIsPercent] = useState(false);
    const [days, setDays] = useState(() => {
        const arr = [];
        const start = new Date(2025, 10, 1);
        const end = new Date(2025, 11, 31);
        for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
            arr.push(new Date(d).getTime());
        }
        return arr;
    });

    useEffect(() => {
        if (!data.length) return;

        const allTimes = data.flatMap(item => item.time.map(t => new Date(t).getTime()));
        const maxTime = Math.max(...allTimes);

        const lastDay = days[days.length - 1];
        if (maxTime > lastDay) {
            const newDays = [...days];
            const endDate = new Date(lastDay);
            const newEnd = new Date(endDate.getFullYear(), endDate.getMonth() + 1, 31);

            for (let d = new Date(endDate); d <= newEnd; d.setDate(d.getDate() + 1)) {
                newDays.push(new Date(d).getTime());
            }

            setDays(newDays);
        }
    }, [data]);

    // 퍼센트 변화 계산 (null 안전 처리)
    const getPercentChanges = (arr) => {
        const validArr = arr.filter(v => v != null);
        const startValue = validArr[0] ?? 1000;
        return arr.map(v => (v == null ? null : ((v - startValue) / startValue) * 100));
    };

    const datamapping = data.map(item => ({
        userId: item.userId,
        username: item.username,
        total_asset: item.total,
        colors: item.colors,
        logo: item.logo,
        time: item.time.map(t => new Date(t).getTime())
    }));

    const filteredSeries = datamapping
        .filter(user => bot === "all" || user.userId === bot)
        .map(user => {
            const yValues = isPercent
                ? getPercentChanges(user.total_asset)
                : user.total_asset;

            const dataWithNulls = days.map(day => {
                const index = user.time.findIndex(t => t === day);
                return { x: day, y: index >= 0 ? yValues[index] : null };
            });

            return {
                name: user.username,
                color: user.colors,
                logo: user.logo,
                data: dataWithNulls
            };
        });

    const y_unit = 2_000_000;
    const initialMoneyMin = 8_000_000;
    const initialMoneyMax = 12_000_000;
    const initialPercentMin = -50;
    const initialPercentMax = 50;

    const yValuesAll = filteredSeries.flatMap(s =>
        s.data.map(d => d.y).filter(v => v != null)
    );

    const rawYMin = isPercent
        ? Math.min(...yValuesAll, initialPercentMin)
        : Math.min(...yValuesAll, initialMoneyMin);

    const rawYMax = isPercent
        ? Math.max(...yValuesAll, initialPercentMax)
        : Math.max(...yValuesAll, initialMoneyMax);

    const yMin = isPercent ? rawYMin * 0.9 : rawYMin * 0.9;
    const yMax = isPercent ? rawYMax * 1.1 : rawYMax * 1.1;

    const yMinTick = isPercent ? Math.floor(yMin / 10) * 10 : Math.floor(yMin / y_unit) * y_unit;
    const yMaxTick = isPercent ? Math.ceil(yMax / 10) * 10 : Math.ceil(yMax / y_unit) * y_unit;
    const yTickAmount = isPercent ? Math.ceil((yMaxTick - yMinTick) / 10) : Math.ceil((yMaxTick - yMinTick) / y_unit);

    const options = {
        chart: {
            type: "line",
            height: 350,
            animations: { enabled: true, easing: "linear", speed: 800 }
        },
        xaxis: {
            type: "datetime",
            labels: {
                formatter: (val) => {
                    const date = new Date(val);
                    return `${date.getMonth() + 1}/${String(date.getDate()).padStart(2, "0")}`;
                },
                rotate: -45,
                style: { fontSize: "12px" }
            }
        },
        yaxis: {
            min: yMinTick,
            max: yMaxTick,
            tickAmount: yTickAmount,
            forceNiceScale: true,
            labels: {
                formatter: (value) => {
                    if (value == null || isNaN(value)) return "";
                    return isPercent
                        ? `${value.toFixed(1)}%`
                        : `${Math.round(value).toLocaleString()} ₩`;
                }
            }
        },
        grid: {
            show: true,
            borderColor: "#90A4AE",
            strokeDashArray: 1,
            xaxis: { lines: { show: true } },
            yaxis: { lines: { show: true } }
        },
        legend: { position: "top" },
        stroke: { width: 3, curve: "straight" }
    };

    return (
        <div className="chart-container">
            <div className="chart-title">
                <button onClick={() => setIsPercent(prev => !prev)}>
                    {isPercent ? "₩ View" : "% View"}
                </button>
                <p>Real-Time Bot Account Asset</p>
            </div>

            <Chart options={options} series={filteredSeries} type="line" height="90%" />
        </div>
    );
}
