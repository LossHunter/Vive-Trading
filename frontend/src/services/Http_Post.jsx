export async function versionCheck({ version }) {
  try {
    if (!version) {
      throw new Error("version is undefined");
    }

    const versionStr = typeof version === "string" 
      ? version.replace(/\//g, '-') 
      : version.toISOString().split('T')[0];

    const res = await fetch(`${import.meta.env.VITE_POST_URL}/api/versioncheck`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version: versionStr }),
    });

    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

    return await res.json();
  } catch (err) {
    console.error("Fetch error:", err);
    return false;
  }
}

export async function LoginTokenSend(AuthorizeCode) {
  try {
    const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/GoogleLogin`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token : AuthorizeCode }),
      credentials: 'include' // ✅ 쿠키 포함
    });

    if(!res.ok)
    {
      console.error("HTTP Error:", res.status);
      return false;
    }
    return true;
  } catch(err)
  {
    console.error("Fetch error:", err);
    return false;
  }
}

export async function LogOut() {
    const maxRetries = 3;
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/logout`, {
                method: "POST",
                credentials: "include",
            });
            
            if (!res.ok) {
                throw new Error(`HTTP error! status: ${res.status}`);
            }

            return true; // 성공 시 true 반환
        } catch (err) {
            console.error(`로그아웃 실패 (시도 ${attempt}):`, err);
            if (attempt < maxRetries) {
                await new Promise(resolve => setTimeout(resolve, 500)); // 0.5초 대기 후 재시도
            } else {
                return false; // 마지막 시도까지 실패하면 false 반환
            }
        }
    }
}

export async function LoginfetchAllData() {
    const defaultAllData = [
        {
            userId: 'default_user_01',
            username: 'Default Bot',
            colors: '#cccccc',
            logo: 'default_logo.png',
            usemodel: [null],
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
    const defaultCacheLastTime = 0; // 초기 로딩 시 기본값은 0 또는 현재 시간으로 설정 가능

    try {
        const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/wallet`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ check: true }),
            credentials: 'include',
        });

        if (!res.ok) {
            // 1. 서버 응답은 받았으나 상태 코드가 실패인 경우 (예: 404, 500)
            throw new Error(`서버 응답 실패: ${res.status}`);
        }

        const data = await res.json();
        console.log("Data : ", data)
        // 2. 서버에서 데이터를 받았으나 배열이 비어있는 경우
        if (!data || data.length === 0) {
            console.log("서버에서 빈 데이터 수신, 기본값 반환");
            return { allData: defaultAllData, cachlastTime: defaultCacheLastTime };
        }

        // UTC 기준으로 수정
        const parseTime = (value) => {
            const str = String(value);
            const year = +str.slice(0, 4);
            const month = +str.slice(4, 6) - 1;
            const day = +str.slice(6, 8);
            const hour = +str.slice(8, 10);
            const minute = +str.slice(10, 12);
            // UTC 기준으로 Date 생성 => 차트오류
            return Date.UTC(year, month, day, hour, minute, 0);
        };

        // 데이터 매핑 로직 (기존 코드와 동일)
        const allData = data.map(item => {
            const userData = item.map(dayArray => ({
                why: dayArray.why,
                position: dayArray.position,
                total: dayArray.total,
                time: parseTime(dayArray.time),
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
        
        // LastTime 삭제
        const check = true;
        return { allData, check };

    } catch (err) {
        console.error("데이터 가져오기 실패, 기본값 반환:", err);
        const check = false;
        return { allData: defaultAllData, check };
    }
}

export async function ID_data() {
  try {
    const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/getUser`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    if (!res.ok) throw new Error("서버 응답 실패");

    const data = await res.json();

  const parseTimeToString = (value) => {
      const str = String(value).padStart(12, '0'); // 혹시 길이 부족하면 0 채우기
      const year = str.slice(0, 4);
      const month = str.slice(4, 6);
      const day = str.slice(6, 8);
      const hour = str.slice(8, 10);
      const minute = str.slice(10, 12);
      return `${year}-${month}-${day} ${hour}:${minute}`;
  };

    const userData = data.map(item => {
      return {
        userId: item.userId,
        username: item.username,
        colors: item.colors,
        logo: item.logo,
        usemodel: [item.usemodel],
        why: [item.why],
        position: [item.position],
        total: [item.total],
        time: [parseTimeToString(item.time)],
        non: [item.non],
        bit: [item.bit],
        eth: [item.eth],
        dog: [item.doge],
        sol: [item.sol],
        xrp: [item.xrp],
      };
    });
    
    return userData;

  } catch (err) {
    console.error("데이터 가져오기 실패:", err);
  }
}