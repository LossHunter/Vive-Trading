import React, { useState, useEffect, useRef } from "react";
import '../styles/AnalyzePanel.css';

export default function Analyze({ sender_analyze }) {
    const displayRef = useRef(null);
    const containerRef = useRef(null);

    const [selectedUser, setSelectedUser] = useState("README");
    const [isOpen, setIsOpen] = useState(false);

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

    const currentAnalyze = sender_analyze.find(a => a.username === selectedUser);

    return (
        <div className="right-panel">
            <div className="right-tag">History</div>

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

            <button className="bot-position" ref={displayRef}>
                <div className="time">
                    <p>
                    Time Point : {currentAnalyze?.time?.at(-1)
                        ? new Date(currentAnalyze.time.at(-1)).getFullYear() + "년 " +
                        String(new Date(currentAnalyze.time.at(-1)).getMonth() + 1).padStart(2, "0") + "월 " +
                        String(new Date(currentAnalyze.time.at(-1)).getDate()).padStart(2, "0") + "일"
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
        </div>
    );
}
