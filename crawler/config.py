import os

from dotenv import load_dotenv

load_dotenv()

# Path to the binary, profile, and driver of the browser
# BINARY_PATH = r"C:\\Users\\SII\\Desktop\\Tor Browser\\Browser\\firefox.exe"
BINARY_PATH = "/opt/homebrew/Caskroom/tor-browser/14.0.4/Tor Browser.app/Contents/MacOS/firefox"
# PROFILE_PATH = r"C:\Users\\SII\\Desktop\\Tor Browser\\Browser\\TorBrowser\\Data\\Browser\\profile.default"
PROFILE_PATH = "/opt/homebrew/Caskroom/tor-browser/14.0.4/Tor Browser.app/Contents/Resources/TorBrowser/Tor"
GECKO_DRIVER_PATH = ("/opt/homebrew/opt/geckodriver/bin/geckodriver")

# MongoDB connection string
MONGO_HOST = 'localhost'
MONGO_PORT = 27017
MONGO_USER = ''
MONGO_PASS = ''

# All the websites to be scraped
SITES = [
     {
        'name': 'suprbay',
        'urls': [
            'http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion/Thread-Tiktok-and-Twitter-integration',
        ],
    },
    {
        'name': 'breach',
        'urls': [
            'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-Cryptos-Any-thoughts-on-Sparrow-Wallet-on-Tails'
         ]
    },
    {
        'name': 'leftychan',
        'urls': [
            'http://leftychans5gstl4zee2ecopkv6qvzsrbikwxnejpylwcho2yvh4owad.onion/posad/index.html'
        ],
        'idpost': '65a8b9f1c1e2d34f8a9b0001'
    },
    {
        'name': 'pitch',
        'urls': [
            'http://pitchprash4aqilfr7sbmuwve3pnkpylqwxjbj2q5o4szcfeea6d27yd.onion/t/OSINT'
        ]
    },
    {
        'name': 'defcon',
        'urls': [
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236100',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/229539',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/243287',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/237639',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/244569',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/241346',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/235968',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236468',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236468',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236548',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236392',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236350',
            # 'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236313'
        ]
    },
    # {
    #     "name": "breakingbad",
    #     "urls": [
    #         "http://bbzzzsvqcrqtki6umym6itiixfhni37ybtt7mkbjyxn2pgllzxf2qgyd.onion/threads/how-do-i-get-access-to-the-rc-section.433",
    #         "http://bbzzzsvqcrqtki6umym6itiixfhni37ybtt7mkbjyxn2pgllzxf2qgyd.onion/threads/phenylacetone-p2p-synthesis-via-bmk-ethyl-glycidate.7549/",
    #         "http://bbzzzsvqcrqtki6umym6itiixfhni37ybtt7mkbjyxn2pgllzxf2qgyd.onion/threads/amphetamine-synthesis-from-p2np-via-al-hg-video.196/"
    #     ],
    # },
    # {
    #     'name': 'abyss',
    #     'urls': [
    #         'http://qyvjopwdgjq52ehsx6paonv2ophy3p4ivfkul4svcaw6qxlzsaboyjid.onion/viewtopic.php?t=1470',
    #         'http://qyvjopwdgjq52ehsx6paonv2ophy3p4ivfkul4svcaw6qxlzsaboyjid.onion/viewtopic.php?t=1123',
    #         'http://qyvjopwdgjq52ehsx6paonv2ophy3p4ivfkul4svcaw6qxlzsaboyjid.onion/viewtopic.php?t=685'
    #     ]
    # },
    # {
    #     'name': 'zone1b',
    #     'urls': [
    #         'https://zone1b.com/threads/wells-fargo-account-needed.2129/',
    #         'https://zone1b.com/threads/black-friday-sale-cc-5-dumps-10-paypal-logs-10-bank-logs-only-10.2082/',
    #         'https://zone1b.com/threads/carded-products-available-at-cheap-prices.1977/'
    #     ]
    # },
    {
        "name": "endchan",
        "urls": [
            "",
            "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion/b/res/45481.html"
            "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion/b/res/40139.html",
            "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion/b/res/48276.html",
        ],
    },
    # http://e735q7rop3xday7y3nbguaeggl5ss6vez6rz4oxwhs3p2sqrx45vhiqd.onion/index.php?sid=2c3c4328f70c3f0249a9fb4937233623
    # {
    #     # "name": "bwc",
    #     # "urls": [
    #     #     "http://e735q7rop3xday7y3nbguaeggl5ss6vez6rz4oxwhs3p2sqrx45vhiqd.onion/viewtopic.php?f=44&t=642&sid=bc12406583101df6b546c2dd95868237",
    #         # 'http://e735q7rop3xday7y3nbguaeggl5ss6vez6rz4oxwhs3p2sqrx45vhiqd.onion/viewtopic.php?f=30&t=9420&sid=df97372f98099945b15ee81808262065',
    #         # 'http://e735q7rop3xday7y3nbguaeggl5ss6vez6rz4oxwhs3p2sqrx45vhiqd.onion/viewtopic.php?f=47&t=5908&sid=ccf410090f045ac0b2f105655e690c74',
    #         # 'http://e735q7rop3xday7y3nbguaeggl5ss6vez6rz4oxwhs3p2sqrx45vhiqd.onion/viewtopic.php?f=29&t=9529&sid=078b2ba79deedcae14f7030c59c0dbef',
    #         # 'http://e735q7rop3xday7y3nbguaeggl5ss6vez6rz4oxwhs3p2sqrx45vhiqd.onion/viewtopic.php?f=20&t=4553&sid=548752277f09445488f8bee57d8485fb'
    #     ],
    # },
    # http://oniongunutp6jfdhkgvsaucuunp4b7kqmbeeo5nxbxtnfxptlaxotmid.onion/
    # {
    #     "name": "oniongun",
    #     "urls": [
    #         "http://oniongunutp6jfdhkgvsaucuunp4b7kqmbeeo5nxbxtnfxptlaxotmid.onion/index.php?PHPSESSID=9ojn806mjm3in2kql3napgsut6&topic=20",
    #         "http://oniongunutp6jfdhkgvsaucuunp4b7kqmbeeo5nxbxtnfxptlaxotmid.onion/index.php?topic=888",
    #         "http://oniongunutp6jfdhkgvsaucuunp4b7kqmbeeo5nxbxtnfxptlaxotmid.onion/index.php?PHPSESSID=df12smi7lmhosn4d4s0t661qnc&topic=893",
    #     ],
    # },
    # http://nzdnmfcf2z5pd3vwfyfy3jhwoubv6qnumdglspqhurqnuvr52khatdad.onion/index.php
    # {
    #     "name": "nzdarknet",
    #     "urls": [
    #         "http://nzdnmfcf2z5pd3vwfyfy3jhwoubv6qnumdglspqhurqnuvr52khatdad.onion/viewtopic.php?id=2100",
    #         "http://nzdnmfcf2z5pd3vwfyfy3jhwoubv6qnumdglspqhurqnuvr52khatdad.onion/viewtopic.php?id=2820",
    #         "http://nzdnmfcf2z5pd3vwfyfy3jhwoubv6qnumdglspqhurqnuvr52khatdad.onion/viewtopic.php?id=2215",
    #     ],
    # },
]

