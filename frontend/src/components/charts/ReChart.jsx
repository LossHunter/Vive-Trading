import React, { useState, useMemo } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import "../../styles/Chart.css";

export default function RealTimeCandleChart({ bot, data }) {
  const [isPercent, setIsPercent] = useState(false);

  // 퍼센트 변화 계산
  const getPercentChanges = (arr) => {
    const validArr = arr.filter(v => v != null);
    const startValue = validArr[0] ?? 1000;
    return arr.map(v => (v == null ? null : ((v - startValue) / startValue) * 100));
  };

  // 데이터 처리
  const chartData = useMemo(() => {
    const filteredUsers = data.filter(user => bot === "all" || user.userId === bot);
    
    // 모든 시간 포인트 수집
    const allTimestamps = new Set();
    filteredUsers.forEach(user => {
      user.time.forEach(t => allTimestamps.add(new Date(t).getTime()));
    });
    
    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);
    
    // 각 시간별로 데이터 구성
    return sortedTimestamps.map(timestamp => {
      const point = { timestamp };
      
      filteredUsers.forEach(user => {
        const timeIndex = user.time.findIndex(t => new Date(t).getTime() === timestamp);
        if (timeIndex !== -1) {
          const values = isPercent 
            ? getPercentChanges(user.total)
            : user.total;
          point[user.username] = values[timeIndex];
        }
      });
      
      return point;
    });
  }, [data, bot, isPercent]);

  // 유저 정보
  const userInfo = useMemo(() => {
    return data
      .filter(user => bot === "all" || user.userId === bot)
      .map(user => ({
        username: user.username,
        color: user.colors
      }));
  }, [data, bot]);

  // Y축 포맷터
  const yAxisFormatter = (value) => {
    if (value == null || isNaN(value)) return "";
    return isPercent
      ? `${value.toFixed(0)}%`
      : `${(value / 1000000).toFixed(1)}M`;
  };

  // X축 포맷터
  const xAxisFormatter = (timestamp) => {
    const date = new Date(timestamp);
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  // 툴팁 포맷터
  const tooltipFormatter = (value) => {
    if (value == null) return "";
    return isPercent
      ? `${value.toFixed(2)}%`
      : `${Math.round(value).toLocaleString()} ₩`;
  };

  return (
    <div className="chart-container">
      <div className="chart-title">
        <button onClick={() => setIsPercent(prev => !prev)}>
          {isPercent ? "₩ View" : "% View"}
        </button>
        <p>Real-Time Bot Account Asset</p>
      </div>
      
      <ResponsiveContainer width="100%" height="90%">
        <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={xAxisFormatter}
            type="number"
            domain={['dataMin', 'dataMax']}
            scale="time"
          />
          <YAxis tickFormatter={yAxisFormatter} />
          <Tooltip 
            formatter={tooltipFormatter}
            labelFormatter={(timestamp) => new Date(timestamp).toLocaleString('ko-KR')}
          />
          <Legend />
          
          {userInfo.map(user => (
            <Line
              key={user.username}
              type="monotone"
              dataKey={user.username}
              stroke={user.color}
              strokeWidth={2}
              dot={false}
              connectNulls={true}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}