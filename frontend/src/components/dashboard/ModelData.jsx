import WandChart from "./WanChart.jsx";
import { useState } from "react";
import "../../styles/ModelData.css";

export default function ModelData({ data }) {
  // 데이터 그룹화: run_name의 접두사 기준 + metric_name 기준
  const groupedData = data.reduce((acc, item) => {
    const runPrefix = item.run_name.split("-")[0];
    if (!acc[runPrefix]) acc[runPrefix] = {};

    const metricName = item.metric_name;
    if (!acc[runPrefix][metricName]) acc[runPrefix][metricName] = [];
    acc[runPrefix][metricName].push(item);

    return acc;
  }, {});

  const groupKeys = ["전체보기", ...Object.keys(groupedData)];
  const [selectedGroup, setSelectedGroup] = useState(groupKeys[0]);
  const [selectedSubGroups, setSelectedSubGroups] = useState([]);

  // 그룹 선택 시 하위 선택 초기화
  const handleGroupClick = (key) => {
    setSelectedGroup(key);
    if (key !== "전체보기") {
      setSelectedSubGroups([`${key}:${Object.keys(groupedData[key])[0]}`]);
    } else {
      // 전체보기 선택 시 모든 하위 그룹 선택 초기화
      const allSubGroups = Object.entries(groupedData).flatMap(([group, subGroup]) =>
        Object.keys(subGroup).map((subKey) => `${group}:${subKey}`)
      );
      setSelectedSubGroups(allSubGroups);
    }
  };

  // 하위 그룹 클릭 시 배열에 추가/제거
  const handleSubGroupClick = (group, subKey) => {
    const fullKey = `${group}:${subKey}`;
    setSelectedSubGroups((prev) =>
      prev.includes(fullKey)
        ? prev.filter((k) => k !== fullKey)
        : [...prev, fullKey]
    );
  };

  // 렌더링할 데이터 계산
  const renderData = () => {
    if (selectedGroup === "전체보기") {
      return Object.entries(groupedData).flatMap(([group, subGroup]) =>
        Object.entries(subGroup).flatMap(([metricName, items]) => {
          if (selectedSubGroups.includes(`${group}:${metricName}`)) return items;
          return [];
        })
      );
    } else if (selectedGroup && selectedSubGroups.length > 0) {
      return selectedSubGroups
        .filter((key) => key.startsWith(selectedGroup + ":"))
        .flatMap((key) => {
          const subKey = key.split(":")[1];
          return groupedData[selectedGroup][subKey];
        });
    }
    return [];
  };

  // 하위 그룹 버튼 리스트
  const subGroupKeys =
    selectedGroup === "전체보기"
      ? Object.entries(groupedData).flatMap(([group, subGroup]) =>
          Object.keys(subGroup).map((subKey) => ({ group, subKey }))
        )
      : selectedGroup
      ? Object.keys(groupedData[selectedGroup]).map((subKey) => ({
          group: selectedGroup,
          subKey,
        }))
      : [];

  return (
    <div className="tap-model">
      {/* 상위 그룹 버튼 */}
      <div className="model-button">
        {groupKeys.map((key) => (
          <button
            key={key}
            className={selectedGroup === key ? "active" : ""}
            onClick={() => handleGroupClick(key)}
          >
            {key}
          </button>
        ))}
      </div>

      <div className="space" />

      {/* 하위 그룹 버튼 */}
      {subGroupKeys.length > 0 && (
        <div className="sub-model-button">
          {subGroupKeys.map(({ group, subKey }) => {
            const fullKey = `${group}:${subKey}`;
            return (
              <button
                key={fullKey}
                className={selectedSubGroups.includes(fullKey) ? "active" : ""}
                onClick={() => handleSubGroupClick(group, subKey)}
              >
                {subKey}
              </button>
            );
          })}
        </div>
      )}

      <div className="space" />

      {/* 차트 렌더링 */}
      <div className="model-data">
        {renderData().map((item, index) => (
          <div key={index} className="wandcart">
            <WandChart data={item} />
          </div>
        ))}
      </div>
    </div>
  );
}
