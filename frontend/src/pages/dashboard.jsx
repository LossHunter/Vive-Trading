import { useState, useEffect } from "react";
import Header from "../components/Header"
import "../styles/dashboard.css"

import Footer from "../components/Footer"

import { useNavigate } from "react-router-dom";

import Account from "../components/dashboard/Account"
import ModelData from "../components/dashboard/ModelData"
import Prompt from "../components/dashboard/Prompt"
import Readme from "../components/dashboard/Readme"

export default function DashBoard() {
    const [select, setSelect] = useState("Account")

    const navigate = useNavigate();

    const menu = ["Account", "ModelData", "Prompt", "Readme"]     

    const goSelect = (menu) => {
        const search = new URLSearchParams(location.search); 
        search.set("select", menu.toLowerCase());         
        navigate(`/dashboard?${search.toString()}`, { replace: true });
    };

    useEffect(()=>
    {
        goSelect(select)
    },[select]);
    
    return (
        <div className="frame">
            <Header />
            <div className="dash-main">
                <div className="dash-main-left">
                    {menu.map((item, index)=>
                    (
                        <button 
                        className="menu"
                        key={item}
                        onClick={()=>setSelect(item)}>
                            {item}
                        </button>
                    ))}
                </div>
                <div className="dash-main-center">
                    {select === "Account" && <Account />}
                    {select === "ModelData" && <ModelData/>}
                    {select === "Prompt" && <Prompt />}
                    {select === "Readme" && <Readme />}
                </div>
            </div>
            <Footer />
        </div>
        )
}