PROFILES = [
    {
        "name": "breakingbad_profile",
        "profile_urls": [
            "http://bbzzzsvqcrqtki6umym6itiixfhni37ybtt7mkbjyxn2pgllzxf2qgyd.onion/threads/free-samples-from-bb-forum-for-everybody.10492/"
        ]
    },
    {
        "name": "endchan_profile",
        "profile_urls": [
            "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion/b/res/45481.html",
            "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion/b/res/40139.html",
            "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion/b/res/48276.html",
            "http://enxx3byspwsdo446jujc52ucy2pf5urdbhqw3kbsfhlfjwmbpj5smdad.onion/ausneets/res/922198.html"
        ]
    },
    {
        "name": "defcon_profile",
        "profile_urls": [
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/240683',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236100',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/229539',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/243287',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/237639',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/235968',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/244569',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/241346',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236468',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236468',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236548',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236392',
            'https://ezdhgsy2aw7zg5N4z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236350',
            'https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/236313'
        ]
    },
    {
        "name": "breach_profile",
        "profile_urls": [
            'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-Cryptos-Any-thoughts-on-Sparrow-Wallet-on-Tails'
            # 'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-post-thread-minimum-before-allowed-to-connect-to-shoutbox',
            # 'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-USA-whos-the-next-president',
            # 'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-ProtonMail-Security'
            # 'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-Mother-of-all-breaches-reveals-26-billion-records-what-we-know-so-far',
            # 'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-Middle-East-and-ww3',
            # 'http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Thread-Crypto-wallets--141940',
            
        ]
    },
    {
        "name": "suprbay_profile",
        "profile_urls": [
            'http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion/Thread-ThePirateBay-The-Pirate-Bay-Moves-to-a-Brand-New-Onion-Domain-v3',
        ],
        # 'idpost': '65a8b9f1c1e2d34f8a9b0001'
    },
    {
        "name": "pitch_profile",
        "profile_urls": [
            'http://pitchprash4aqilfr7sbmuwve3pnkpylqwxjbj2q5o4szcfeea6d27yd.onion/t/OSINT'
        ]
    },
    {
        "name": "leftychan_profile",
        "profile_urls": [
            'http://leftychans5gstl4zee2ecopkv6qvzsrbikwxnejpylwcho2yvh4owad.onion/tech/index.html'
        ]
    },
]

LINKS = [
    {
        "name": "breach_link",
        "link_urls": [
            "http://breached26tezcofqla4adzyn22notfqwcac7gpbrleg4usehljwkgqd.onion/Forum-The-Lounge"
        ]
    },
    {
        "name": "suprbay_link",
        "link_urls": [
            "http://suprbaydvdcaynfo4dgdzgxb4zuso7rftlil5yg5kqjefnw4wq4ulcad.onion/Forum-Other-Requests"
        ]
    },
    {
        "name": "defcon_link",
        "link_urls": [
            "https://ezdhgsy2aw7zg54z6dqsutrduhl22moami5zv2zt6urr6vub7gs6wfad.onion/node/19"
        ]
    },
    {
        "name": "flower_link",
        "link_urls": [
             "http://26yukmkrhmhfg6alc56oexe7bcrokv4rilwpfwgh2u6bsbkddu55h4ad.onion/lynx/index.html"
        ]
    },
    {
        "name": "foxdick_link",
        "link_urls": [
             "http://rcuhe6pk7mbmsjk7bwyja5etvjhjvzmc724rnf3piamemvawoi44z7qd.onion/b/"
        ]
    },
    {
        "name": "ptchan_link",
        "link_urls": [
             "http://jieq75a6uwqbj5sjzaxlnd7xwgs35audjmkk4g3gfjwosfrz7cp47xid.onion/muie/index.html"
        ]
    }
]
