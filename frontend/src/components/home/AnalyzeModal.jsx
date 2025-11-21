import '../../styles/AnalyzeModal.css';
import ReactDOM from "react-dom";
import { useMemo, useState } from 'react';

export default function AanalyzeModal({ currentAnalyze, modalopen, setModalOpen }) {
    const [searchTime, setSearchTime] = useState("");

    // Hook은 항상 최상단에서 호출
    const filteredAnalysis = useMemo(() => {
        if (!currentAnalyze?.time) return [];
        return currentAnalyze.time
            .map((time, index) => ({
                time: time, // 타임스탬프 → YYYY-MM-DD HH:MM
                usemodel: currentAnalyze.usemodel?.[index],
                why: currentAnalyze.why?.[index],
                position: currentAnalyze.position?.[index],
            }))
            .filter(item =>
                searchTime.trim() === "" ||
                (item.time && item.time.includes(searchTime.trim()))
            );
    }, [currentAnalyze, searchTime]);

    if (!modalopen) return null;

    return ReactDOM.createPortal(
        <div className="modal-backdrop" onClick={() => setModalOpen(false)}>
            <div className="modal-box" onClick={(e) => e.stopPropagation()}>
                <div className='title'>
                    <input
                        className="Search"
                        placeholder="YYYY-MM-DD HH:MM"
                        type="text"
                        value={searchTime}
                        onChange={e => setSearchTime(e.target.value)}
                    />
                </div>

                {filteredAnalysis.length > 0 ? (
                    filteredAnalysis.map((item, index) => (
                        <div className="history-card" key={index}>
                            <h2>## Time: {item.time ?? "Unknown Time"}</h2>
                            <p>* Model: {item.usemodel ?? "Unknown Model"}</p>
                            <p>* Reason: {item.why ?? "No Reason"}</p>
                            <p>* Position: {item.position ?? "No Position"}</p>
                        </div>
                    ))
                ) : (
                    searchTime.trim() !== "" && (
                        <div className="history-card no-results">
                            <p>'{searchTime}'에 해당하는 검색 결과가 없습니다.</p>
                        </div>
                    )
                )}
            </div>
        </div>,
        document.body
    );
}
