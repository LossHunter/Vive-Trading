import { useEffect, useState } from "react";
import { ID_data } from "../../services/Http_Post";
import Loading from "../Loading";
import "../../styles/Account.css"

export default function Account() {
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true); // 초기값 true

  useEffect(() => {
    (async () => {
      const data = await ID_data();
      setUserData(data?.[0] || null);
      setLoading(false); // 데이터 로드 후 false
    })();
  }, []);

  if (loading) return <Loading />; // 로딩 중이면 바로 Loading 표시
  if (!userData) return <div>데이터가 없습니다.</div>; // 데이터 없으면 안전 처리

  const accountInfo = {
    name: userData.username,
    time: userData.time,
    total: userData.total,
    bit: userData.bit,
    eth: userData.eth,
    xrp: userData.xrp,
    dog: userData.dog,
    sol: userData.sol,
    non: userData.non
  };

  return (
    <div className="account-container">
        <div className="top">
          <h2>Account Information</h2>
        </div>
        <div className="center">
          <div className="Name">
              <p>Name: {accountInfo.name} </p>
          </div>
          <div className="chartView">
              <p>Recent Account Change rate</p>
              <div className="chart"/>
          </div>
          <div className="coin_wallet">
              <p>Current Your Coin</p>
              <p>BIT : {accountInfo.bit.at(-1) ?? 0}</p>
              <p>ETH : {accountInfo.eth.at(-1) ?? 0}</p>
              <p>XRP : {accountInfo.xrp.at(-1) ?? 0}</p>
              <p>DOGE : {accountInfo.dog.at(-1) ?? 0}</p>
              <p>CASH : {accountInfo.non.at(-1)  ?? 0} ₩</p>
              <idv className="graph">

              </idv>
          </div>
          <div className="Created">
              <p>{accountInfo.time.at(0) ?? 0}</p>
          </div>
        </div>
    </div>
  );
}
