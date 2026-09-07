"""
Orchestrator-Workers Pattern for AI Trip Planner.
A central Orchestrator dynamically breaks down complex trip requirements
into discrete subtasks, dispatches them to specialized worker agents,
and synthesizes their individual deliverables into a unified TripItinerary.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from pydantic import BaseModel, Field

from trip_planner.schemas.models import (
    AccommodationOption,
    CostItem,
    DayPhoto,
    IntercityTransport,
    ItineraryDay,
    TripItinerary,
    clean_float,
)
from trip_planner.tools.city_media import get_day_photos


class TripSubtask(BaseModel):
    """Subtask created by the Orchestrator for a specialized worker."""
    task_type: str  # 'day_plan', 'stay', 'transit', 'checklist'
    target_city: str
    allocated_days: int = 1
    allocated_budget: float = 0.0
    context: dict[str, Any] = Field(default_factory=dict)


class TripPlanOutline(BaseModel):
    """High-level execution blueprint broken down by the Orchestrator."""
    destination_cities: list[str]
    origin_city: str
    total_days: int
    total_budget: float
    travelers: int
    city_allocations: list[TripSubtask] = Field(default_factory=list)


def _normalize_city_key(city: str) -> str:
    c = str(city).strip().lower()
    if "tiru" in c:
        return "tirupati"
    if "vijay" in c or "bezawada" in c:
        return "vijayawada"
    if "vizag" in c or "visakha" in c or "waltair" in c:
        return "visakhapatnam"
    if "nello" in c:
        return "nellore"
    if "rajah" in c or "rajm" in c or "rajamahendra" in c:
        return "rajahmundry"
    if "kurn" in c:
        return "kurnool"
    if "kakin" in c:
        return "kakinada"
    if "goa" in c:
        return "goa"
    if "hyder" in c or "hyd" in c:
        return "hyderabad"
    if "bengal" in c or "bangal" in c or "blr" in c:
        return "bengaluru"
    if "jaipur" in c:
        return "jaipur"
    if "udai" in c:
        return "udaipur"
    if "delhi" in c:
        return "delhi"
    if "agra" in c:
        return "agra"
    if "mumbai" in c or "bombay" in c:
        return "mumbai"
    if "chennai" in c or "madras" in c:
        return "chennai"
    return c


CITY_EXPERIENCES: dict[str, list[dict[str, Any]]] = {
    "tirupati": [
        {
            "theme": "Tirumala Balaji Darshan & Sacred Seven Hills",
            "morning": (
                "🏨 Stay Recommendation (Best for your budget): Check in around Tirupati Central Railway Station or RTC Bus Stand (e.g. Sri Sai Residency / Hotel Bliss, ₹1,200 - ₹2,200/night). This location is best for your budget as you can directly board official electric buses, saving ₹1,000+ on private cabs.\n\n"
                "🌅 06:00 AM - 11:30 AM (Tirumala Darshan & Sacred Hills): Start early at 06:00 AM to beat long queues. [Smart Budget Transit]: Take the official TTD AC Electric Bus from RTC Bus Stand to Tirumala hilltop (₹65/person) or shared APSRTC jeep instead of hiring a private cab (saves ₹1,200). For Darshan, if you booked the ₹300 Special Entry Darshan (SED) online, report at Vaikuntam Queue Complex-1; otherwise, collect the free Slotted Sarva Darshan (SSD) token at Vishnu Nivasam counter. After peaceful darshan of Lord Sri Venkateswara Swamy, collect your complimentary Tirupati Laddoo prasadam. Walk 10 mins to Silathoranam (natural 2.5-billion-year-old rock arch) and Chakra Theertham. For breakfast, visit Sri Lakshmi Narayana Bhavan near the temple car parking for hot Ghee Pudi Dosa & Filter Coffee (₹70-100)."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Authentic Andhra Feast & Heritage Museums): Take the return electric bus down the scenic Ghat Road back to Tirupati town. [Budget Lunch & Food Gem]: Head to Minerva Coffee Shop or Sri Venkateswara Bhavan on Renigunta Road. Order their authentic Rayalaseema Vegetarian Thali (₹180-240) served with steaming hot rice, ghee, pappu, and spicy gongura pachadi. At 02:30 PM, visit the ancient Sri Govindaraja Swamy Temple right beside the railway station (free entry), admiring its towering 50-meter 7-tier Raja Gopuram. Next, walk to the Sri Venkateswara Dhyana Vignan Mandiram (SV Museum, Entry ₹10) housing 1,000-year-old temple bronze sculptures, ancient stone inscriptions, and traditional musical instruments."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Sacred Waterfall, Bazaar Shopping & Dinner): Take a short auto-rickshaw (₹50) to Kapila Theertham at the foot of Tirumala Hills, where water cascades down a natural mountain gorge into a holy pushkarini. Attend the peaceful twilight Shiva Aarti as cool hill breezes set in. [Shopping & Budget Advice]: Walk down Gandhi Road and TK Street bazaars. Shop for authentic brass pooja lamps, red-sanders wood crafts, and sandalwood garlands—bargain respectfully, as prices here are 25-30% lower than hill-top souvenir stalls. [Dinner]: Finish with a light dinner of hot Rava Masala Dosa or Ghee Podi Idli at Hotel Mayura / Maurya Mess (₹120-150). Rest early to recharge for Day 2."
            ),
            "items": [
                ("Special Entry Darshan & TTD Electric Bus", 0.40),
                ("Minerva Traditional Thali & Breakfast", 0.30),
                ("SV Museum Entry & Pooja Offerings", 0.20),
                ("Local Auto & Station Commute", 0.10),
            ],
            "weather": "Pleasant and breezy on Tirumala hilltop (22°C - 27°C), sunny in Tirupati town.",
        },
        {
            "theme": "Chandragiri Fort, Sacred Padmavathi Temple & Waterfalls",
            "morning": (
                "🏨 Stay Recommendation: Continue stay at your hotel near RTC Central Hub to easily catch local buses and shared autos for out-of-town excursions.\n\n"
                "🌅 07:30 AM - 12:00 PM (Chandragiri Vijayanagara Fort): After morning idli-vada breakfast at your hotel (₹60), take a shared auto or APSRTC local bus (₹30, 25 mins) to historic Chandragiri Fort (14 km west of Tirupati). Built in the 11th century and later the fourth capital of the Vijayanagara Empire, this fort features the magnificent 3-storey Indo-Saracenic Raja Mahal and Rani Mahal palaces surrounded by lush green moat gardens. Entry ticket is only ₹25 (ASI). Climb the stone ramparts for sweeping 360-degree views of the countryside and explore the palace museum showcasing medieval weapons, coins, and royal artifacts."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Tiruchanur Padmavathi Temple & Rayalaseema Lunch): Return to Tirupati and stop at Andhra Spice or Sri Krishna Mess for a traditional spicy Andhra meals lunch (₹150) featuring hot sambar, rasam, and curd. At 02:30 PM, take an auto (₹60) to Sri Padmavathi Ammavari Temple at Tiruchanur (5 km south). By age-old pilgrimage tradition, visiting Goddess Padmavathi completes the sacred Tirupati pilgrimage. Opt for the ₹100 special darshan line to save 1-2 hours of waiting time. Walk around the tranquil Padma Sarovaram temple tank where golden lotus flowers bloom."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Regional Science Centre, Sunset Viewpoint & Sweet Delicacies): Visit the Regional Science Centre and Planetarium near Alipiri (Entry ₹40) or take a peaceful stroll through TTD Deer Park along the foot of the hills. [Evening Food Gem]: Stop by famous local sweet stalls near RTC Bus Stand for piping-hot fresh Jalebis and Tirupati Pala Kova (₹60-90). [Dinner & Next Destination Prep]: Enjoy dinner at Hotel Sindhu Rajasthan / Vrinda Veg (₹160), settle hotel bills, and prepare your travel bags for departure to Vijayawada / your next corridor hub in the morning."
            ),
            "items": [
                ("Chandragiri Fort & Museum Entry Ticket", 0.40),
                ("Padmavathi Ammavari Special Darshan Ticket", 0.30),
                ("Rayalaseema Meals Lunch & Evening Snacks", 0.20),
                ("Local Auto & Inter-Town Transit", 0.10),
            ],
            "weather": "Warm sunshine in the morning, breezy and pleasant near Chandragiri hills at sunset.",
        },
        {
            "theme": "Sri Kalahasti Vayu Lingam & Swarnamukhi River Valley",
            "morning": (
                "🌅 07:00 AM - 12:30 PM (Sri Kalahasti Temple & Rahu-Ketu Kshetra): Start at 07:00 AM by boarding an APSRTC express bus from Tirupati Central Bus Stand to Sri Kalahasti (36 km, ₹50, 50 mins). Sri Kalahasteeswara Temple is one of the five sacred Pancha Bhoota Sthalams representing the Element of Air (Vayu Lingam). Marvel at the towering 100-foot entrance gopuram and the ancient monolithic temple architecture on the banks of River Swarnamukhi. Special entry darshan is ₹50-₹200. Observe the unique eternal lamp inside the sanctum sanctorum flickering without any breeze—a divine manifestation of the Vayu element."
            ),
            "afternoon": (
                "☀️ 01:00 PM - 04:30 PM (Riverfront Dining & Kalamkari Artistry): Dine at Sri Vani Mess or Hotel Saravana near the temple for traditional banana-leaf South Indian thali (₹140). Afterward, visit the local Kalamkari textile craft units in Sri Kalahasti, where master artisans hand-paint intricate mythological epics onto cotton fabrics using natural vegetable dyes and bamboo pens. You can purchase authentic hand-painted dupattas and wall tapestries directly from artisan families at half the showroom price."
            ),
            "evening": (
                "🌆 05:00 PM - 09:00 PM (Sunset over Swarnamukhi & Return Transit): Take a peaceful sunset walk along the Swarnamukhi riverbank bridge, watching temple gopurams reflect in the water. Catch an express bus back to Tirupati (₹50). Conclude with light dinner at your transit hub, ready for your onwards journey."
            ),
            "items": [
                ("Sri Kalahasti Special Entry & Temple Offerings", 0.40),
                ("Traditional Banana Leaf Lunch & Refreshments", 0.30),
                ("Kalamkari Artisan Craft Centre Visit", 0.20),
                ("APSRTC Express Bus Return Tickets", 0.10),
            ],
            "weather": "Sunny and clear with cooling riverbank breeze in the evening.",
        },
    ],
    "vijayawada": [
        {
            "theme": "Indrakeeladri Hill, Kanaka Durga Temple & Krishna Riverfront",
            "morning": (
                "🏨 Stay Recommendation (Best for your budget): Check in at Hotel Manorama or Quality Hotel D V Manor along MG Road / Governor Peta (₹1,500 - ₹3,000/night). Highly accessible to both railway station and temple ghats, saving cab commute expenses.\n\n"
                "🌅 06:30 AM - 11:30 AM (Indrakeeladri Kanaka Durga Darshan): Head early to Indrakeeladri Hill. [Budget Transit]: Take a local auto (₹40) or city bus to the hill base. Take the scenic Kanaka Durga Ghat Road walk or the hillside ropeway/lift (₹20). The temple dedicated to Goddess Kanaka Durga overlooks the mighty River Krishna. Book ₹100 or ₹300 Antralaya Darshan line to bypass 2-hour general rush. After receiving temple blessings and delicious Puliora prasadam, take in the breathtaking panoramic view of the Krishna river splitting across the delta."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Legendary Babai Hotel Lunch & Prakasam Barrage Walk): Walk down to Governor Peta for lunch at the historic Babai Hotel (established in 1942). Feast on their legendary Ghee Idli, melting Butter Dosa, and authentic Andhra Meals with podi and fresh homemade butter (₹120-180/person). At 02:30 PM, take a scenic walk across the 1.2 km long Prakasam Barrage. Constructed across the Krishna River with 70 majestic gates, it connects Vijayawada to Guntur and offers cool riverside views and breeze."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Bhavani Island River Cruise & Night Street Eats): Take an auto (₹60) to Berm Park boat jetty and board an AP Tourism motorboat (₹120 return) to Bhavani Island—a 133-acre river island on the Krishna River. Enjoy nature walks among giant trees, mirror maze, or zip-lining. Watch the sun dip into the river while sipping fresh coconut water. [Night Street Food]: Return to Besant Road night market to savor Vijayawada's famous spicy Punugulu served with peanut and ginger chutney, Mirchi Bajji, and fresh Badam Milk (₹60-100). Dine at Minerva Grand / Sarovar Veg and retire for the night."
            ),
            "items": [
                ("Kanaka Durga Special Darshan & Ropeway", 0.40),
                ("Babai Hotel Ghee Idli Feast & Lunch", 0.30),
                ("Bhavani Island Boat Cruise & Island Entry", 0.20),
                ("Riverfront Auto Rickshaw Commute", 0.10),
            ],
            "weather": "Warm and tropical daytime (31°C), refreshing and breezy by the Krishna river in evening.",
        },
        {
            "theme": "4th-Century Undavalli Caves & Kondapalli Heritage",
            "morning": (
                "🌅 07:30 AM - 12:00 PM (Sandstone Undavalli Caves): After breakfast at your hotel, hire an auto or cab (₹120, 20 mins) across the river to Undavalli Caves. Carved in the 4th-5th century out of solid sandstone rock faces, this 4-storey monolith is an architectural marvel of Buddhist and Hindu rock-cut art. On the second floor, gaze at the colossal 5-meter long reclining statue of Lord Vishnu (Anantasayana Padmanabha) sculpted from a single granite boulder. Entry ticket is only ₹25 (ASI). Climb to the upper terrace for panoramic green vista of the Krishna riverbank."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Famous Ulavacharu Biryani & Bapu Museum): Return to MG Road for lunch at Cross Roads Restaurant or Sweet Magic. Try Vijayawada's iconic Ulavacharu Veg/Chicken Biryani (rice slow-cooked in thick horse-gram soup with rich spices, ₹200-260). Afterward, visit the renovated Bapu Museum (Victoria Jubilee Regional Museum, Entry ₹50), showcasing ancient Buddhist limestone statues, medieval weaponry, and 1,500-year-old Jain bronze icons."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Gandhi Hill Sunset & Kondapalli Toy Bazaars): Visit Gandhi Hill memorial park atop the central hill (toy train & planetarium, ₹30). View the 52-foot Gandhi Stupa and enjoy sweeping sunset views over the entire illuminated railway junction and city. [Shopping]: Visit Lepakshi Handicrafts on MG Road to buy authentic Kondapalli wooden toys (Ambari elephant, Dashavataram set, rocking dolls) made from light Poniki wood by local artisan clusters. Dinner at Silver Spoon / RR Durbar (₹180), then rest."
            ),
            "items": [
                ("Undavalli Caves ASI Entry & Guide", 0.40),
                ("Authentic Ulavacharu Biryani & Refreshments", 0.30),
                ("Bapu Museum & Gandhi Hill Tickets", 0.20),
                ("Local Auto Rickshaw Transit", 0.10),
            ],
            "weather": "Sunny conditions in morning, best to explore rock caves early before midday heat.",
        },
    ],
    "visakhapatnam": [
        {
            "theme": "Beach Road Promenade, INS Kursura Submarine & Kailasagiri",
            "morning": (
                "🏨 Stay Recommendation (Best for your budget): Check in at Hotel Supreme / Keys Lite near Ramakrishna Beach (₹1,800 - ₹3,200/night). Walking distance to the ocean promenade, submarine museum, and morning beach jogging tracks.\n\n"
                "🌅 06:30 AM - 11:30 AM (RK Beach & Naval Museums): Start with a morning walk along the golden sands of RK Beach. At 09:00 AM, step inside the iconic INS Kursura Submarine Museum (Entry ₹40)—the actual Soviet-built submarine that served in the 1971 Indo-Pak war, now mounted right on the sands. Retired naval officers guide you through the torpedo room and periscope control deck. Right across the road, visit the TU-142M Aircraft Museum (Entry ₹70), walking inside an immense maritime reconnaissance anti-submarine warplane."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Coastal Andhra Seafood / Thali & Matsyadarshini): Walk 5 mins to Sea Inn (Raju Gari Dhaba) or Daspalla Executive Court. Feast on spicy Andhra Fish Curry, Prawn Fry, Crab Masala, or authentic coastal vegetarian thali served with hot rice and rasam (₹200-280). Visit Matsyadarshini Aquarium (Entry ₹30) showcasing exotic marine life from the Bay of Bengal, then head to VUDA Park for shady tree promenades."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Kailasagiri Hilltop Ropeway & Panoramic Sunset): Take an auto (₹60) to Kailasagiri hill base. Hop onto the scenic aerial cable car ropeway (₹110 return) gliding over the hills. From the summit 360 feet above sea level, take in the jaw-dropping panoramic view of the crescent coastline, Bay of Bengal, and city skyline. Stand beside the towering 40-foot white statues of Lord Shiva and Parvathi. Ride the circular toy train around the hill edge at golden hour. Dine at the hilltop garden restaurant (₹200) with cool ocean sea breezes."
            ),
            "items": [
                ("INS Kursura Submarine & TU-142 Entry", 0.40),
                ("Raju Gari Coastal Seafood / Andhra Thali", 0.30),
                ("Kailasagiri Ropeway & Toy Train Ticket", 0.20),
                ("Beach Road Auto & App Cab Commute", 0.10),
            ],
            "weather": "Warm coastal maritime climate with refreshing sea breezes throughout the afternoon.",
        },
        {
            "theme": "Rushikonda Beach Watersports & Ancient Simhachalam Hill",
            "morning": (
                "🌅 07:30 AM - 12:30 PM (Rushikonda Beach Watersports & Tenneti Park): Drive along the stunning coastal Marine Drive to Rushikonda Beach (8 km north). Known for its clean waters and curved bay, it is Andhra's premier beach. Enjoy speedboating (₹350), sea-kayaking, or relax under thatched beach umbrellas with fresh coconut water (₹40). On the way back, stop at Tenneti Park cliffside, viewing the dramatic rock shoreline and the famous stranded cargo ship viewpoint."
            ),
            "afternoon": (
                "☀️ 01:00 PM - 04:30 PM (Bamboo Chicken Feast & Simhachalam Temple): Savor authentic Araku-style Bamboo Chicken / Cashew Pulao at a beachside cafe or Sai Priya resort (₹220-300). At 03:00 PM, take a cab/auto inland to ancient Sri Varaha Lakshmi Narasimha Swamy Temple atop Simhachalam hill. Built in Kalinga and Chola architectural styles, the deity remains permanently covered in thick sandalwood paste (Chandanotsavam). Special darshan ticket is ₹100 to save time."
            ),
            "evening": (
                "🌆 05:30 PM - 09:30 PM (Dolphin's Nose Lighthouse & Jagadamba Bazaars): Head to Dolphin's Nose cliff and lighthouse (Entry ₹20) for a spectacular sunset view of the Vizag natural harbor. Return to Jagadamba Centre for shopping authentic Madugula Halwa, Uppada silks, and handmade horn toys. Enjoy dinner at Dolphin Hotel / Ming Garden (₹250), then rest."
            ),
            "items": [
                ("Rushikonda Beach Watersports & Umbrella", 0.40),
                ("Beachside Dining & Bamboo Chicken Feast", 0.30),
                ("Simhachalam Hill Transit & Darshan Ticket", 0.20),
                ("Coastal Highway Cab Transit", 0.10),
            ],
            "weather": "Sunny beach conditions with pleasant evening temple breeze on Simhachalam hill.",
        },
    ],
    "nellore": [
        {
            "theme": "Sri Talpagiri Ranganatha Temple & Pennar Riverbank",
            "morning": (
                "🏨 Stay Recommendation: Check in at Hotel Minerva Grand / Pavani Residency near Trunk Road (₹1,400 - ₹2,600/night). Centrally located for local transit and dining.\n\n"
                "🌅 07:00 AM - 11:30 AM (Sri Ranganathaswamy Temple): Start your morning by visiting the magnificent Sri Talpagiri Ranganathaswamy Temple on the banks of River Pennar. Over 600 years old, it boasts a towering 29-meter 7-tier Raja Gopuram with intricate stucco sculptures. Enter the sanctum to witness the 12-foot reclining deity of Lord Ranganatha upon the coiled serpent Adisesha. Take a peaceful morning walk along the Pennar river ghats, listening to temple bells."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (World-Famous Nellore Chepala Pulusu Feast): Head to Komala Vilas or Murali Krishna Hotel on Trunk Road. Order the legendary Nellore Chepala Pulusu (tangy and spicy Korameenu fish curry cooked in earthen pots with raw mango and country spices) served with hot steamed rice (₹180-240), or authentic Gongura vegetarian thali. Stop at a local sweet shop to savor Nellore's signature Malai Khaja (crispy flaky pastry filled with sweetened cream, ₹50-80)."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Historic Barah Shaheed Dargah & Bazaars): Visit the revered Barah Shaheed Dargah on the tranquil shores of Swarnala Cheruvu lake, celebrated during the annual Rottela Panduga festival. Stroll along Trunk Road market to browse local handloom lungis and sarees, then enjoy light dinner at Mayuri Veg (₹130)."
            ),
            "items": [
                ("Temple Archana & Pennar River Boat", 0.40),
                ("Famous Nellore Pulusu & Thali Lunch", 0.30),
                ("Barah Shaheed Dargah & Malai Khaja", 0.20),
                ("Local Auto Rickshaw Commute", 0.10),
            ],
            "weather": "Warm daytime (30°C) with pleasant breezes along the Pennar riverfront in evening.",
        },
        {
            "theme": "Mypadu Beach Shorelines & Nelapattu Bird Sanctuary",
            "morning": (
                "🌅 07:00 AM - 12:00 PM (Mypadu Beach Promenade): Hire a private cab or board a direct bus (22 km east, ₹30) to tranquil Mypadu Beach on the Bay of Bengal. Walk barefoot along soft golden sands fringed with whispering casuarina groves. The shallow waters here are safe for morning wading and beach relaxation."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Coastal Seafood & Sri Chengalamma Temple): Enjoy fresh sea crab or prawn fry with rice at a local beachfront eatery (₹200). In the afternoon, travel to Sullurpeta to visit the famous Sri Chengalamma Parameswari Temple, where the Goddess protects the coastal delta."
            ),
            "evening": (
                "🌆 05:00 PM - 08:30 PM (Nelapattu Bird Sanctuary Sunset): Visit Nelapattu Sanctuary (Entry ₹20), watching thousands of migratory grey pelicans, open-billed storks, and flamingos nesting on lake trees at sunset. Return to Nellore for dinner and overnight rest."
            ),
            "items": [
                ("Mypadu Beach Umbrella & Entry", 0.40),
                ("Coastal Seafood & Andhra Thali", 0.30),
                ("Nelapattu Sanctuary Entry & Guide", 0.20),
                ("Excursion Private Cab Transit", 0.10),
            ],
            "weather": "Cool sea breeze at the coast, warm sunshine inland.",
        },
    ],
    "rajahmundry": [
        {
            "theme": "Sacred Godavari River, Pushkar Ghats & Kotilingeshwara Temple",
            "morning": (
                "🏨 Stay Recommendation: Check in at Hotel River Bay / Shelton Comfort along Godavari embankment (₹1,500 - ₹3,000/night). Riverfront views and quick access to boat cruises.\n\n"
                "🌅 06:30 AM - 11:30 AM (Godavari Holy Dip & River Temples): Start with an early morning visit to Pushkar Ghat on the holy Godavari River. Take a sacred morning dip and board a morning country boat ride on the expansive river (₹60). Visit the ancient Kotilingeshwara Temple nearby, where legend says Lord Indra installed ten million Shiva lingams to cleanse his sins."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Godavari Pulasa Fish & Iconic Rose Milk): Savor an authentic Godavari lunch at Sri Kanya or Hotel Shelton. Try the seasonal Godavari Pulasa fish curry or traditional Andhra Veg Thali with fresh Godavari gongura (₹180-260). Walk to Kotipalli Bus Stand to taste the legendary Kotipalli Rose Milk (established in 1950)—creamy, chilled, and subtly flavored (₹40). Afterward, visit the Sir Arthur Cotton Barrage Museum at Dowleswaram (Entry ₹20)."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Godavari Arch Bridge Sunset & Pootharekulu Shopping): Walk along the riverfront promenade watching sunset colors reflect off the historic Godavari Fourth Arch Bridge. [Shopping]: Visit specialized sweet stalls on Main Road to purchase authentic Atreyapuram Pootharekulu (paper-thin sweet rice-wafer rolls stuffed with jaggery, ghee, and dry fruits, ₹150-250/box). Dine at River Bay restaurant and relax."
            ),
            "items": [
                ("Godavari River Boat Ride & Ghat Tour", 0.40),
                ("Godavari Meals & Famous Rose Milk", 0.30),
                ("Kotilingeshwara Temple & Pootharekulu", 0.20),
                ("Local Auto Rickshaw Commute", 0.10),
            ],
            "weather": "Pleasant tropical riverside climate with refreshing evening river breezes.",
        },
        {
            "theme": "Papikondalu River Gorges & Kadiyam Flower Nurseries",
            "morning": (
                "🌅 07:00 AM - 01:00 PM (Breathtaking Papikondalu Boat Cruise): Board an early morning AP Tourism luxury cruise from Purushothapatnam / Polavaram. Cruise deep into the scenic Papi Hills (Papikondalu) gorge where the Godavari River narrows between towering green mountain peaks. The tranquil scenery, tribal songs, and morning mist over the water make this an unforgettable adventure."
            ),
            "afternoon": (
                "☀️ 01:00 PM - 04:30 PM (Riverside Cruise Buffet & Tribal Culture): Enjoy hot Andhra vegetarian and chicken buffet lunch served on board the cruise ship. Disembark briefly at Kolluru bamboo huts or Perantapalli ashram to learn about local riparian tribal lifestyle and buy bamboo handicrafts."
            ),
            "evening": (
                "🌆 05:00 PM - 08:30 PM (Kadiyam Flower Nurseries): On your return, stop by Kadiyam village—Asia's largest flower nursery hub with thousands of acres of exotic orchids, bonsai, and flowering plants. Stroll the green gardens before returning to Rajahmundry for dinner."
            ),
            "items": [
                ("Papikondalu Scenic Boat Cruise Ticket", 0.40),
                ("River Cruise Buffet Lunch & Refreshments", 0.30),
                ("Kadiyam Nurseries Tour & Souvenirs", 0.20),
                ("Harbor Cab & Local Commute", 0.10),
            ],
            "weather": "Misty and cool on the river gorge in morning, warm afternoon in nurseries.",
        },
    ],
    "kurnool": [
        {
            "theme": "Historic Konda Reddy Buruju Fort & Tomb of Abdul Wahab",
            "morning": (
                "🏨 Stay Recommendation: Check in at Hotel DVR Mansion / Hotel Maurya Inn near Old Bus Stand (₹1,200 - ₹2,400/night). Best budget location with direct auto connections.\n\n"
                "🌅 07:30 AM - 11:30 AM (Konda Reddy Buruju Fort): Visit the historic Konda Reddy Buruju fortress in the heart of Kurnool town. Famous in Deccan history and Telugu cinema, this imposing stone bastion features observation towers and underground tunnels built by the Vijayanagara kings. Climb to the top for a panoramic view of Kurnool town and the Handri River. Entry is free."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Kurnool Uggani Bajji Lunch & Royal Tombs): Stop at a local heritage eatery for Kurnool's famous dish: Uggani (seasoned puffed rice with lemon, onions, and roasted gram powder) served with piping-hot Mirchi Bajji (₹60-80). Follow it with a full Rayalaseema ragi mudda lunch (₹120). At 02:30 PM, visit the Tomb of Abdul Wahab (Gol Gumbaz) on the riverbank, featuring 17th-century Adil Shahi domes and peaceful gardens."
            ),
            "evening": (
                "🌆 05:00 PM - 09:00 PM (Orvakal Rock Garden Sunset): Drive 20 km to Orvakal Rock Garden (Entry ₹20), a dramatic geological canyon of natural silica and quartz rock formations surrounding a tranquil lake. Hike the stone pathway up to the sunset pavilion. [Sweets]: On returning, buy authentic Kurnool Pala Kova sweets from legacy sweet shops. Dine at Maurya Inn and rest."
            ),
            "items": [
                ("Konda Reddy Buruju Fort & Guide", 0.40),
                ("Kurnool Uggani Bajji & Andhra Meals", 0.30),
                ("Orvakal Rock Garden Entry & Pala Kova", 0.20),
                ("City Auto Rickshaw Transit", 0.10),
            ],
            "weather": "Warm and dry climate, best to complete the fort climb early morning.",
        },
        {
            "theme": "Subterranean Belum Caves & Sacred Yaganti Nandi",
            "morning": (
                "🌅 07:00 AM - 12:30 PM (Belum Caves Underground Caverns): Take a private cab or express bus south to Belum Caves (105 km, 2 hrs, Entry ₹60). India's second-largest cave system, these subterranean limestone caverns plunge 150 feet underground with 3.5 km of mapped passages. Walk beneath surreal stalactites, the musical chamber, and the deep 'Patalaganga' perennial stream illuminated with soft LED lighting."
            ),
            "afternoon": (
                "☀️ 01:00 PM - 04:30 PM (Yaganti Uma Maheswara Temple & Growing Nandi): Travel to ancient Sri Yaganti Temple nestled among scenic canyon cliffs. Marvel at the famous monolithic Nandi stone bull which has been physically expanding over the centuries according to the Archaeological Survey of India. Drink the sweet mineral water flowing from the natural perennial spring (Pushkarini)."
            ),
            "evening": (
                "🌆 05:00 PM - 08:30 PM (Scenic Highway Return): Enjoy tea and snacks near Banaganapalle before returning to Kurnool. Savor an authentic dinner and rest."
            ),
            "items": [
                ("Belum Caves Entry & Guided Tunnel Tour", 0.40),
                ("Yaganti Pilgrimage Lunch & Fresh Snacks", 0.30),
                ("Cave Exploration Permits & Refreshments", 0.20),
                ("Day Excursion Private Cab", 0.10),
            ],
            "weather": "Cool inside the deep caves (24°C), sunny in the surrounding hills.",
        },
    ],
    "kakinada": [
        {
            "theme": "Coringa Mangrove Safari, Hope Island & Kakinada Kaja",
            "morning": (
                "🏨 Stay Recommendation: Check in at Hotel SVN Grand or Royal Park near Bhanugudi Junction (₹1,400 - ₹2,800/night). Close to bus hub and coastal roads.\n\n"
                "🌅 07:00 AM - 11:30 AM (Coringa Mangrove Wildlife Safari): Take an auto (14 km south, ₹150) to Coringa Wildlife Sanctuary—India's second-largest mangrove forest ecosystem where the Godavari river meets the Bay of Bengal. Board a forest eco-boat cruise (₹120) winding through dense mangrove creeks, spotting golden jackals, smooth-coated otters, and rare migratory shorebirds. Walk across the 4 km wooden canopy boardwalk over the tidal swamp."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Hope Island Picnic & Kakinada Beach Promenade): Take a motorized boat across the bay to Hope Island, a tranquil natural sand spit protecting Kakinada bay. Enjoy a picnic lunch by the calm shoreline. Return to Kakinada town and visit the vibrant beach promenade, enjoying views of deep-sea cargo ships docked in the port."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Kotaiah Gottam Kaja & Street Feasts): Stroll through Main Road to visit the legendary Kotaiah Sweets (established in 1891) to taste and pack the world-famous Kakinada Gottam Kaja (cylindrical pastry crisp on the outside and bursting with sweet syrup inside, ₹120/box). Savor hot Onion Pakoda and Mirchi Bajji on the beach road, followed by dinner at Royal Park restaurant."
            ),
            "items": [
                ("Coringa Mangrove Safari & Boat Entry", 0.40),
                ("Coastal Island Picnic Lunch & Drinks", 0.30),
                ("Beach Promenade & Famous Kotaiah Kaja", 0.20),
                ("Coastal Cab & Boat Transfer", 0.10),
            ],
            "weather": "Warm and breezy coastal maritime climate with refreshing sea breezes.",
        },
        {
            "theme": "Draksharamam Bheemeswara Temple & Subbaiah Gari Butta Bhojanam",
            "morning": (
                "🌅 07:30 AM - 12:00 PM (Ancient Draksharamam Temple): Take an express bus or auto (28 km, ₹30) to Draksharamam, known as the 'Dakshina Kasi' and one of the sacred Pancharama Kshetras. The monumental 9th-century temple built by Eastern Chalukyan King Bhima features a colossal 14-foot black crystal Shiva Lingam that spans two storeys. Admire the two-storeyed stone circumambulatory verandas and sacred Sapta Godavari pushkarini."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Subbaiah Gari Legendary Butta Bhojanam): Return to Kakinada to experience the original Subbaiah Gari Hotel. Partake in the legendary 'Butta Bhojanam' (a lavish 32-item traditional feast served on fresh banana leaves from woven bamboo baskets), featuring hot rice, homemade ghee, Majjiga Pulusu, Guttivankaya curry, and sweet Purnam Burelu (₹200/person)."
            ),
            "evening": (
                "🌆 05:00 PM - 09:00 PM (Uppada Handloom Silk Trail & Sunset): Drive 16 km north along the coast to Uppada village. Watch master weavers weave world-renowned lightweight Uppada Jamdani silk sarees on wooden pit-looms. Catch a dramatic sunset over Uppada Beach before dinner."
            ),
            "items": [
                ("Draksharamam Temple Archana & Guide", 0.40),
                ("Subbaiah Gari Authentic Butta Bhojanam", 0.30),
                ("Uppada Silk Weaver Studio Tour", 0.20),
                ("Inter-Town Cab Commute", 0.10),
            ],
            "weather": "Sunny morning in temple corridors with breezy sunset along Uppada beach.",
        },
    ],
    "goa": [
        {
            "theme": "Historic Fort Aguada & North Goa Coastal Vibe",
            "morning": (
                "🏨 Stay Recommendation: Check in around Candolim / Calangute (e.g. Zostel Goa / Whispering Palms, ₹1,500 - ₹3,500/night). Near beach access and two-wheeler rental hubs.\n\n"
                "🌅 08:00 AM - 12:00 PM (Fort Aguada & Lighthouse): Rent a scooter (₹350/day) or hire a taxi. Ride to 17th-century Portuguese Fort Aguada overlooking the Arabian Sea. Tour the upper fort citadel, deep freshwater cistern, and the four-storey lighthouse with panoramic ocean views. Entry is ₹25."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Calangute & Baga Beach Shacks): Head to Calangute beach for lunch at a shaded beach shack (Britto's / Souza Lobo). Savor authentic Goan Fish Curry Thali, Prawn Balchão, or Veg Xacuti with hot poi bread (₹250-350). Relax on beach sunbeds under palm trees."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Chapora Fort Sunset & Anjuna Flea Market): Ride up to Chapora Fort for the most famous sunset view over Vagator beach. End the evening enjoying live acoustic music and dinner at Curlies or Shiva Valley at Anjuna beach."
            ),
            "items": [
                ("Fort Aguada Entry & Scooter Rental", 0.40),
                ("Goan Fish Curry Thali & Kokum Drink", 0.30),
                ("Chapora Fort Sunset & Beach Shack Cafe", 0.20),
                ("Two-Wheeler Fuel & Beach Commute", 0.10),
            ],
            "weather": "Sunny tropical beach weather (29°C) with balmy sea breezes.",
        },
        {
            "theme": "UNESCO Heritage Old Goa & Latin Quarter Fontainhas",
            "morning": (
                "🌅 08:30 AM - 12:30 PM (Old Goa Cathedrals): Ride to Old Goa (10 km east of Panaji) to explore UNESCO World Heritage monuments: the Basilica of Bom Jesus (holding the sacred mortal remains of St. Francis Xavier) and the colossal Se Cathedral with its Golden Bell. Entry is free."
            ),
            "afternoon": (
                "☀️ 01:00 PM - 04:30 PM (Fontainhas Heritage Walk & Portuguese Dining): Head to Panaji's Latin Quarter (Fontainhas). Walk among pastel-colored Portuguese villas, terracotta-tiled roofs, and wrought-iron balconies. Dine at Viva Panjim or Confeitaria 31 De Janeiro for authentic Pork/Mushroom Vindaloo and warm Bebinca dessert (₹220-320)."
            ),
            "evening": (
                "🌆 05:30 PM - 09:30 PM (Mandovi River Sunset Cruise): Board an evening cruise on the Mandovi River (₹400, 1 hr) featuring traditional Goan folk dances (Dekhni & Fugdi). Shop for feni and cashew nuts at Panaji Municipal Market before dinner."
            ),
            "items": [
                ("Old Goa Museum & Cathedral Guide", 0.40),
                ("Fontainhas Heritage Lunch & Bebinca", 0.30),
                ("Mandovi River Sunset Cruise Ticket", 0.20),
                ("Panaji City Auto / Cab Fare", 0.10),
            ],
            "weather": "Pleasant and warm, great for walking heritage trails in Fontainhas.",
        },
    ],
    "jaipur": [
        {
            "theme": "Royal Amber Fort, Jal Mahal & Pink City Palaces",
            "morning": (
                "🏨 Stay Recommendation: Check in at Hotel Pearl Palace / Shahpura House in Bani Park (₹1,500 - ₹3,500/night). Central, safe, and close to both railway station and Old City gates.\n\n"
                "🌅 07:30 AM - 12:00 PM (Majestic Amber Fort): Take an auto/cab (11 km, ₹150) to Amber Fort. Tour the mirror-inlaid Sheesh Mahal, Diwan-e-Aam, and scenic Maota Lake. Entry is ₹100 (Indian) / composite ticket. Walk the high stone ramparts for sweeping views of the Aravalli hills."
            ),
            "afternoon": (
                "☀️ 12:30 PM - 04:30 PM (Jal Mahal Photo-Stop & Dal Baati Churma Feast): Stop to photograph the water-floating palace Jal Mahal in Man Sagar Lake. Head to heritage eatery 1135 AD or LMB in Johari Bazaar for a royal Rajasthani Dal Baati Churma feast with spicy Gatte ki Sabzi and Ker Sangri (₹220-300). Tour the City Palace and adjacent Jantar Mantar observatory (Entry ₹50)."
            ),
            "evening": (
                "🌆 05:00 PM - 09:30 PM (Hawa Mahal & Johari Bazaar Shopping): Admire the illuminated facade of Hawa Mahal (Palace of Winds). Browse Johari Bazaar and Bapu Bazaar for Jaipur blue pottery, bandhani dupattas, and handcrafted juttis. Taste famous sweet Ghevar at LMB sweet shop before dinner."
            ),
            "items": [
                ("Amber Fort Entry & Palace Guide", 0.40),
                ("Rajasthani Dal Baati Churma Feast", 0.30),
                ("City Palace & Jantar Mantar Ticket", 0.20),
                ("City Auto / Cab Transit", 0.10),
            ],
            "weather": "Warm and sunny with crisp pleasant evenings across the Pink City.",
        },
    ],
}

GENERIC_DAY_TEMPLATES: list[dict[str, Any]] = [
    {
        "theme_suffix": "Heritage Landmarks & Historical Quarter",
        "morning": "Embark on a guided morning walking tour of {city}'s prime historical quarter, visiting signature heritage landmarks, iconic monuments, and revered cultural centers.",
        "afternoon": "Indulge in authentic regional delicacies and traditional home-style thali at a popular local heritage dining mess, followed by exploring municipal art galleries and museums.",
        "evening": "Stroll through the vibrant central town plaza and artisan bazaar, picking up handcrafted local souvenirs before settling in for a relaxing regional dinner.",
        "items": [
            ("Monument & Heritage Entry Passes", 0.40),
            ("Authentic Regional Thali & Beverages", 0.30),
            ("Museum & Cultural Centre Ticket", 0.20),
            ("Local Auto Rickshaw / Cab Transit", 0.10),
        ],
        "weather": "Sunny and clear, pleasant for walking through historic city avenues.",
    },
    {
        "theme_suffix": "Nature Trails, Lakes & Waterfront Promenades",
        "morning": "Begin early with a serene morning promenade along {city}'s prominent waterfront / public botanical gardens, observing local birdlife and peaceful sunrise vistas.",
        "afternoon": "Enjoy a fresh farm-to-table lunch at a lakeside or garden cafe, followed by a scenic boat ride or short nature trail exploring geological formations nearby.",
        "evening": "Head to a popular sunset viewpoint overlooking the city valley, sipping freshly brewed local tea while sampling hot regional street snacks.",
        "items": [
            ("Waterfront Boat Cruise / Park Entry", 0.40),
            ("Lakeside Dining & Fresh Coconut Water", 0.30),
            ("Nature Trail & Viewpoint Observatory", 0.20),
            ("Local Commute & Return Cab", 0.10),
        ],
        "weather": "Refreshing morning breeze with warm, clear afternoon sunshine.",
    },
    {
        "theme_suffix": "Arts, Crafts & Culinary Food Walks",
        "morning": "Explore vibrant craft clusters and artisan workshops in {city}, witnessing master craftsmen create traditional handlooms, pottery, and regional metal crafts.",
        "afternoon": "Embark on a culinary food walk through the old town alleyways, tasting famous legacy snacks, hot spice-infused street dishes, and traditional desserts.",
        "evening": "Attend a live cultural music or dance performance at a civic auditorium, followed by a peaceful dinner at a rooftop restaurant under the stars.",
        "items": [
            ("Artisan Workshop Tour & Craft Experience", 0.40),
            ("Old Town Culinary Food Walk & Lunch", 0.30),
            ("Cultural Event / Auditorium Entry", 0.20),
            ("City Auto Transit & Evening Cab", 0.10),
        ],
        "weather": "Pleasant conditions throughout the day, ideal for open-air cultural discovery.",
    },
    {
        "theme_suffix": "Scenic Excursions & Panoramic Hilltops",
        "morning": "Take a scenic half-day excursion to the highest vantage point / ancient hill sanctuary near {city}, taking in sprawling panoramic countryside views.",
        "afternoon": "Enjoy a hearty country-style lunch at a rustic highway dhaba, learning about regional agricultural traditions and visiting fruit orchards.",
        "evening": "Return to the city center for relaxed twilight shopping along premier commercial boulevards, concluding with a memorable festive dinner.",
        "items": [
            ("Hill Sanctuary & Viewpoint Permit", 0.40),
            ("Highway Dhaba Feast & Refreshments", 0.30),
            ("Orchard Visit & Local Farm Produce", 0.20),
            ("Excursion Cab Hire & Fuel", 0.10),
        ],
        "weather": "Breezy and cooler on the higher elevations, pleasant evening return.",
    },
]

CITY_STAYS: dict[str, dict[str, tuple[str, str]]] = {
    "tirupati": {
        "budget": ("Sri Sai Residency", "Near Tirupati Central Railway Station, Tirupati"),
        "comfort": ("Hotel Bliss / Minerva Grand", "Ramanuja Circle, Renigunta Road, Tirupati"),
        "luxury": ("Fortune Select Grand Ridge / Marasa Sarovar Premiere", "Shilparamam Theme Park Road, Tirupati"),
    },
    "vijayawada": {
        "budget": ("Hotel Manorama", "Old Bus Stand Road, Governor Peta, Vijayawada"),
        "comfort": ("Quality Hotel D V Manor", "M.G. Road, Labbipet, Vijayawada"),
        "luxury": ("Novotel Vijayawada Varun / The Gateway Hotel", "Bharathi Nagar / M.G. Road, Vijayawada"),
    },
    "visakhapatnam": {
        "budget": ("Hotel Supreme / Keys Lite", "Beach Road, Ramakrishna Beach, Visakhapatnam"),
        "comfort": ("Dolphin Hotel / Green Park", "Daba Gardens / Waltair Uplands, Visakhapatnam"),
        "luxury": ("Novotel Varun Beach / The Park", "Beach Road, Visakhapatnam"),
    },
    "nellore": {
        "budget": ("Hotel Pavani Residency", "Trunk Road, Near Railway Station, Nellore"),
        "comfort": ("Hotel Minerva Grand / D R Utthama", "Grand Trunk Road, Pogathota, Nellore"),
        "luxury": ("The Grand D G / Seasons Healthcare Resort", "Mini Bypass Road, Nellore"),
    },
    "rajahmundry": {
        "budget": ("Hotel Shelton Comfort", "Near Kotipalli Bus Stand, Rajahmundry"),
        "comfort": ("Anand Regalia / Hotel River Bay", "River Godavari Front, Gowthami Ghat, Rajahmundry"),
        "luxury": ("River Bay Resort / Grand Palace", "Godavari River Embankment, Rajahmundry"),
    },
    "kurnool": {
        "budget": ("Hotel DVR Mansion", "Station Road, Near Railway Hub, Kurnool"),
        "comfort": ("Hotel Maurya Inn", "Bhagya Nagar, Opp APSRTC Bus Station, Kurnool"),
        "luxury": ("Triguna Clarks Inn / The Mourya", "Bellary Road, Kurnool"),
    },
    "kakinada": {
        "budget": ("Hotel SVN Grand", "Cinema Road, Surya Rao Peta, Kakinada"),
        "comfort": ("Royal Park / Grand Kakinada by GRT", "Near Bhanugudi Junction, Kakinada"),
        "luxury": ("Paradigm Sarovar Portico", "Subhash Road, Kakinada"),
    },
    "goa": {
        "budget": ("Zostel Goa / Backpacker Panda", "Calangute / Anjuna Beach, Goa"),
        "comfort": ("Lemon Tree Amarante / Whispering Palms", "Candolim Beach, North Goa"),
        "luxury": ("Taj Holiday Village / Goa Marriott Resort", "Sinquerim / Miramar Beach, Goa"),
    },
    "jaipur": {
        "budget": ("Zostel Jaipur / Hotel Pearl Palace", "Ajmer Road, Hathroi Fort, Jaipur"),
        "comfort": ("Hotel Jaipur Central Residency / Shahpura House", "Bani Park, Sansar Chandra Road, Jaipur"),
        "luxury": ("Rambagh Palace / ITC Rajputana", "Bhawani Singh Road / Station Road, Jaipur"),
    },
}


class DayPlanWorker:
    """Worker responsible for planning unique morning, afternoon, evening activities and realistic cost breakdowns."""

    def plan_day(
        self,
        day_num: int,
        city: str,
        budget_for_day: float,
        theme: str = "Sightseeing",
        context: dict[str, Any] | None = None,
    ) -> ItineraryDay:
        c_norm = _normalize_city_key(city)

        if c_norm in CITY_EXPERIENCES and len(CITY_EXPERIENCES[c_norm]) > 0:
            exp_list = CITY_EXPERIENCES[c_norm]
            exp = exp_list[(day_num - 1) % len(exp_list)]
            day_theme = exp["theme"]
            morning = exp["morning"]
            afternoon = exp["afternoon"]
            evening = exp["evening"]
            weather_note = exp["weather"]
            items_spec = exp["items"]
        else:
            tmpl = GENERIC_DAY_TEMPLATES[(day_num - 1) % len(GENERIC_DAY_TEMPLATES)]
            day_theme = f"{city} {tmpl['theme_suffix']}"
            morning = tmpl["morning"].format(city=city)
            afternoon = tmpl["afternoon"].format(city=city)
            evening = tmpl["evening"].format(city=city)
            weather_note = tmpl["weather"].format(city=city)
            items_spec = tmpl["items"]

        # Build exactly 4 distinct itemized cost breakdown lines summing to estimated_cost
        breakdown = []
        for item_name, frac in items_spec:
            breakdown.append(CostItem(item=item_name, amount=round(budget_for_day * frac, 2)))

        day_photos = get_day_photos(city, day_num)

        return ItineraryDay(
            day_number=day_num,
            city=city,
            theme=day_theme,
            morning=morning,
            afternoon=afternoon,
            evening=evening,
            estimated_cost=round(budget_for_day, 2),
            cost_breakdown=breakdown,
            weather_note=weather_note,
            photos=[DayPhoto(**p) for p in day_photos] if day_photos else None,
        )


class StayWorker:
    """Worker responsible for selecting accommodations matching destination and budget."""

    def select_stay(self, city: str, night_budget: float, travelers: int = 1) -> AccommodationOption:
        tier_key = "budget" if night_budget < 1500 else ("comfort" if night_budget < 4000 else "luxury")
        tier_label = "Budget" if tier_key == "budget" else ("Comfort / Mid-range" if tier_key == "comfort" else "Luxury")
        c_norm = _normalize_city_key(city)

        if c_norm in CITY_STAYS and tier_key in CITY_STAYS[c_norm]:
            hotel_name, address = CITY_STAYS[c_norm][tier_key]
        else:
            hotel_name = f"Hotel {city} Residency"
            address = f"Central Town, near Transit Hub, {city}"

        return AccommodationOption(
            name=hotel_name,
            city=city,
            category=f"{tier_label} Hotel",
            address_or_area=address,
            estimated_price_per_night=round(night_budget, 2),
            why_recommended=f"Centrally located, highly rated {tier_label.lower()} accommodation curated for easy transit and sightseeing in {city}.",
        )


class TransitWorker:
    """Worker responsible for intercity transit and sequential connection routing."""

    def plan_transit(self, origin: str, cities: list[str], total_transit_budget: float) -> IntercityTransport:
        if len(cities) <= 1:
            dest = cities[0] if cities else origin
            return IntercityTransport(
                mode="Express Train / Flight",
                recommended_option=f"Direct Express Transit ({origin} to {dest})",
                estimated_cost_per_person=round(total_transit_budget, 2),
                travel_duration="3 - 6 hrs",
                why_recommended=f"Convenient and direct connection from departure hub {origin} to {dest}.",
                local_connect_tips="Prepaid cabs and autos readily available outside the transit terminal.",
                route_legs=[],
            )

        # Multi-leg transit
        legs: list[dict[str, Any]] = []
        all_stops = [origin] + cities
        leg_cost = round(total_transit_budget / max(1, len(all_stops) - 1), 2)

        for i in range(len(all_stops) - 1):
            f_city = all_stops[i]
            t_city = all_stops[i + 1]
            legs.append(
                {
                    "from_city": f_city,
                    "to_city": t_city,
                    "mode": "Express Train / Volvo Bus",
                    "recommended_option": f"Intercity Express ({f_city} ➔ {t_city})",
                    "estimated_cost_per_person": leg_cost,
                    "travel_duration": "3 - 4 hrs",
                    "why_recommended": f"Optimal sequential corridor link between {f_city} and {t_city}.",
                    "local_connect_tips": "Station-front auto stands and local taxi services.",
                }
            )

        return IntercityTransport(
            mode="Multi-Leg Rail / Road Transit",
            recommended_option=f"Multi-City Corridor ({' ➔ '.join(all_stops)})",
            estimated_cost_per_person=round(total_transit_budget, 2),
            travel_duration="Sequential Corridor",
            why_recommended="Sequential route minimizing travel fatigue and backtracking.",
            local_connect_tips="Local connectivity at every stop.",
            route_legs=legs,
        )


class TripOrchestrator:
    """
    Central Orchestrator breaking down trip goals, delegating to specialized workers,
    and synthesizing results into a unified TripItinerary.
    """

    def __init__(
        self,
        day_worker: DayPlanWorker | None = None,
        stay_worker: StayWorker | None = None,
        transit_worker: TransitWorker | None = None,
    ):
        self.day_worker = day_worker or DayPlanWorker()
        self.stay_worker = stay_worker or StayWorker()
        self.transit_worker = transit_worker or TransitWorker()

    def breakdown_trip(self, inputs: dict[str, Any]) -> TripPlanOutline:
        """
        Analyzes high-level parameters and creates a structured execution blueprint.
        """
        origin = str(inputs.get("origin", "Origin")).strip()
        cities_raw = str(inputs.get("cities", inputs.get("destination_city", "Vijayawada"))).strip()
        city_list = [c.strip() for c in cities_raw.split(",") if c.strip()]
        if not city_list:
            city_list = ["Vijayawada"]
        elif len(city_list) > 1 and origin.lower() != city_list[0].lower():
            from trip_planner.api.app import optimize_city_route
            city_list = optimize_city_route(origin, city_list)

        total_days = max(1, int(inputs.get("trip_length", inputs.get("days", 3))))
        total_budget = clean_float(inputs.get("budget", 25000.0), 25000.0)
        travelers = max(1, int(inputs.get("travelers", 1)))

        allocations: list[TripSubtask] = []
        num_cities = len(city_list)

        if num_cities <= total_days:
            base_days = total_days // num_cities
            rem_days = total_days % num_cities
            for idx, city in enumerate(city_list):
                d_count = base_days + (1 if idx < rem_days else 0)
                city_budget = (total_budget / total_days) * d_count
                allocations.append(
                    TripSubtask(
                        task_type="city_bundle",
                        target_city=city,
                        allocated_days=d_count,
                        allocated_budget=city_budget,
                        context={"origin": origin, "travelers": travelers, "interests": str(inputs.get("interests", ""))},
                    )
                )
        else:
            # More cities requested than total days (e.g. 7 cities for a 5-day trip)
            # Select the top total_days sequential corridor stops so total days is exactly total_days!
            active_cities = city_list[:total_days]
            city_budget = total_budget / total_days
            for city in active_cities:
                allocations.append(
                    TripSubtask(
                        task_type="city_bundle",
                        target_city=city,
                        allocated_days=1,
                        allocated_budget=city_budget,
                        context={"origin": origin, "travelers": travelers, "interests": str(inputs.get("interests", ""))},
                    )
                )

        return TripPlanOutline(
            destination_cities=city_list,
            origin_city=origin,
            total_days=total_days,
            total_budget=total_budget,
            travelers=travelers,
            city_allocations=allocations,
        )

    @classmethod
    def should_use_orchestrator(cls, inputs: dict[str, Any]) -> bool:
        """
        Determines whether the Orchestrator-Workers pattern should execute.
        Only multi-city trips use this pattern; single-city trips bypass it completely.
        """
        cities_raw = str(inputs.get("cities", "")).strip()
        city_list = [c.strip() for c in cities_raw.split(",") if c.strip()]
        is_multi = bool(inputs.get("multi_city"))
        return len(city_list) > 1 or (is_multi and len(city_list) > 1)

    def _plan_city_worker(self, subtask: TripSubtask, daily_budget: float) -> dict[str, Any]:
        """
        Concurrent worker planning that city's portion (days, activities, costs, and stay).
        """
        city_days: list[ItineraryDay] = []
        for i in range(subtask.allocated_days):
            day = self.day_worker.plan_day(
                day_num=i + 1,
                city=subtask.target_city,
                budget_for_day=daily_budget,
                context=subtask.context,
            )
            city_days.append(day)

        stay = self.stay_worker.select_stay(
            city=subtask.target_city,
            night_budget=daily_budget * 0.40,
            travelers=subtask.context.get("travelers", 1),
        )

        return {
            "city": subtask.target_city,
            "days": city_days,
            "stay": stay,
        }

    def orchestrate_itinerary(self, inputs: dict[str, Any]) -> TripItinerary:
        """
        Orchestrates full trip generation:
        1. Orchestrator breaks down trip into per-city day/budget allocations and transit links.
        2. Workers execute concurrently in parallel worker threads (one per city).
        3. Synthesizer merges the city plans into a coherent whole-trip itinerary.
        """
        blueprint = self.breakdown_trip(inputs)
        # Carve out transit budget first so daily activities + stays + transit strictly <= total_budget
        transit_budget = round(blueprint.total_budget * 0.12, 2)
        stay_and_day_budget = max(500.0, blueprint.total_budget - transit_budget)
        daily_budget = round(stay_and_day_budget / max(1, blueprint.total_days), 2)

        # 1. Dispatch worker agents concurrently (one per city) via ThreadPoolExecutor
        city_results: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(blueprint.city_allocations))) as executor:
            future_to_city = {
                executor.submit(self._plan_city_worker, subtask, daily_budget): subtask.target_city
                for subtask in blueprint.city_allocations
            }
            for fut in as_completed(future_to_city):
                city_name = future_to_city[fut]
                city_results[city_name] = fut.result()

        # 2. Synthesizer merges the city plans preserving chronological city sequence
        all_days: list[ItineraryDay] = []
        stays: list[AccommodationOption] = []
        day_counter = 1

        for subtask in blueprint.city_allocations:
            c_name = subtask.target_city
            worker_data = city_results.get(c_name)
            if not worker_data:
                continue

            for day_item in worker_data["days"]:
                # Renumber day consecutively for the synthesized whole-trip schedule
                day_item.day_number = day_counter
                all_days.append(day_item)
                day_counter += 1

            if worker_data.get("stay"):
                stays.append(worker_data["stay"])

        # Strictly enforce total days limit
        if len(all_days) > blueprint.total_days:
            all_days = all_days[:blueprint.total_days]

        # 3. Dispatch TransitWorker to synthesize sequential transit links
        transit = self.transit_worker.plan_transit(
            origin=blueprint.origin_city,
            cities=blueprint.destination_cities,
            total_transit_budget=transit_budget,
        )

        # 4. Synthesize final whole-trip TripItinerary
        primary_city = blueprint.destination_cities[0]
        cities_visited = blueprint.destination_cities if len(blueprint.destination_cities) > 1 else None
        calculated_cost = round(sum(d.estimated_cost for d in all_days) + transit.estimated_cost_per_person, 2)
        final_total_cost = min(blueprint.total_budget, calculated_cost)

        itinerary = TripItinerary(
            destination_city=primary_city,
            origin_city=blueprint.origin_city,
            cities_visited=cities_visited,
            destination_country="India",
            trip_length_days=blueprint.total_days,
            currency=str(inputs.get("currency", "INR")),
            travelers=blueprint.travelers,
            total_estimated_cost=final_total_cost,
            days=all_days,
            packing_suggestions=[
                "Comfortable walking shoes",
                "Weather-appropriate clothing",
                "Government ID & tickets",
                "Power bank & multi-city transit passes",
            ],
            intercity_transport=transit,
            recommended_stay=stays[0] if stays else None,
            recommended_stays=stays if len(stays) > 1 else None,
            orchestrator_used=True,
        )

        try:
            from trip_planner.patterns.evaluator_optimizer import EvaluatorOptimizer
            eval_opt = EvaluatorOptimizer(max_passes=2)
            refined, _, _ = eval_opt.run_optimization_loop(
                itinerary,
                target_budget=blueprint.total_budget,
                default_origin=blueprint.origin_city,
            )
            return refined
        except Exception:
            return itinerary

