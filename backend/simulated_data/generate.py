import json
import os
import random
from datetime import datetime, timezone, timedelta

def generate_id() -> str:
    return os.urandom(8).hex()

ITEMS = [
    "Sony WH-1000XM5 headphones",
    "Apple AirPods Pro 2nd gen",
    "Samsung Galaxy S24 Ultra",
    "Dyson V15 vacuum cleaner",
    "Instant Pot Duo 7-in-1",
    "Kindle Paperwhite 11th gen",
    "Bose QuietComfort Earbuds II",
    "Google Pixel 8 Pro",
    "Ninja Air Fryer Max XL",
    "MacBook Air M3",
    "LG C3 OLED TV",
    "Roomba i3+ EVO",
    "Nespresso VertuoPlus",
    "GoPro HERO12 Black",
    "Garmin Forerunner 265",
    "Oura Ring Gen3",
    "PlayStation 5 Console",
    "Steam Deck OLED",
    "Breville Barista Express",
    "Logitech MX Master 3S",
]

SOURCES = ["amazon", "youtube", "reddit", "google"]

# Product-specific review templates keyed by keyword in product name
REVIEW_TEMPLATES = {
    "headphones": {
        "positive": [
            "The noise cancellation on these is absolutely incredible. I can work from a coffee shop and hear nothing but my music.",
            "Sound quality is top notch. The bass is deep without being overpowering, and the mids are crystal clear.",
            "Battery life is phenomenal — I get about 30 hours easily on a single charge.",
            "Best wireless headphones I've owned. The over-ear fit is comfortable even after 4+ hours of use.",
            "The call quality is superb. People on the other end say I sound clearer than on speakerphone.",
            "Wear detection works flawlessly — they pause music the moment I lift one ear cup.",
            "The companion app is polished and the EQ customization is excellent.",
            "ANC is so good it gives me pressure headaches in very quiet environments — that's how effective it is.",
            "Folding mechanism feels premium and they travel really well in the included hard case.",
        ],
        "mixed": [
            "Sound is excellent but I find the ANC makes my ears feel a bit pressurized after long sessions.",
            "Great headphones but the touch controls are overly sensitive — too many accidental skips.",
            "For the price they're good but I expected a bit more bass. Treble is a little sharp.",
            "Love the ANC but connectivity sometimes stutters when my phone screen is locked.",
            "Comfortable for 2 hours, after that the clamping force starts to bother me.",
            "Good sound quality but the Bluetooth range drops noticeably through walls.",
        ],
        "negative": [
            "Had these for 3 months and the right ear cup already has a crackling sound. Very disappointed.",
            "The multipoint Bluetooth feature drops my laptop connection constantly. Big issue for remote work.",
            "Way too expensive for what you get. My old pair sounded just as good for half the price.",
            "Build quality feels plasticky for a premium-priced product.",
            "Returned them after a week. The touch controls were infuriating — couldn't get used to them.",
        ],
    },
    "airpods": {
        "positive": [
            "The transparency mode is mind-blowing. It sounds more natural than just taking them out.",
            "Seamless switching between my iPhone, iPad, and MacBook. Apple ecosystem integration is unmatched.",
            "ANC is significantly better than the previous generation. Finally blocks out my open-plan office.",
            "The fit with the new ear tips is much more secure during workouts.",
            "H2 chip makes a noticeable difference in both ANC strength and audio quality.",
            "Battery life is solid and the MagSafe case is super convenient.",
            "Spatial audio with head tracking is genuinely impressive for movies and immersive content.",
        ],
        "mixed": [
            "Great sound but the ANC still lets through low rumbles like AC units.",
            "Love them but at this price I'd expect a slightly longer battery life.",
            "Perfect if you're in the Apple ecosystem. Less useful if you mix devices.",
            "Ear tips fit perfectly but I wish there were more sizes included.",
        ],
        "negative": [
            "Connection drops randomly a few times per week. Has to be a firmware bug.",
            "For the price, competitors offer better ANC and longer battery.",
            "One bud stopped charging after 4 months. Customer support was helpful but still frustrating.",
        ],
    },
    "vacuum": {
        "positive": [
            "Picks up pet hair like nothing I've ever seen. My husky's fur doesn't stand a chance.",
            "The laser dust detection is genuinely useful — shows you exactly what the standard light misses.",
            "Runs the full 60 minutes on eco mode, which is more than enough for my entire house.",
            "Lightweight and maneuverable. I can do the whole house without my arm getting tired.",
            "Emptying the bin is hygienic and easy — no touching the dust at all.",
            "Suction on max mode is insane — pulls stuff out of carpet I didn't know was there.",
            "Converts to a handheld in seconds. Great for stairs and car interiors.",
        ],
        "mixed": [
            "Excellent performance but the battery drains too fast on max mode — maybe 20 minutes.",
            "Great suction but the dustbin is smaller than I'd like. Need to empty it mid-clean on big sessions.",
            "Works brilliantly on hardwood. Carpet performance is good but not exceptional.",
            "The hair screw tool is great in theory but still needs occasional manual untangling.",
            "Pricey, but the cleaning performance does justify it for large homes with pets.",
        ],
        "negative": [
            "The hair screw tool jammed on my first use. Customer service eventually replaced it.",
            "At this price, I expected the attachments to feel more premium.",
            "Battery degraded noticeably after 18 months of heavy use.",
            "Noisy on max mode. Wouldn't use it while someone else is sleeping.",
        ],
    },
    "phone": {
        "positive": [
            "Camera system is absolutely best-in-class. Night mode photos are brighter than what my eye sees.",
            "The 200MP sensor is overkill in the best possible way. Zoom quality at 10x is remarkable.",
            "Performance is flawless. Not a single stutter or app crash in 6 months of heavy use.",
            "Battery easily lasts a full day even with heavy use. Fast charging is genuinely fast.",
            "Display is gorgeous — sharp, bright outdoors, and the 120Hz refresh makes everything silky.",
            "S Pen integration is more useful than I expected for quick notes and sketching.",
        ],
        "mixed": [
            "Excellent hardware but Samsung's bloatware situation is still frustrating in 2024.",
            "Camera quality is exceptional but processing can slightly over-sharpen portraits.",
            "The size is a bit unwieldy one-handed, but the display real estate is worth it.",
            "Great phone but the price puts it firmly in 'can't recommend to most people' territory.",
        ],
        "negative": [
            "Too big and too heavy. My wrist actually ached after extended use.",
            "Samsung Pay and some Samsung apps are redundant with Google equivalents.",
            "Dropped it from about 3 feet and the screen cracked. Durability is disappointing at this price.",
        ],
    },
    "air fryer": {
        "positive": [
            "Chicken wings come out crispier than deep fried. The family is obsessed.",
            "Preheats in 3 minutes and cooks faster than my oven. A genuine time saver.",
            "Easy to clean — the basket is non-stick and dishwasher safe.",
            "Large enough to cook for 4 people at once. The XL size is absolutely worth it.",
            "Fries, veggies, reheated pizza — everything comes out better than the oven.",
        ],
        "mixed": [
            "Food comes out great but it's louder than I expected.",
            "Works well but the controls are basic. A digital display with presets would help.",
            "Great capacity but takes up a lot of counter space.",
        ],
        "negative": [
            "The non-stick coating started flaking after 6 months. Had to replace it.",
            "Unevenly cooks larger items — need to shake/flip multiple times.",
        ],
    },
    "instant pot": {
        "positive": [
            "Pressure cooks a whole chicken in 25 minutes. Absolutely transformed my weeknight cooking.",
            "7-in-1 is no gimmick — I use the slow cook, sauté, and steam functions regularly.",
            "The sealing ring doesn't retain odors as much as I feared. Easy maintenance overall.",
            "Makes the most tender pulled pork I've ever had, consistently.",
            "Set it and forget it. I start dinner before my work calls and it's ready when I'm done.",
        ],
        "mixed": [
            "Excellent but the learning curve is real — took a few experiments to nail timing.",
            "Love it but it's big. Not ideal for small kitchens.",
            "Great results for soups and stews. Less impressive for rice compared to a dedicated rice cooker.",
        ],
        "negative": [
            "The lid seal cracked after about a year of weekly use.",
            "Instructions are unclear for beginners. Needed YouTube tutorials to feel confident.",
        ],
    },
    "kindle": {
        "positive": [
            "The waterproof design means I can read in the bath without anxiety. Game changer.",
            "300 PPI display is razor sharp — genuinely looks like ink on paper.",
            "Battery lasts weeks, not days. I charged it twice in two months of daily reading.",
            "Warm light feature is gentle on my eyes for late-night reading sessions.",
            "Thin, light, and fits perfectly in one hand. My physical books are collecting dust.",
        ],
        "mixed": [
            "Excellent e-reader but the page turn lag is occasionally noticeable on long swipes.",
            "Love the screen but the bezel is chunkier than it needs to be.",
        ],
        "negative": [
            "Wish it had physical page-turn buttons. Touch-only is less convenient when eating.",
            "Amazon's ecosystem lock-in is real — sideloading requires extra steps.",
        ],
    },
    "laptop": {
        "positive": [
            "M3 chip handles everything I throw at it — video editing, multiple VMs, no thermal throttling.",
            "Battery life is genuinely all-day. 12 hours of real mixed workload use.",
            "Completely silent under most workloads. The fanless design actually works at this performance level.",
            "The display is stunning — color accuracy is excellent for photo and video work.",
            "Lightest laptop I've owned and it's by far the fastest.",
        ],
        "mixed": [
            "Incredible performance but 8GB RAM base model feels limiting for pro workloads.",
            "macOS is polished but some niche Windows software I need requires Parallels.",
            "Love the hardware but only 2 USB-C ports is a real compromise.",
        ],
        "negative": [
            "RAM is soldered and non-upgradeable. The base model price vs storage upgrade cost is absurd.",
            "Gets warm during sustained GPU workloads — not hot, but warmer than expected for fanless.",
        ],
    },
    "tv": {
        "positive": [
            "OLED blacks are in a different league. Watching dark scenes in a dim room is cinematic.",
            "Gaming mode with 4K/120Hz and near-instant response time makes this a serious gaming display.",
            "WebOS is the best smart TV interface I've used — fast, logical, minimal ads.",
            "Colors are vibrant and accurate out of the box, especially in filmmaker mode.",
            "HDR content genuinely shines. The peak brightness for highlights is impressive.",
        ],
        "mixed": [
            "Stunning image but OLED brightness struggles in a very bright living room.",
            "Excellent panel but the built-in speakers are thin. Need a soundbar.",
            "Remote could be better — too many buttons, confusing layout.",
        ],
        "negative": [
            "Burned-in after 18 months of use with a static news ticker. Disappointing for the price.",
            "WebOS updates broke some apps temporarily. Frustrating for a premium product.",
        ],
    },
    "roomba": {
        "positive": [
            "Maps my house in one session and navigates perfectly after that. Zero random bumping.",
            "Handles the transition from hardwood to thick carpet without any hesitation.",
            "Auto-empty base means I only need to touch it once every few weeks.",
            "Scheduling via the app is dead simple and it always finishes the job.",
        ],
        "mixed": [
            "Good coverage but occasionally misses corners and tight spaces along walls.",
            "Works great but the auto-empty base is louder than expected when it empties.",
            "Handles pet hair well but the filter needs cleaning more often than advertised.",
        ],
        "negative": [
            "Got stuck on my bath mat three times in one week before I just removed it.",
            "The map reset itself after a firmware update. Had to let it remap from scratch.",
        ],
    },
    "coffee": {
        "positive": [
            "Espresso quality rivals my local coffee shop. The grinder produces a consistent grind every time.",
            "Steaming milk is intuitive once you get the technique down — microfoam is achievable.",
            "All-in-one design saves counter space compared to separate grinder and machine.",
            "Pressure gauge makes dialing in the grind size genuinely educational and fun.",
        ],
        "mixed": [
            "Makes excellent espresso but has a steep learning curve. Budget a month to dial it in.",
            "Great machine but the grinder is loud in the mornings.",
            "Coffee quality is exceptional but cleaning is a 15-minute daily commitment.",
        ],
        "negative": [
            "Grinder seized after 14 months. Repair was almost as expensive as a new machine.",
            "Takes 30 minutes to warm up properly in cold weather. Slow start to the morning.",
        ],
    },
    "gopro": {
        "positive": [
            "HyperSmooth 6.0 stabilization is unbelievable. Hiking footage looks like it was on a gimbal.",
            "Image quality in 4K60 is exceptional. Colors look natural and detail is impressive.",
            "Waterproof to 10m out of the box — no case needed for most water activities.",
            "Max Lens Mod 2.0 gives the widest, most immersive field of view I've seen on an action cam.",
        ],
        "mixed": [
            "Great video quality but battery drains fast in 4K60 — about 70 minutes.",
            "Excellent in good light, but low-light performance still lags behind smartphones.",
            "The subscription is annoying but the unlimited cloud backup is genuinely useful.",
        ],
        "negative": [
            "Overheats during long continuous 4K60 recordings on warm days.",
            "The Quik app is buggy and loses edits occasionally.",
        ],
    },
    "garmin": {
        "positive": [
            "GPS accuracy is exceptional — matches my running route precisely even in dense urban areas.",
            "Battery lasts 13+ days in smartwatch mode. I charge it on Sundays and forget about it.",
            "Training Load and Recovery analytics have genuinely improved how I structure my weeks.",
            "Built-in maps are detailed and reliable for trail navigation.",
            "HRV tracking overnight gives me actionable sleep insights every morning.",
        ],
        "mixed": [
            "Excellent fitness features but the smart notifications are basic compared to Apple Watch.",
            "GPS lock takes longer than expected in urban canyons.",
            "Training analytics are powerful but take weeks to calibrate to your fitness baseline.",
        ],
        "negative": [
            "Display isn't as sharp as competitors at this price point.",
            "Wrist-based HR is unreliable during high-intensity HIIT — spikes and drops frequently.",
        ],
    },
    "oura": {
        "positive": [
            "The sleep staging accuracy is the best I've seen from a wearable. My Oura data matches sleep studies closely.",
            "So unobtrusive I forget I'm wearing it. No irritation even after months of daily wear.",
            "Readiness score genuinely helps me decide when to push hard vs when to rest.",
            "HRV tracking trends over months revealed clear patterns with my stress and recovery.",
        ],
        "mixed": [
            "Excellent data but the subscription is a hard sell when competitors include the analytics for free.",
            "Readiness score is useful but can be overly conservative after just one bad night.",
            "The ring sizing process is essential — get it wrong and accuracy suffers.",
        ],
        "negative": [
            "Scratched easily despite the titanium finish. Shows wear after a few months.",
            "The gen 3 still lacks real-time heart rate display — you need the app.",
        ],
    },
    "playstation": {
        "positive": [
            "Load times in games like Spider-Man are under 2 seconds. The SSD makes last gen feel ancient.",
            "DualSense adaptive triggers add a layer of immersion I didn't know I was missing.",
            "Game library is excellent — both exclusive and third-party support is strong.",
            "Quiet during most games. Only gets loud during graphically intense sections.",
            "Remote Play to my phone or laptop works surprisingly well.",
        ],
        "mixed": [
            "Incredible console but the first-party game prices never drop and exclusives are slow to release.",
            "DualSense is innovative but the battery life is notably worse than PS4 controllers.",
            "Great performance but still larger than I'd like for my entertainment center.",
        ],
        "negative": [
            "PSN account required for even single-player offline games — feels excessive.",
            "UI organization is worse than PS4 in some ways. Game library browsing is clunky.",
        ],
    },
    "steam deck": {
        "positive": [
            "OLED display is gorgeous — deep blacks and vibrant colors make everything pop.",
            "My entire Steam library, playable anywhere. The game compatibility has improved dramatically.",
            "Battery life on the OLED model is a meaningful step up from the original.",
            "The built-in controls are ergonomically excellent for long sessions.",
            "SteamOS is polished and Proton compatibility works for 90%+ of my library.",
        ],
        "mixed": [
            "Excellent device but demanding games still run hot and battery drains quickly.",
            "Great for indie and older games. AAA titles sometimes need settings tweaking.",
            "The trackpads are useful once mastered but have a real learning curve.",
        ],
        "negative": [
            "Some anti-cheat systems still block games from running. Disappointing for online titles.",
            "Heavy for handheld use over 2+ hours. Wrist fatigue is real.",
        ],
    },
    "mouse": {
        "positive": [
            "The MagSpeed scroll wheel is legitimately the best I've ever used. Free-spin through long documents.",
            "Ergonomics are exceptional for an all-day productivity mouse.",
            "Logi Bolt receiver is rock-solid — no interference, no lag.",
            "Side buttons are perfectly placed and customizable to my workflow.",
            "Works flawlessly across three devices with instant switching.",
        ],
        "mixed": [
            "Great mouse but the software is heavier than it needs to be.",
            "Excellent ergonomics for right-hand use, but left-handed users need a different option.",
            "Good battery life but the right-click mechanism feels slightly mushy.",
        ],
        "negative": [
            "Double-click issues developed after 18 months of heavy use.",
            "Expensive for a productivity mouse. The scroll wheel is the only feature that justifies the premium.",
        ],
    },
    "nespresso": {
        "positive": [
            "Makes a genuinely great espresso in under 30 seconds. The crema is impressive for a pod machine.",
            "Vertuo pods produce a larger cup format that Nespresso Original couldn't.",
            "Compact, quiet, and simple. Perfect for office use.",
            "Milk frother included in the bundle is easy to use and cleans in seconds.",
        ],
        "mixed": [
            "Great coffee but the pod cost adds up quickly compared to beans.",
            "Good espresso but real enthusiasts will notice it's not as nuanced as ground coffee.",
            "The Vertuo ecosystem limits you to Nespresso pods only — no third-party options.",
        ],
        "negative": [
            "Machine stopped recognizing pods after 8 months. Had to contact support.",
            "Pod waste is a genuine environmental concern with this system.",
        ],
    },
    "ring": {
        "positive": [
            "Ring alarm integration is seamless. Motion detection has never triggered a false alarm.",
            "Video quality is sharp enough to identify faces at night with the spotlight on.",
            "Two-way talk is clear and works reliably even on slow WiFi.",
            "Installation was genuinely easy — done in 20 minutes with no electrician needed.",
        ],
        "mixed": [
            "Good security camera but the subscription for video history is almost mandatory.",
            "Motion zones work well but need fine-tuning to avoid neighbor sidewalk false alerts.",
        ],
        "negative": [
            "Had connection issues after a router upgrade. Support was helpful but the fix took hours.",
            "The subscription price has increased twice since I bought it. Frustrating.",
        ],
    },
}

