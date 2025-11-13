import { useState, useEffect } from "react";
import '../styles/home.css';
import RealTimeCandleChart from '../components/Chart.jsx'
import Analyze from '../components/AnalyzePanel.jsx';

import WalletList from '../components/Wallet_Rank';

import { fetchAllData  } from '../components/Http_Get.jsx';
import { useSocketData } from '../components/Socket.jsx';

import Loading from "../components/Loading.jsx"
import Header from "../components/Header.jsx";
import Footer from "../components/Footer.jsx";

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
    const [lastTime, setlastTime] = useState("");

    // 초기데이터 불러오기
    useEffect(() => {
        (async () => {
            try {
                const { allData, lastTime } = await fetchAllData();
                setInitData(allData);
                setlastTime(lastTime)
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        })();
    }, []);

    // 초기 데이터 맵핑하기
    useEffect(() => {
            if (InitData) {
                const mixed = accumulate(InitData);
                setMappingData(mixed);
                setLiveData(InitData);
            }
    }, [InitData]);
    

    const socket_data = useSocketData({lastTime});

    // 초기 데이터에 추가 데이터 합치기
    useEffect(() => {
        if (LiveData) {
            const re_data = [...LiveData, socket_data];  // 새 배열 생성
            setLiveData(re_data);
        }
    }, [socket_data]);

    // 재 맵핑하기
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
            setsender_chart(mapping_result?.map(item => item.sender_chart));
            setsender_analyze(mapping_result?.map(item => item.sender_analyze));
            setsender_wallet(mapping_result?.map(item => item.sender_wallet));
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

