import { useState, useEffect } from "react";
import '../styles/home.css';
import RealTimeCandleChart from '../components/charts/Chart.jsx'
// import RealTimeCandleChart from '../components/charts/ReChart.jsx'
// import RealTimeCandleChart from '../components/charts/LightChart.jsx'
// import RealTimeCandleChart from '../components/charts/EChart.jsx'

import Analyze from '../components/AnalyzePanel.jsx';

import WalletList from '../components/Wallet_Rank';

import { fetchAllData  } from '../hooks/Http_Get.jsx';
import { useSocketData } from '../hooks/Socket.jsx';

import Loading from "../components/Loading.jsx"
import Header from "../components/Header.jsx";
import Footer from "../components/Footer.jsx";

import { saveUpdate, loadUpdate, clearStore } from "../components/OpenDB.jsx"
import { versionCheck } from '../hooks/Http_Post.jsx';

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
        logo: data.logo,
        time: data.time,
        why: data.why,
        position: data.position,
    };

    const sender_wallet = {
        userId: data.userId,
        username: data.username,
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

function accumulate(init_data) {
    const nums = [1, 2, 3, 4];
    const datalist = [];
    nums.forEach(num => {
        const userData = [];
        let userid, username, color, logo;

        init_data.forEach(dayArray => {
            dayArray.forEach(item => {
                if (item.userId === num) {
                    userid = item.userId;
                    username = item.username;
                    color = item.colors;
                    logo = item.logo;

                    const { xrp, dog, why, btc, time, total, sol, non, eth, position } = item;
                    userData.push({ xrp, dog, why, btc, time, total, sol, non, eth, position});
                }
            });
        });

        const remapped = {
            userId: userid,
            username: username,
            why: userData.map(d => d.why),
            position: userData.map(d => d.position),
            total: userData.map(d => d.total),
            colors: color,
            logo: logo,
            time: userData.map(d => d.time),
            non: userData.map(d => d.non),
            bit: userData.map(d => d.btc),
            eth: userData.map(d => d.eth),
            dog: userData.map(d => d.dog),
            sol: userData.map(d => d.sol),
            xrp: userData.map(d => d.xrp),
        };

        datalist.push(remapped);
    });

    return datalist;
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
    const [lastTime, setLastTime] = useState("");

    const [isCacheExisit, setIscacheExisit] = useState(true);
    const [socketEnabled, setSocketEnabled] = useState(false);
    
    useEffect(() => {
        (async () => {
            const cachedData = await loadUpdate("Chart_data", 1);
            if (cachedData) {
                const allDates = cachedData.data.map(dayArr => dayArr[0]?.time);
                const isSequential = allDates.every((date, i) => {
                    if (i === 0) return true;
                    const prev = new Date(allDates[i - 1]);
                    const curr = new Date(date);
                    const diffDays = (curr - prev) / (1000 * 60 * 60 * 24);
                    return diffDays === 1;
                });

                if (!isSequential) {
                    setIscacheExisit(false);
                    return;
                }

                const isVersion = await versionCheck({version : cachedData.time});
                if (isVersion)
                {
                    setIscacheExisit(false)
                    return
                }

                setInitData(cachedData.data);
                setLastTime(cachedData.time);
            }
            else
            {
                setIscacheExisit(false)
            }
        })();
    }, []);

    useEffect(() => {
        if (isCacheExisit === false) {
            (async () => {
                try {
                    await clearStore("Chart_data", 1);
                    const { allData, cachlastTime } = await fetchAllData();

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
                const mixed = accumulate(LiveData);
                setMappingData(mixed)
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
                setLoading(false);
                
            }
        }

    }, [MappingData])

    useEffect(()=>
    {
        if(sender_chart)
        {
            setSocketEnabled(true);
        }
    },[sender_chart])

    const { socket_data, socketlasttime } = useSocketData({ lastTime, enabled: socketEnabled });

    // 초기 데이터에 추가 데이터 합치기
    useEffect(() => {
        if (LiveData) {
            const re_data = [...LiveData, socket_data];
            setLiveData(re_data);
        }
    }, [socket_data]);

    useEffect(() => {
        if (socketlasttime){
            (async () => {
                try {
                    const insertdata = {
                        time: socketlasttime,
                        data: LiveData
                    };

                    await saveUpdate("Chart_data", 1, insertdata);
                } catch (err) {
                    console.error("DB 저장 에러:", err);
                }
            })();
        }
    }, [socketlasttime]);

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

