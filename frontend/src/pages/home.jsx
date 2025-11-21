import { useState, useEffect, use } from "react";
import '../styles/home.css';

// components/charts 폴더
import RealTimeCandleChart from '../components/charts/Chart.jsx'
// import RealTimeCandleChart from '../components/charts/ReChart.jsx'
// import RealTimeCandleChart from '../components/charts/LightChart.jsx'
// import RealTimeCandleChart from '../components/charts/EChart.jsx'

import Analyze from '../components/home/AnalyzePanel.jsx';

import WalletList from '../components/home/Wallet_Rank.jsx';

// serviecs 폴더
// import { fetchAllData  } from '../services/Http_Get.jsx';
// import { useSocketData } from '../services/Socket.jsx';
import { versionCheck, LoginfetchAllData } from '../services/Http_Post.jsx';

// components 폴더
import Loading from "../components/common/Loading.jsx"
import Header from "../components/common/Header.jsx";
import Footer from "../components/common/Footer.jsx";

function data_split(data) {
    const sender_chart = {
        userId: data.userId,
        username: data.username,
        total: data.total,
        colors: data.colors,
        logo: data.logo,
        time: data.time,
    };

    const sender_analyze = {
        userId: data.userId,
        username: data.username,
        usemodel: data.usemodel,
        logo: data.logo,
        time: data.time,
        why: data.why,
        position: data.position,
    };

    const sender_wallet = {
        userId: data.userId,
        username: data.username,
        usemodel: data.usemodel,
        total: data.total,
        colors: data.colors,
        logo: data.logo,
        time: data.time,
        non: data.non,
        bit: data.bit,
        eth: data.eth,
        dog: data.dog,
        sol: data.sol,
        xrp: data.xrp,
    };

    return { sender_chart, sender_analyze, sender_wallet };
}

export default function Home() {
    const [bot, setbot] = useState("all");
    const [InitData, setInitData] = useState(null);
    const [LiveData, setLiveData] = useState(null);
    const [MappingData, setMappingData] = useState([]);

    const [sender_chart, setsender_chart] = useState([]);
    const [sender_analyze, setsender_analyze] = useState([]);
    const [sender_wallet, setsender_wallet] = useState([]);

    const [loading, setLoading] = useState(true);

    // Open Db 삭제
    useEffect(() => {
        let finalAllData = [];
        const fetchData = async () => {
            const maxRetries = 3; // 최대 x번 시도
            let attempt = 0;

            while (attempt < maxRetries) {
                try {
                    const { allData, check } = await LoginfetchAllData();
                    finalAllData = allData

                    if (check === false) {
                        attempt++;
                        console.warn(`데이터 fetch 실패, 재시도 ${attempt}회`);
                        await new Promise(res => setTimeout(res, 200)); 
                        continue;
                    }
      
                    setInitData(allData);
                    return; 

                } catch (err) {
                    console.error(err);
                    attempt++;
                    await new Promise(res => setTimeout(res, 200)); // UX 관점에서 200ms 로 처리
                }
            }
            console.error("최대 재시도 5회 초과, 기본값으로 세팅");
            // alert("서버 불러오기 실패 관리자에게 문의하세요.") // 개발자 모드로 우선 안뜨게 조정
            setInitData(finalAllData);
        };

        fetchData();

        const intervalId = setInterval(fetchData, 3 * 60 * 1000); // 데이터 가져오기 3분당 한번 가져옴

        return () => clearInterval(intervalId);
    }, []);


    useEffect(() => {
        if (InitData) {
            try{
                setLiveData(InitData);
            }
            catch(err){
                console.error(err);
            }
        }
    }, [InitData]);

    useEffect(() => {
            if (LiveData) {
                setMappingData(LiveData)
            }
    }, [LiveData]);

    // 맵핑 데이터 분리 하기
    useEffect(() =>
    {
        if(MappingData) {
            const mapping_result = MappingData?.map(item => data_split(item));
            if(mapping_result.length > 0)
            {
                setsender_chart(mapping_result?.map(item => item.sender_chart));
                setsender_analyze(mapping_result?.map(item => item.sender_analyze));
                setsender_wallet(mapping_result?.map(item => item.sender_wallet));        
                setLoading(false);
            }
        }
    }, [MappingData])

   return (
    <>
        {loading ? (
        <Loading />
        ) : (
        <div className="frame">
            <Header/>
            <main>
            <div className="main-left">
                <div className="bot-selection">
                <div className="all-wallet" onClick={() => setbot("all")}>
                    All Bot Model
                </div>
                <WalletList sender_wallet={sender_wallet} setbot={setbot}/>
                </div>
            </div>
            <div className="main-center">
                <RealTimeCandleChart 
                key={JSON.stringify(sender_chart)} // 데이터 불러오면 차트 업데이트
                bot={bot} 
                data={sender_chart}/>
            </div>
            <div className="main-right">
                <Analyze sender_analyze={sender_analyze} />
            </div>
            </main>
            <Footer />
        </div>
        )}
    </>
    );
}