# Generic fallback templates
GENERIC_REVIEWS = {
    "positive": [
        "Excellent product. Exceeded my expectations in every way.",
        "Solid build quality and the performance is exactly what was advertised.",
        "Would absolutely buy again. Highly recommended to anyone on the fence.",
        "Setup was straightforward and it has worked flawlessly since day one.",
        "Great value at this price point. Very happy with my purchase.",
    ],
    "mixed": [
        "Good product overall but a few minor issues keep it from being perfect.",
        "Does what it says but the quality control could be better.",
        "Happy with it mostly, just a few UX decisions I don't understand.",
        "Decent for the price but don't expect it to replace a more premium option.",
    ],
    "negative": [
        "Had high hopes but the quality doesn't match the price tag.",
        "Stopped working properly after just a few months of normal use.",
        "Customer support was unhelpful when I had an issue.",
        "Would not recommend based on my experience. Look at alternatives.",
    ],
}

def _get_templates(item: str) -> dict:
    item_lower = item.lower()
    for keyword, templates in REVIEW_TEMPLATES.items():
        if keyword in item_lower:
            return templates
    return GENERIC_REVIEWS


def random_date(days_back: int = 730) -> str:
    """Random datetime within the last `days_back` days."""
    offset = timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )
    dt = datetime.now(timezone.utc) - offset
    return dt.isoformat()


