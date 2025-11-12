import React, { useState, useEffect } from "react";
import { useNavigate, useLocation  } from "react-router-dom";
import '../styles/home.css';
import RealTimeCandleChart from '../components/Chart.jsx'
import Analyze from '../components/AnalyzePanel.jsx';

import WalletList from '../components/Wallet_Rank';
import LoginModel from './login.jsx';

import { fetchAllData  } from '../components/Http_Get.jsx';
import { useSocketData } from '../components/Socket.jsx';

import Header from "../components/Header.jsx";

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
    const navigate = useNavigate();
    const [bot, setbot] = useState("all");
    const [InitData, setInitData] = useState(null);
    const [LiveData, setLiveData] = useState(null);
    const [MappingData, setMappingData] = useState([]);

    const [isOpen, setIsOpen] = useState(false);

    const [sender_chart, setsender_chart] = useState([]);
    const [sender_analyze, setsender_analyze] = useState([]);
    const [sender_wallet, setsender_wallet] = useState([]);

    // 초기데이터 불러오기
    useEffect(() => {
        (async () => {
        const allData = await fetchAllData();
        setInitData(allData);
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
    
    // 추가 데이터 불러오기
    const socket_data = useSocketData();

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

    // 로그인 상황 파악
    const location = useLocation();
    useEffect(() => {
        const savedCode = localStorage.getItem("googleAuthCode");

        if (savedCode) {
            const searchParams = new URLSearchParams(location.search);

            if (searchParams.get("code") !== savedCode) {
                searchParams.set("code", savedCode);
                navigate(`${location.pathname}?${searchParams.toString()}`, { replace: true });
            }
        }
    }, [location, navigate]);

    return (
        <div className="frame">
            <Header/>

            <main>
                <div className="main-left" >
                    <div className="bot-selection">
                        <div className="all-wallet"
                            onClick={() => setbot("all")}>
                            All Bot Model</div>
                        <WalletList sender_wallet={sender_wallet} setbot={setbot} />
                    </div>
                </div>
                <div className="main-center" >
                    <RealTimeCandleChart bot={bot} data={sender_chart} />
                </div>
                <div className="main-right" >
                    <Analyze sender_analyze={sender_analyze} />
                </div>
            </main>

            <footer>
                <div className="footer-content">
                    <p>
                        **생성형 AI 1회차 프로젝트** |
                        AI 기반 투자 분석 및 실시간 트래커 시스템
                    </p>
                    <p>
                        데이터 소스: Upbit WebSocket API |
                        차트 라이브러리: ApexCharts
                    </p>
                    <p>
                        © 2025 Team [T-Bone]. All Rights Reserved.
                    </p>
                </div>
            </footer>

            {isOpen && <LoginModel onClose={() => setIsOpen(false)} />}
        </div>
    );
}

