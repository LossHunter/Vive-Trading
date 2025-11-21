import React, { useState, useEffect } from "react";
import Chart from "react-apexcharts";
import "../../styles/Chart.css";
import Loading from "../../components/common/Loading";

export default function RealTimeCandleChart({ bot, data }) {
    const [isPercent, setIsPercent] = useState(false);
    const [loading, setLoading] = useState(true);

    const getPercentChanges = (arr) => {
        const validArr = arr.filter(v => v != null);
        const startValue = validArr[0] ?? 1000;
        return arr.map(v => (v == null ? null : ((v - startValue) / startValue) * 100));
    };

    // YYMMDDHHMM 문자열 → Date 객체 변환
    const parseYYMMDDHHMM = (str) => {
        const yy = parseInt(str.slice(0, 2), 10);
        const year = yy >= 70 ? 1900 + yy : 2000 + yy;
        const month = parseInt(str.slice(2, 4), 10) - 1;
        const day = parseInt(str.slice(4, 6), 10);
        const hour = parseInt(str.slice(6, 8), 10);
        const min = parseInt(str.slice(8, 10), 10);
        return new Date(year, month, day, hour, min);
    };

    // 데이터 매핑
    const datamapping = data.map(item => ({
        userId: item.userId,
        username: item.username,
        total_asset: item.total,
        colors: item.colors,
        logo: item.logo,
        time: item.time.map(t => parseYYMMDDHHMM(t).getTime())
    }));

    const botStr = String(bot);

    // 필터링 + series 생성
    const filteredSeries = datamapping
        .filter(user => bot === "all" || user.userId === botStr)
        .filter(user => user.total_asset.some(v => v != 0))
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
        });

    // Y축 범위 계산
    const yValuesAll = filteredSeries.flatMap(s => s.data.map(d => d.y));
    let yMinTick, yMaxTick;

    if (isPercent) {
        // 첫 값 기준 ±30%
        const firstValue = filteredSeries[0]?.data?.[0]?.y ?? 0;
        yMinTick = firstValue - 30;
        yMaxTick = firstValue + 30;
    } else {
        const minVal = yValuesAll.length > 0 ? Math.min(...yValuesAll) : 10_000_000;
        const maxVal = yValuesAll.length > 0 ? Math.max(...yValuesAll) : 10_000_000;
        yMinTick = Math.floor(minVal * 0.7 / 1_000_000) * 1_000_000;
        yMaxTick = Math.ceil(maxVal * 1.3 / 1_000_000) * 1_000_000;
    }

    // X축 범위 계산 (오른쪽 여유 20%)
    const allTimes = filteredSeries.flatMap(s => s.data.map(d => d.x));
    const minTime = allTimes.length > 0 ? Math.min(...allTimes) : Date.now();
    const maxTime = allTimes.length > 0 ? Math.max(...allTimes) : Date.now();
    const xMaxWithPadding = maxTime + (maxTime - minTime) * 0.2;

    useEffect(() => {
        const hasPoints = filteredSeries.some(s => s.data && s.data.length > 0);
        if (hasPoints) setLoading(false);
    }, [filteredSeries]);

    const options = {
        chart: {
            type: "line",
            height: 350,
            animations: { enabled: true, easing: "linear", speed: 800 }
        },
        stroke: { width: 3, curve: "straight" },
        markers: { size: 0, hover: { size: 5 } },
        xaxis: {
            type: "datetime",
            min: minTime,
            max: xMaxWithPadding,
            labels: {
                rotate: -45,
                style: { fontSize: "12px", colors: "black" },
                formatter: function(val) {
                    const date = new Date(val);
                    return `${date.getMonth() + 1}/${date.getDate()}`;
                }
            }
        },
        yaxis: {
            min: yMinTick,
            max: yMaxTick,
            tickAmount: isPercent
                ? 6
                : Math.floor((yMaxTick - yMinTick) / 1_000_000), // 100만 단위
            forceNiceScale: false,
            labels: {
                style: { fontSize: "12px", colors: "black" },
                formatter: (value) => {
                    if (value == null || isNaN(value)) return "";
                    return isPercent ? ` ${value.toFixed(1)}%` : Math.round(value);
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
        legend: { position: "top", labels: { colors: "inherit", useSeriesColors: false } },
        tooltip: {
            enabled: true,
            y: {
                formatter: function(val) {
                    if (val == null) return "-";
                    return isPercent ? ` ${val.toFixed(1)}%` : val.toLocaleString();
                }
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
