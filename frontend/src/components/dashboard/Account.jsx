import { useEffect, useState } from "react";
import { ID_data } from "../../services/Http_Post";
import Loading from "../Loading";
import "../../styles/Account.css";
import RoundChart from "../../components/charts/RoundChart"
import RealTimeCandleChart from "../../components/charts/Chart"

function data_split(data) {
    const sender_chart = {
        userId: data.userId,
        username: data.username,
        total: data.total,
        colors: data.colors,
        logo: data.logo,
        time: data.time,
    };

    return sender_chart;
}

export default function Account() {
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true); // 초기 로딩 상태
  const [senderChart, setSenderChart] = useState(null);
  const [searchTime, setSearchTime] = useState("");

  useEffect(() => {
    const fetchData = async () => {
      // 서버 연결 실패 시 사용할 기본값 (모든 값 배열로 통일)
      const defaultData = {
        userId: 0,
        username: "Unknown",
        colors: "",
        logo: "",
        usermodel: ["Unknown"],
        why: [],
        position: [],
        total: [0],
        time: ["0000-00-00 00:00"],
        non: [0],
        bit: [0],
        eth: [0],
        dog: [0],
        sol: [0],
        xrp: [0],
      };

      try {
        const data = await ID_data();
        setUserData(data?.[0] ?? defaultData);

      } catch (err) {
        setUserData(defaultData);
        console.error("데이터 가져오기 실패:", err);
      } finally {

      }
    };

    fetchData();
  }, []);

  const defaultBot = {
    name: "Default Bot",
    interval: "1m",
    settings: {},
  };

  useEffect(() => {
    if (userData) {
      setSenderChart(data_split(userData));
      setLoading(false);
    }
  }, [userData]);

  const filteredData = (userData?.time ?? [])
    .map((t, index) => ({
      time: t,
      reason: userData.why?.[index],
      position: userData.position?.[index],
      total: userData.total?.[index],
    }))
  .filter(item => item.time.includes(searchTime));


  if (loading) return <Loading />; // 로딩 중 표시

  // userData가 항상 존재하도록 default 처리

  return (
    <div className="account-container">
      <div className="center">
          <div className="account-live">
              <h2>Account Information</h2>
                <div className="infro">
                <p>Name: {userData.username}</p>
                <p>Created: {userData.time?.[0] ?? "0000-00-00 00:00"}</p>
                <p>
                  UserModel: {userData.usermodel.at(-1) ?? "Unknown"}
                </p>
                <p>
                  Post : 
                  <input
                    type="text">
                  </input>
                </p>
                <p>
                  Phone-Number : 
                  <input
                    type="text">
                  </input>
                </p>
                <p>
                  Current Membership :
                </p>
                <button>
                  Save
                </button>
              </div>
          </div>

          <div className="coin_wallet">
              <h2>Account Live</h2>
              <div className="roundchart">
                <RoundChart data={[
                  { name: "BIT", value: userData.bit.at(-1) },
                  { name: "ETH", value: userData.eth.at(-1) },
                  { name: "XRP", value: userData.xrp.at(-1) },
                  { name: "DOGE", value: userData.dog.at(-1) },
                  { name: "CASH", value: userData.non.at(-1) },
                ]} />
              </div>
          </div>

        <div className="history">
          <input
            className="Search"
            placeholder="YYYY-MM-DD HH:MM"
            type="text"
            value={searchTime}
            onChange={e => setSearchTime(e.target.value)}
          />
          <div className="hitroy-data">
            {filteredData.map((item, index) => (
              <div className="history-card" key={index}>
                <h4>Time: {item.time ?? "Unknown Time"}</h4>
                <p>Reason: {item.reason ?? "No Reason"}</p>
                <p>Position: {item.position ?? "No Position"}</p>
                <p>Total: {item.total ?? 0}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
