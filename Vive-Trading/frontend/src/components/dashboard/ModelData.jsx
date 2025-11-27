import WandChart from "./WanChart.jsx";
import { useEffect, useState } from "react";
import "../../styles/ModelData.css";
import Loading from "../common/Loading.jsx";
import WanData from "../../services/WanDB_Api.jsx";

export default function ModelData() {
  const [loading, setLoading] = useState(true);
  const data = WanData();

  useEffect(() => {
    if (data && data.length > 0) {
      setLoading(false);
    }
  }, [data]);

  // 데이터를 그룹별/메트릭별로 정리
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

  // 상위 그룹 클릭
  const handleGroupClick = (key) => {
    setSelectedGroup(key);
    if (key !== "전체보기") {
      const firstSubKey = Object.keys(groupedData[key])[0];
      setSelectedSubGroups([`${key}:${firstSubKey}`]);
    } else {
      setSelectedSubGroups([]); // 전체보기일 땐 하위 선택 초기화
    }
  };

  // 하위 그룹 클릭 시 선택 토글
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
      // 전체보기일 때는 모든 그룹/메트릭 데이터 반환
      return Object.entries(groupedData).flatMap(([group, subGroup]) =>
        Object.values(subGroup).flat()
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

  // 하위 그룹 버튼 리스트 (전체보기일 때는 비워둠)
  const subGroupKeys =
    selectedGroup !== "전체보기" && selectedGroup
      ? Object.keys(groupedData[selectedGroup]).map((subKey) => ({
          group: selectedGroup,
          subKey,
        }))
      : [];

  return (
    <>
      {loading ? (
        <Loading />
      ) : (
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

          {/* 하위 그룹 버튼: 전체보기일 때는 렌더링하지 않음 */}
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
      )}
    </>
  );
}
