import { useState, useEffect, use } from "react";
import '../styles/home.css';

// components/charts 폴더
import RealTimeCandleChart from '../components/charts/Chart.jsx'
// import RealTimeCandleChart from '../components/charts/ReChart.jsx'
// import RealTimeCandleChart from '../components/charts/LightChart.jsx'
// import RealTimeCandleChart from '../components/charts/EChart.jsx'

import Analyze from '../components/AnalyzePanel.jsx';

import WalletList from '../components/Wallet_Rank';

// serviecs 폴더
import { fetchAllData  } from '../services/Http_Get.jsx';
import { useSocketData } from '../services/Socket.jsx';
import { versionCheck, LoginfetchAllData } from '../services/Http_Post.jsx';

// components 폴더
import Loading from "../components/Loading.jsx"
import Header from "../components/Header.jsx";
import Footer from "../components/Footer.jsx";

import { saveUpdate, loadUpdate, clearStore } from "../components/OpenDB.jsx"


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

    const [isCacheExisit, setisCacheExisit] = useState(true);
    const [lastTime, setLastTime] =useState("");

    useEffect(() => {
        const fetchData = async () => {
            const cachedData = await loadUpdate("Chart_data", 1);
            if (cachedData) {
                if (typeof cachedData.time === "undefined") {
                    setisCacheExisit(false);
                    return;
                }

                const allDates = cachedData.data.map(dayArr => dayArr[0]?.time);
                const isSequential = allDates.every((date, i) => {
                    if (i === 0) return true;
                    const prev = new Date(allDates[i - 1]);
                    const curr = new Date(date);
                    const diffDays = (curr - prev) / (1000 * 60 * 60 * 24);
                    return diffDays === 1;
                });

                if (!isSequential) {
                    setisCacheExisit(false);
                    return;
                }

                setInitData(cachedData.data);
                setLastTime(cachedData.time);
            } else {
                setisCacheExisit(false);
            }
        };

        fetchData();

        const intervalId = setInterval(fetchData, 3 * 60 * 1000);

        return () => clearInterval(intervalId);
    }, []);

    useEffect(() => {
        if (isCacheExisit === false) {
            (async () => {
                try {
                    await clearStore("Chart_data", 1);

                    let timeToSend = 0
                    
                    if(lastTime || lastTime == undefined || lastTime == "undefined")
                    {
                        timeToSend = lastTime
                    }

                    const { allData, cachlastTime } = await LoginfetchAllData(timeToSend);
                    const insertdata = {  time: cachlastTime, data: allData };
                    const result = await saveUpdate("Chart_data", 1, insertdata);
                    
                    if(result)
                    {                        
                        setInitData(allData);
                        setLastTime(cachlastTime);
                        return;
                    }
                } catch (err) {
                    console.error(err);
                }
            })();
        }
    }, [isCacheExisit]);

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

            if(mapping_result)
            {
                setsender_chart(mapping_result?.map(item => item.sender_chart));
                setsender_analyze(mapping_result?.map(item => item.sender_analyze));
                setsender_wallet(mapping_result?.map(item => item.sender_wallet));
                
            }
            const timer = setTimeout(() => {
                setLoading(false);
            }, 2000);
            return () => clearTimeout(timer);
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
                <WalletList sender_wallet={sender_wallet} setbot={setbot} />
                </div>
            </div>
            <div className="main-center">
                <RealTimeCandleChart bot={bot} data={sender_chart} />
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

