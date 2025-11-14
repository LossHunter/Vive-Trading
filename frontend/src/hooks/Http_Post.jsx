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
