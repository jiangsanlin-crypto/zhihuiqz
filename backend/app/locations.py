"""KhmerHire internal Cambodia location reference.

Codes are product-internal stable identifiers, not government or ISO codes.
The province list covers all 25 first-level administrative areas. District
seed data is intentionally focused on launch markets and can be expanded
without changing API contracts.
"""

PROVINCES = [
    {"code":"phnom_penh","km":"ភ្នំពេញ","en":"Phnom Penh","zh":"金边"},
    {"code":"banteay_meanchey","km":"បន្ទាយមានជ័យ","en":"Banteay Meanchey","zh":"班迭棉吉"},
    {"code":"battambang","km":"បាត់ដំបង","en":"Battambang","zh":"马德望"},
    {"code":"kampong_cham","km":"កំពង់ចាម","en":"Kampong Cham","zh":"磅湛"},
    {"code":"kampong_chhnang","km":"កំពង់ឆ្នាំង","en":"Kampong Chhnang","zh":"磅清扬"},
    {"code":"kampong_speu","km":"កំពង់ស្ពឺ","en":"Kampong Speu","zh":"磅士卑"},
    {"code":"kampong_thom","km":"កំពង់ធំ","en":"Kampong Thom","zh":"磅同"},
    {"code":"kampot","km":"កំពត","en":"Kampot","zh":"贡布"},
    {"code":"kandal","km":"កណ្ដាល","en":"Kandal","zh":"干拉"},
    {"code":"kep","km":"កែប","en":"Kep","zh":"白马"},
    {"code":"koh_kong","km":"កោះកុង","en":"Koh Kong","zh":"国公"},
    {"code":"kratie","km":"ក្រចេះ","en":"Kratie","zh":"桔井"},
    {"code":"mondulkiri","km":"មណ្ឌលគិរី","en":"Mondulkiri","zh":"蒙多基里"},
    {"code":"oddar_meanchey","km":"ឧត្តរមានជ័យ","en":"Oddar Meanchey","zh":"奥多棉吉"},
    {"code":"pailin","km":"ប៉ៃលិន","en":"Pailin","zh":"拜林"},
    {"code":"preah_sihanouk","km":"ព្រះសីហនុ","en":"Preah Sihanouk","zh":"西哈努克"},
    {"code":"preah_vihear","km":"ព្រះវិហារ","en":"Preah Vihear","zh":"柏威夏"},
    {"code":"prey_veng","km":"ព្រៃវែង","en":"Prey Veng","zh":"波罗勉"},
    {"code":"pursat","km":"ពោធិ៍សាត់","en":"Pursat","zh":"菩萨"},
    {"code":"ratanakiri","km":"រតនគិរី","en":"Ratanakiri","zh":"腊塔纳基里"},
    {"code":"siem_reap","km":"សៀមរាប","en":"Siem Reap","zh":"暹粒"},
    {"code":"stung_treng","km":"ស្ទឹងត្រែង","en":"Stung Treng","zh":"上丁"},
    {"code":"svay_rieng","km":"ស្វាយរៀង","en":"Svay Rieng","zh":"柴桢"},
    {"code":"takeo","km":"តាកែវ","en":"Takeo","zh":"茶胶"},
    {"code":"tbong_khmum","km":"ត្បូងឃ្មុំ","en":"Tbong Khmum","zh":"特本克蒙"},
]

DISTRICTS = {
    "phnom_penh": [
        {"code":"chamkar_mon","en":"Chamkar Mon","zh":"桑园区"},
        {"code":"daun_penh","en":"Daun Penh","zh":"隆边区"},
        {"code":"mean_chey","en":"Mean Chey","zh":"棉芷区"},
        {"code":"sen_sok","en":"Sen Sok","zh":"森速区"},
        {"code":"por_sen_chey","en":"Por Sen Chey","zh":"波森芷区"},
        {"code":"chroy_changvar","en":"Chroy Changvar","zh":"水净华区"},
    ],
    "kandal": [
        {"code":"ta_khmau","en":"Ta Khmau","zh":"大金欧"},
        {"code":"ang_snuol","en":"Ang Snuol","zh":"安斯努"},
        {"code":"khsach_kandal","en":"Khsach Kandal","zh":"干拉斯登"},
    ],
    "kampong_speu": [
        {"code":"chbar_mon","en":"Chbar Mon","zh":"查巴蒙"},
        {"code":"samraong_tong","en":"Samraong Tong","zh":"森隆东县"},
    ],
    "takeo": [
        {"code":"doun_kaev","en":"Doun Kaev","zh":"敦胶"},
        {"code":"bati","en":"Bati","zh":"巴提"},
    ],
    "svay_rieng": [
        {"code":"bavet","en":"Bavet","zh":"巴域"},
        {"code":"svay_rieng_city","en":"Svay Rieng","zh":"柴桢市"},
    ],
    "preah_sihanouk": [
        {"code":"sihanoukville","en":"Sihanoukville","zh":"西哈努克市"},
        {"code":"prey_nob","en":"Prey Nob","zh":"波雷诺"},
    ],
}

PROVINCE_CODES = {item["code"] for item in PROVINCES}
