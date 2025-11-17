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
const parentColor = getComputedStyle(document.documentElement)
  .getPropertyValue('--text-color') || '#000'; // 기본값 #000
export default function WandChart({ data }) {
  // 숫자로 변환된 데이터
  const numericData = data.chart_data.map(v => {
    const num = extractNumber(v);
    return num !== null ? num : 0;
  });

  const xMax = numericData.length;

  // series 데이터: x값은 0부터 시작
  const series = [
    {
      name: data.metric_name,
      data: numericData.map((y, idx) => ({ x: idx, y })),
    },
  ];

  const options = {
    chart: {
      id: "wand-chart",
      toolbar: { show: false },
      zoom: { enabled: false },
      pan: { enabled: false },
      animations: { enabled: false },
    },
    xaxis: {
      type: "numeric",
      min: 0,
      max: xMax - 1,       // 데이터 마지막 인덱스
      tickInterval: 1,     // 항상 1씩 증가
      title: { 
        text: "Step"
      },
      labels: {
        formatter: (val) => {
          if (val >= xMax) return ""; // 마지막 번호 필요 없으면 공백
          return val + 1;             // 시각적으로 1부터 표시
        },
      },
    },
    yaxis: {
      labels: {
        formatter: (val) =>
          isNaN(val) ? val : Number(val).toExponential(2),
      },
    },
    tooltip: {
      y: {
        formatter: (val) =>
          isNaN(val) ? val : Number(val).toExponential(2),
      },
    },
    title: {
      text: data.metric_name,
      align: "center",
    },
    stroke: { curve: "straight" },
  };

  return (
    <Chart
      options={options}
      series={series}
      type="line"
      height="100%"
      width="100%"
    />
  );
}
