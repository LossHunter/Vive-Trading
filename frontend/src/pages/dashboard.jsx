import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";

import Header from "../components/common/Header"
import Footer from "../components/common/Footer"

import "../styles/dashboard.css"
import Account from "../components/dashboard/Account"

import GPT from "../components/dashboard/GPT"
import GEMMA from "../components/dashboard/GEMMA"
import DEEPSEEK from "../components/dashboard/DEEPSEEK"
import QWEN from "../components/dashboard/QWEN"

export default function DashBoard({ analyzeData }) {
    const navigate = useNavigate();
    const location = useLocation();
    const menu = ["Account", "GPT", "GEMMA", "DEEPSEEK", "QWEN"];

    // 1. URL 쿼리에서 select 가져오기
    const searchParams = new URLSearchParams(location.search);
    const initialSelect = menu.find(
        item => item.toLowerCase() === searchParams.get("select")
    ) || "Account";

    const [select, setSelect] = useState(initialSelect);

    // 2. select 바뀌면 URL 업데이트
    const goSelect = (menuItem) => {
        const search = new URLSearchParams(location.search); 
        search.set("select", menuItem.toLowerCase());         
        navigate(`/dashboard?${search.toString()}`, { replace: false });
    };

    useEffect(() => {
        goSelect(select);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [select]);

    // 3. 뒤로가기/앞으로가기 감지
    useEffect(() => {
        const search = new URLSearchParams(location.search);
        const urlSelect = menu.find(
            item => item.toLowerCase() === search.get("select")
        ) || "Account";
        setSelect(urlSelect);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [location.search]);

    return (
        <div className="frame">
            <Header />
            <div className="dash-main">
                <div className="dash-main-left">
                    {menu.map((item) => (
                        <button 
                            className="menu"
                            key={item}
                            onClick={() => setSelect(item)}
                        >
                            {item}
                        </button>
                    ))}
                </div>
                <div className="dash-main-center">
                    {select === "Account" && <Account />}
                    {select === "GPT" && <GPT analyzeData={analyzeData} />} 
                    {select === "GEMMA" && <GEMMA analyzeData={analyzeData} />}
                    {select === "DEEPSEEK" && <DEEPSEEK analyzeData={analyzeData} />}
                    {select === "QWEN" && <QWEN analyzeData={analyzeData} />}
                </div>
            </div>
            <Footer />
        </div>
    );
}