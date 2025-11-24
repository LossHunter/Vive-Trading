import React, { useState, useEffect, useRef } from "react";
import '../../styles/AnalyzePanel.css';
import AanalyzeModal from "./AnalyzeModal"


export default function Analyze({ sender_analyze }) {
    const displayRef = useRef(null);
    const containerRef = useRef(null);
    const [modalopen, setModalOpen] = useState(false);
    const [selectedUser, setSelectedUser] = useState("README");
    const [isOpen, setIsOpen] = useState(false);

    const parseYYMMDDHHMM = (str) => {
        if (!str) return null;
        const yy = parseInt(str.slice(0, 2), 10);
        const year = yy >= 70 ? 1900 + yy : 2000 + yy;
        const month = parseInt(str.slice(2, 4), 10) - 1;
        const day = parseInt(str.slice(4, 6), 10);
        const hour = parseInt(str.slice(6, 8), 10);
        const min = parseInt(str.slice(8, 10), 10);
        return new Date(year, month, day, hour, min);
    };


    // 외부 클릭 시 드롭다운 닫기
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (containerRef.current && !containerRef.current.contains(event.target)) {
                setIsOpen(false);
            }
        };
        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    const handleSelect = (username) => {
        setSelectedUser(username);
        setIsOpen(false);
    };

    const currentAnalyze = (sender_analyze || []).find(a => a.username === selectedUser) || {
        username: selectedUser,
        usemodel: ["N/A"],
        time: [null],
        position: ["-"],
        why: ["-"],
    };
    
    return (
        <div className="right-panel">
            <div className="custom-select-container" ref={containerRef}>
                <div className="custom-select-header" onClick={() => setIsOpen(!isOpen)}>
                    {selectedUser}
                    <span className={`arrow ${isOpen ? 'up' : 'down'}`}></span>
                </div>

                {isOpen && (
                    <ul className="custom-select-options">
                        <li onClick={() => handleSelect("README")}>README</li>
                        {sender_analyze.map((analze, index) => (
                            <li key={index} onClick={() => handleSelect(analze.username)}>
                                {analze.username}
                            </li>
                        ))}
                    </ul>
                )}
            </div>

            <div className="right-space" />
            
            {selectedUser === "README" ? (
               <div className="ReadMe">
                    <h3>Welcome to README</h3>
                    <p>This is the default user guide and information panel.</p>
                    <p>You can select other users to see their analysis data.</p>
                </div>
            ) : (
            <button className="bot-position" ref={displayRef} onClick={() => setModalOpen(true)}>
                <div className="usemodel">
                    <p> Model : {currentAnalyze?.usemodel?.at(-1)} </p>
                </div>
                <div className="time">
                    <p>
                    Time : {currentAnalyze?.time?.at(-1)
                        ? (() => {
                            const date = parseYYMMDDHHMM(currentAnalyze.time.at(-1));
                            if (!date) return "-";
                            return `${date.getFullYear()}년 ${String(date.getMonth() + 1).padStart(2, "0")}월 ${String(date.getDate()).padStart(2, "0")}일 ${String(date.getHours()).padStart(2, "0")}시 ${String(date.getMinutes()).padStart(2, "0")}분`;
                        })()
                        : "-"
                    }
                    </p>
                </div>
                <div className="position">
                    <p>  Position : {currentAnalyze?.position?.at(-1)
                        ? currentAnalyze.position.at(-1).charAt(0).toUpperCase() + currentAnalyze.position.at(-1).slice(1)
                        : "-"
                    }</p>    
                </div>
                <div className="why">
                    <p>Reason : {currentAnalyze?.why?.at(-1) ?? "-"}</p>
                </div>
            </button>
            )}
            <AanalyzeModal 
                currentAnalyze={currentAnalyze} 
                modalopen={modalopen} 
                setModalOpen={setModalOpen} 
            />
        </div>
    );
}
