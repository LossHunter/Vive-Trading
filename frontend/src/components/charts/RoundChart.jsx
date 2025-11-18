import React from "react";
import Chart from "react-apexcharts";
import "../../styles/Chart.css";

export default function RoundChart({data}) {

    const hasNonZero = data?.some(item => item.value > 0);
    const chartData = hasNonZero
        ? data
        : [
            { name: "BIT", value: 20 },
            { name: "ETH", value: 20 },
            { name: "XRP", value: 20 },
            { name: "DOGE", value: 20 },
            { name: "CASH", value: 20 },
        ];

    const series = chartData.map(item => item.value);
    const labels = chartData.map(item => item.name);

    const options = {
        chart: { type: "donut" },
        labels: labels,
        legend: { position: "bottom" },
        dataLabels: { enabled: true },
        responsive: [
        {
            breakpoint: 480,
            options: { chart: { width: 300 }, legend: { position: "bottom" } },
        },
        ],
    };

    return (
        <div style={{ width: "350px", height: "350px", margin: "auto" }}>
        <Chart options={options} series={series} type="donut" width="100%" height="100%" />
        </div>
    );
}
