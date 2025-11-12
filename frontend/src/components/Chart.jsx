import React, { useState, useEffect } from "react";
import Chart from "react-apexcharts";
import "../styles/Chart.css";

export default function RealTimeCandleChart({ bot, data }) {
    const [isPercent, setIsPercent] = useState(false);
    const [days, setDays] = useState(() => {
        // 초기: 11월~12월
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

    // 퍼센트 변화 계산 함수
    const getPercentChanges = (arr) => {
        const startValue = arr.find(v => v !== null) ?? 1000;
        return arr.map(v => (v === null ? null : ((v - startValue) / startValue) * 100));
    };

    // 데이터 매핑
    const datamapping = data.map(item => ({
        userId: item.userId,
        username: item.username,
        total_asset: item.total,
        colors: item.colors,
        logo: item.logo,
        time: item.time.map(t => new Date(t).getTime())
    }));

    // 필터링 + X축 고정 처리
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

    // 초기 Y축 범위
    const initialMoneyMin = 5000;
    const initialMoneyMax = 15000;
    const initialPercentMin = -50;
    const initialPercentMax = 50;

    // 실제 데이터 범위 계산
    const yValuesAll = filteredSeries.flatMap(s => s.data.map(d => d.y).filter(v => v !== null));
    const yMin = Math.min(...yValuesAll, isPercent ? initialPercentMin : initialMoneyMin);
    const yMax = Math.max(...yValuesAll, isPercent ? initialPercentMax : initialMoneyMax);

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
            min: yMin,
            max: yMax,
            labels: {
                formatter: (value) =>
                    isPercent
                        ? `${value.toFixed(1)}%`
                        : `${Math.round(value).toLocaleString()} ₩`
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
        stroke: { width: 3, curve: "smooth" }
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
