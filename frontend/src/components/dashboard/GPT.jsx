import '../../styles/History.css'
import { useEffect, useState } from 'react';

export default function GPT({ analyzeData }) {
    const [searchTime, setSearchTime] = useState("");
    const data = analyzeData.filter(item => item.username === 'GPT');
    
    const filteredData = data.map(item => {
        const { position, time, why, usemodel } = item;
        return { position, time, why, usemodel };
    });

    const combinedData =[]

    if (filteredData.length > 0) {
        const item = filteredData[0]; // username이 하나니까 첫번째만 사용
        for (let i = 0; i < item.time.length; i++) {
            combinedData.push({
                time: item.time[i],
                position: item.position[i],
                why: item.why[i],
                usemodel: item.usemodel[i],
            });
        }
    }
    const displayedData = combinedData.filter(item => 
        item.time.includes(searchTime)
    );

    return (
        <div className='history-container'>
            <input
                className="Search"
                placeholder="YYYYMMDDHHMM"
                type="text"
                value={searchTime}
                onChange={e => setSearchTime(e.target.value)}
            />
            <div className="card-container">
                {displayedData.length > 0 ? (
                    displayedData.map((item, index) => (
                        <div className="card-history" key={index}>
                            <h2>## Time: {item.time}</h2>
                            <p>* Model: {item.usemodel}</p>
                            <p>* Reason: {item.why}</p>
                            <p>* Position: {item.position}</p>
                        </div>
                    ))
                ) : (
                    searchTime.trim() !== "" && (
                        <div className="card-history no-results">
                            <p>'{searchTime}'에 해당하는 검색 결과가 없습니다.</p>
                        </div>
                    )
                )}
            </div>
        </div>
    );
}