import React, { useState, useEffect } from "react";
import Chart from "react-apexcharts";
import "../../styles/Chart.css";

export default function RealTimeCandleChart({ bot, data }) {
    const [isPercent, setIsPercent] = useState(false);

    // ① 기본 날짜 (2025년 11월 1일 ~ 12월 31일)
    const [days, setDays] = useState(() => {
        const arr = [];
        const start = new Date(2025, 10, 1).getTime(); // 11월
        const end = new Date(2025, 11, 31).getTime(); // 12월
        const DAY = 1000 * 60 * 60 * 24;
        for (let t = start; t <= end; t += DAY) arr.push(t);
        return arr;
    });

    // ② 데이터에서 가장 최신 시간 확인 후 days 확장
    useEffect(() => {
        if (!data.length) return;

        const allTimes = data.flatMap(item => item.time.map(t => new Date(t).getTime()));
        const maxTime = Math.max(...allTimes);
        const lastDay = days[days.length - 1];
        const DAY = 1000 * 60 * 60 * 24;

        if (maxTime > lastDay) {
            const newDays = [...days];
            for (let t = lastDay + DAY; t <= maxTime + DAY; t += DAY) newDays.push(t);
            setDays(newDays);
        }
    }, [data, days]);

    // ③ 퍼센트 변화 계산
    const getPercentChanges = (arr) => {
        const validArr = arr.filter(v => v != null);
        const startValue = validArr[0] ?? 1000;
        return arr.map(v => (v == null ? null : ((v - startValue) / startValue) * 100));
    };

    // ④ 데이터 매핑
    const datamapping = data.map(item => ({
        userId: item.userId,
        username: item.username,
        total_asset: item.total,
        colors: item.colors,
        logo: item.logo,
        time: item.time.map(t => new Date(t).getTime())
    }));

    // ⑤ 필터링된 시리즈 데이터
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

    // ⑥ Y축 계산
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

    const yMin = rawYMin * 0.9;
    const yMax = rawYMax * 1.1;

    const yMinTick = isPercent
        ? Math.floor(yMin / 10) * 10
        : Math.floor(yMin / y_unit) * y_unit;

    const yMaxTick = isPercent
        ? Math.ceil(yMax / 10) * 10
        : Math.ceil(yMax / y_unit) * y_unit;

    const yTickAmount = isPercent
        ? Math.ceil((yMaxTick - yMinTick) / 10)
        : Math.ceil((yMaxTick - yMinTick) / y_unit);

    // 1일 밀리초
    const DAY = 1000 * 60 * 60 * 24;

    // ⑦ 차트 옵션
    const options = {
        chart: {
            type: "line",
            height: 350,
            animations: { enabled: true, easing: "linear", speed: 800 }
        },
        xaxis: {
            type: "datetime",
            min: days[0], 
            max: days[days.length - 1] + DAY * 5, // 마지막 날짜 + 5일 여유
            tickAmount: 10,
            labels: {
                formatter: (val) => {
                    const date = new Date(val);
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, "0");
                    const day = String(date.getDate()).padStart(2, "0");
                    return `${year}/${month}/${day}`;
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
