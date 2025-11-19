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

export async function LoginfetchAllData(time) {
  try {
    const res = await fetch(`${import.meta.env.VITE_GET_URL}/api/wallet`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lasttime: time }),
      credentials: 'include',
    });

    if (!res.ok) throw new Error("서버 응답 실패");

    const data = await res.json();

    const parseTime = (value) => {
        const str = String(value);
        const year = +str.slice(0, 4);
        const month = +str.slice(4, 6) - 1; 
        const day = +str.slice(6, 8);
        const hour = +str.slice(8, 10);
        const minute = +str.slice(10, 12);
        return new Date(year, month, day, hour, minute, 0).getTime(); 
    };

    // usermodel 사용
    // home, dashboard/AnalzePanel

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

      const { userId, username, colors, logo } = item[0]; // 첫 번째 요소에서 공통 정보 가져오기

      return {
        userId,
        username,
        colors,
        logo,
        usemodel:userData.map(d => d.usemodel),
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
    
    const firstUser = allData[0];       
    const cachlastTime = firstUser.time.at(-1); 
    return { allData, cachlastTime };

  } catch (err) {
    console.error("데이터 가져오기 실패:", err);
    return null;
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