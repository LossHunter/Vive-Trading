import { saveUpdate, loadUpdate, clearStore } from "../../components/common/OpenDB.jsx";

function data_sum(ex_data, new_data) {
    new_data.forEach(newUserArr => {
        const userId = newUserArr[0].userId;
        const existingUserArr = ex_data.find(userArr => userArr[0].userId === userId);

        if (existingUserArr) {
            existingUserArr.push(...newUserArr);
        } else {
            ex_data.push(newUserArr);
        }
    });

    return ex_data;
}

function formatToYYMMDDHHMM(dateStr) {
  const date = new Date(dateStr);

  const yyyy = date.getUTCFullYear().toString();
  const mm = String(date.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(date.getUTCDate()).padStart(2, '0');
  const hh = String(date.getUTCHours()).padStart(2, '0');
  const min = String(date.getUTCMinutes()).padStart(2, '0');

  return `${yyyy}${mm}${dd}${hh}${min}`;
}

export default async function LoginfetchAllData() {
    const defaultAllData = [
        {
            userId: 'default_user_01',
            username: 'Default Bot',
            colors: '#cccccc',
            logo: 'default_logo.png',
            why: [null],
            position: [null],
            total: [0], 
            time: [0], 
            non: [null],
            bit: [null],
            eth: [null],
            dog: [null],
            sol: [null],
            xrp: [null],
        },
    ];

    try {
        // indexedb time 라인 비교후 가져오기 식
        // 웹 db 클리어 하면 time이 undefined 또는 null이 되므로 다지워짐
        // await clearStore("min3", 1); // 개발환경 배포 시 반드시 주석 처리

        // indexedb 데이터 불러오기
        const cachedData = await loadUpdate("min3", 1);

        let latest_time = "0";
        if (cachedData?.time) latest_time = cachedData.time;
        
        let ex_data = cachedData?.data || [];

        const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/wallet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ latest_time }),
            credentials: 'include',
        });

        if (!res.ok) return { allData: defaultAllData, check: false };

        const data = await res.json();
        
        let sum_data = [];
        if (data.data === "Nodata") {
            sum_data = ex_data.length > 1 ? ex_data : defaultAllData;
        } else {
            sum_data = data_sum(ex_data, data.data);
            await saveUpdate("min3", 1, { time: data.time, data: sum_data });
        }

        const allData = sum_data.map(item => {
            const userData = item.map(dayArray => ({
                why: dayArray.why,
                position: dayArray.position,
                total: dayArray.total,
                time: formatToYYMMDDHHMM(dayArray.time),
                non: dayArray.non,
                bit: dayArray.bit,
                eth: dayArray.eth,
                dog: dayArray.doge,
                sol: dayArray.sol,
                xrp: dayArray.xrp,
                usemodel: dayArray.usemodel
            }));

            const { userId, username, colors, logo } = item[0];

            return {
                userId,
                username,
                colors,
                logo,
                usemodel: userData.map(d => d.usemodel),
                why: userData.map(d => d.why),
                position: userData.map(d => d.position),
                total: userData.map(d => d.total),
                time: userData.map(d => d.time),
                non: userData.map(d => d.non),
                bit: userData.map(d => d.bit),
                eth: userData.map(d => d.eth),
                dog: userData.map(d => d.dog),
                sol: userData.map(d => d.sol),
                xrp: userData.map(d => d.xrp),
            };
        });

        return { allData, check: true };

    
    } catch (err) {
        console.error("데이터 가져오기 실패, 기본값 반환:");
        return { allData: defaultAllData, check: false };
    }
}
