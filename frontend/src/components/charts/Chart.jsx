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

    
    const datamapping = data.map(item => ({
        userId: item.userId,
        username: item.username,
        total_asset: item.total,
        colors: item.colors,
        logo: item.logo,
        time: item.time.map(t => new Date(t).getTime())
    }));

    // 필터링된 시리즈 데이터
    // const filteredSeries = datamapping
    //     .filter(user => bot === "all" || user.userId === bot)
    //     .map(user => {
    //         const yValues = isPercent
    //         ? getPercentChanges(user.total_asset)
    //         : user.total_asset;

    //         const dataPoints = user.time.map((t, idx) => ({
    //         x: t,           // 밀리초 값 그대로
    //         y: yValues[idx] ?? 0  // 값 없으면 0
    //         }));

    //         return {
    //         name: user.username,
    //         color: user.colors,
    //         logo: user.logo,
    //         data: dataPoints
    //         };
    //     });

    // y값이 전부 0이면 차트에서제외
    let filteredSeries = datamapping
        .filter(user => bot === "all" || user.userId === bot)
        .filter(user => {
            // total_asset이 모두 0이면 제외
            const yValuesRaw = isPercent
                ? getPercentChanges(user.total_asset)
                : user.total_asset;
            // 하나라도 0이 아닌 값이 있으면 true, 모두 0이면 false
            return yValuesRaw.some(v => v !== 0 && v != null);
        })
        .map(user => {
            const yValuesRaw = isPercent
                ? getPercentChanges(user.total_asset)
                : user.total_asset;

            const dataPoints = user.time.map((t, idx) => ({
                x: t,
                y: yValuesRaw[idx] ?? 0
            }));

            return {
                name: user.username,
                color: user.colors,
                logo: user.logo,
                data: dataPoints
            };
        });

            
    const allTimes = filteredSeries.flatMap(s => s.data.map(d => d.x));
    const minTime = Math.min(...allTimes);
    const maxTime = Math.max(...allTimes);

    // 짧은 시리즈 마지막에 null 추가
    // X축 배열 수정
    filteredSeries = filteredSeries.map(s => {
        const lastX = s.data[s.data.length - 1]?.x ?? minTime;
        if (lastX < maxTime) {
            return {
                ...s,
                data: [
                    ...s.data,
                    { x: maxTime, y: null }
                ]
            };
        }
        return s;
    });

    // Y축 계산 (+30%/-30% 여유)
    const initialMoney = 100_000_000;
    const initialPercent = 0;

    const yValuesAll = filteredSeries.flatMap(s =>
        s.data.map(d => d.y).filter(v => v != null)
    );

    const rawYMin = isPercent
        ? Math.min(...yValuesAll, initialPercent)
        : Math.min(...yValuesAll, initialMoney);

    const rawYMax = isPercent
        ? Math.max(...yValuesAll, initialPercent)
        : Math.max(...yValuesAll, initialMoney);

    const yMin = rawYMin * 0.96; 
    const yMax = rawYMax * 1.04;  

    const y_unit = 10_000_000;
    const yMinTick = isPercent
        ? Math.floor(yMin / 10) * 10
        : Math.floor(yMin / y_unit) * y_unit;

    const yMaxTick = isPercent
        ? Math.ceil(yMax / 10) * 10
        : Math.ceil(yMax / y_unit) * y_unit;

    const yTickAmount = isPercent
        ? Math.ceil((yMaxTick - yMinTick) / 10)
        : Math.ceil((yMaxTick - yMinTick) / y_unit);

    useEffect(() => {
        const hasPoints = filteredSeries.some(s => s.data && s.data.length > 0);
        if (hasPoints) setLoading(false);
    }, [filteredSeries]);

    const timePadding = (maxTime - minTime) * 0.05; 

    // 마커 추가
    // X축 여유값 추가
    // Y축 맞추도록 추가
    const options = {
        chart: {
            type: "line",
            height: 350,
            animations: { enabled: true, easing: "linear", speed: 800 },
        },
        xaxis: {
            type: "datetime",
            max: maxTime + timePadding,
            labels: {
                rotate: -45,
                style: { fontSize: "10px" },
                formatter: function(value) {
                const date = new Date(value);
                date.setHours(date.getHours() + 9); // UTC -> KST
                return `${date.getFullYear()}-${(date.getMonth()+1).toString().padStart(2,'0')}-${date.getDate().toString().padStart(2,'0')} ${date.getHours().toString().padStart(2,'0')}:${date.getMinutes().toString().padStart(2,'0')}`;
                }
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
        markers: {
            size: 0,       // 포인트 크기
            hover: { size: 5 } // hover 시 확대
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