def generate_review(item: str, templates: dict, source: str) -> dict:
    sentiment = random.choices(
        ["positive", "positive", "positive", "mixed", "negative"],
        weights=[40, 30, 10, 15, 5],
    )[0]
    pool = templates.get(sentiment, GENERIC_REVIEWS[sentiment])
    text = random.choice(pool)

    rating = (
        random.uniform(4.0, 5.0) if sentiment == "positive" else
        random.uniform(2.5, 3.9) if sentiment == "mixed" else
        random.uniform(1.0, 2.4)
    )

    return {
        "id": generate_id(),
        "source": source,
        "text": text,
        "rating": round(rating, 1),
        "date": random_date(),
        "verified_purchase": random.choices([True, False], weights=[70, 30])[0],
        "helpful_votes": random.randint(0, 200),
        "reviewer_id": f"user_{generate_id()[:8]}",
        "fake_score": 0.0,
    }


def generate_reviews_for_item(item: str, n: int = 80) -> list:
    templates = _get_templates(item)
    # Distribute across sources
    source_weights = {"amazon": 40, "youtube": 35, "reddit": 15, "google": 10}
    sources = random.choices(
        list(source_weights.keys()),
        weights=list(source_weights.values()),
        k=n,
    )
    return [generate_review(item, templates, src) for src in sources]


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "items")
    os.makedirs(output_dir, exist_ok=True)

    for item in ITEMS:
        data = {
            "product_name": item,
            "image_url": None,  # Will be fetched live by Amazon scraper
            "reviews": generate_reviews_for_item(item, n=80),
        }
        filename = item.replace(" ", "_").replace("-", "_").lower() + ".json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Generated {filepath} ({len(data['reviews'])} reviews)")


if __name__ == "__main__":
    main()
