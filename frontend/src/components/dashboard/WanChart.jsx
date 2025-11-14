import Chart from "react-apexcharts";

// 문자열에서 숫자만 추출하고 없으면 0 반환
function extractNumber(value) {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const match = value.match(/-?\d+(\.\d+)?/); // 정수 또는 소수만 추출
    if (match) return parseFloat(match[0]);
  }
  return 0;
}

export default function WandChart({ data }) {
  // 숫자로 변환된 데이터
  const numericData = data.chart_data
    .map(v => {
      const num = extractNumber(v);
      return num !== null ? num : 0;
    });

  // x축 최대값
  const xMax = numericData.length;

  // x축 단위 계산: max 10 → 1, max 11~20 → 2, max 21~30 → 3 ...
  const xStep = Math.ceil(xMax / 10);

  // x축 값 배열 생성
  const xValues = numericData.map((_, idx) => idx + 1);

  const options = {
    chart: {
      id: "wand-chart",
      toolbar: { show: false },
      zoom: { enabled: false },  // 확대/축소 비활성
      pan: { enabled: false },   // 패닝 비활성
      animations: { enabled: false } // 필요시 애니메이션도 제거
    },
    xaxis: {
      min: 1,
      max: xMax,
      tickAmount: Math.ceil(xMax / xStep),
      categories: xValues,
      title: { text: "Step" },
      labels: {
        formatter: (val) => val.toString(),
      },
    },
    yaxis: {
      title: { text: data.metric_name },
      labels: {
        formatter: (val) => (isNaN(val) ? val : Number(val).toExponential(2)), // 지수 표기 2자리
      },
    },
    tooltip: {
      y: {
        formatter: (val) => (isNaN(val) ? val : Number(val).toExponential(2)),
      },
    },
    title: {
      text: data.run_name,
      align: "center",
    },
    stroke: { curve: "straight" },
  };

  // series 데이터는 {x, y} 형태
  const series = [
    {
      name: data.metric_name,
      data: numericData.map((y, idx) => ({ x: idx + 1, y })),
    },
  ];

  return <Chart options={options} series={series} type="line" height="100%" width="100%" />;
}
