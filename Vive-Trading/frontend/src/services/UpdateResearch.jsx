export default function UpdateSource({ get_wan_version, get_asset_version }) {
    let WAN_VERSION = localStorage.getItem("WAN_VERSION");
    let ASSET_VERSION = localStorage.getItem("ASSET_VERSION");

    if (WAN_VERSION !== get_wan_version) {
        localStorage.setItem("WAN_VERSION", get_wan_version);
        WAN_VERSION = get_wan_version;
    }

    if (ASSET_VERSION !== get_asset_version) {
        localStorage.setItem("ASSET_VERSION", get_asset_version);
        ASSET_VERSION = get_asset_version;
    }

    const Wan_DB = WAN_VERSION;
    const Asset_Chart_DB = ASSET_VERSION;

    return { Wan_DB, Asset_Chart_DB };
}