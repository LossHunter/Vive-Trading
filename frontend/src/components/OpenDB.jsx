import { openDB, deleteDB  } from 'idb';

export default async function getDB() {
  try {
    const db = await openDB("VT_DB", 1, {
      
      upgrade(db) {
        if (!db.objectStoreNames.contains("Chart_data")) {
          db.createObjectStore("Chart_data");
        }
        if (!db.objectStoreNames.contains("Model_data")) {
          db.createObjectStore("Model_data");
        }
      },
    });
    return db;
  } catch (err) {
    console.warn("DB 열기 실패, 삭제 후 재시도:", err);
 
    await deleteDB("VT_DB");

    const db = await openDB("VT_DB", 1, {
      upgrade(db) {
        if (!db.objectStoreNames.contains("Chart_data")) {
          db.createObjectStore("Chart_data");
        }
        if (!db.objectStoreNames.contains("Model_data")) {
          db.createObjectStore("Model_data");
        }
      },
    });
    return db;
  }
}

export async function saveUpdate(storeName, updateNumber, data) {
  try{
    const db = await getDB();
    const tx = db.transaction(storeName, "readwrite");
    await tx.objectStore(storeName).put(data, updateNumber);
    await tx.done;
    return true;
  }
  catch {
    return false;
  }
}

export async function loadUpdate(storeName, updateNumber) {
  const db = await getDB();
  const tx = db.transaction(storeName, "readonly");
  const data = await tx.objectStore(storeName).get(updateNumber);
  await tx.done;
  return data;
}

export async function clearStore(storeName, updateNumber) {
  try{
    const db = await getDB();
    const tx = db.transaction(storeName, "readwrite");
    await tx.objectStore(storeName).delete(updateNumber); // 특정 key 삭제
    await tx.done;
    return true;
  }catch{
    return false;
  }
}