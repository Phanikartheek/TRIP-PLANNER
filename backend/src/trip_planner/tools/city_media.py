"""
City Media & Visual Showcase Registry.
Provides curated, high-quality images and "Why Famous & Why Visit" tourist narratives
for attractions, budget hotels, and iconic food spots across destinations.
"""
from typing import Any


CITY_MEDIA_DATABASE: dict[str, list[dict[str, Any]]] = {
    "tirupati": [
        # Day 1
        {
            "photos": [
                {
                    "title": "Sri Venkateswara Swamy Temple (Tirumala)",
                    "category": "🏛️ Famous Sacred Shrine",
                    "url": "https://images.unsplash.com/photo-1609766857041-ed402ea8069a?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "The world-renowned Kaliyuga Vaikuntha atop the sacred Seven Hills. Famous for its magnificent gold-plated Ananda Nilayam vimana tower and divine darshan attended by millions.",
                },
                {
                    "title": "Silathoranam Natural Rock Arch",
                    "category": "🪨 2.5-Billion-Year Wonder",
                    "url": "https://images.unsplash.com/photo-1544717305-2782549b5136?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "One of only three natural geological rock arches in the entire world. Formed 2.5 billion years ago in the Precambrian Eon, located beside holy Chakra Theertham.",
                },
                {
                    "title": "Sri Sai Residency / Hotel Bliss (Best Budget Stay)",
                    "category": "🏨 Budget Stay Recommendation",
                    "url": "https://images.unsplash.com/photo-1590490360182-c33d57733427?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Best for your budget (₹1,200-₹2,200/night) right next to Tirupati Central Railway Station and RTC Bus Stand. Lets you board official TTD electric buses directly, saving ₹1,200+ on private taxis.",
                },
                {
                    "title": "Tirupati Laddoo Prasadam & Ghee Podi Dosa",
                    "category": "🍽️ Iconic Culinary Specialty",
                    "url": "https://images.unsplash.com/photo-1668236543090-82eba5ee5976?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "The legendary GI-tagged Tirupati Laddoo prepared with pure country cow ghee, cashews, raisins, and cardamom. Savor crispy melting Ghee Pudi Dosa at Sri Lakshmi Narayana Bhavan.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Tirupati is India's preeminent spiritual capital, home to Lord Venkateswara atop the sacred Seshachalam hills and prehistoric natural rock wonders.",
            },
        },
        # Day 2
        {
            "photos": [
                {
                    "title": "Chandragiri Fort & Raja Mahal",
                    "category": "🏰 11th-Century Vijayanagara Fort",
                    "url": "https://images.unsplash.com/photo-1599661046289-e31897846e41?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Historic 11th-century capital citadel of the Vijayanagara Empire. Famous for the intact 3-storey Indo-Saracenic Raja Mahal, stone ramparts, and tranquil moat gardens.",
                },
                {
                    "title": "Sri Padmavathi Ammavari Temple (Tiruchanur)",
                    "category": "🛕 Sacred Lotus Goddess Temple",
                    "url": "https://images.unsplash.com/photo-1582510003544-4d00b7f74220?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Dedicated to Goddess Padmavathi incarnated on a golden lotus in Padma Sarovaram. By ancient belief, your Tirupati pilgrimage is only auspiciously complete after visiting this shrine.",
                },
                {
                    "title": "Kapila Theertham Waterfalls & Shiva Kshetra",
                    "category": "🌊 Sacred Gorge Waterfall",
                    "url": "https://images.unsplash.com/photo-1432405972618-c60b0225b8f9?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "The only Shiva temple situated in Tirupati, where a natural mountain river cascades down a deep granite canyon into the temple pushkarini.",
                },
                {
                    "title": "Authentic Rayalaseema Thali (Andhra Spice)",
                    "category": "🍽️ Famous Regional Food Gem",
                    "url": "https://images.unsplash.com/photo-1626777552726-4a6b54c97e46?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Spicy banana-leaf meal served with steaming Sona Masoori rice, fresh Gongura pachadi, country dal with ghee, and Tirupati milk Pala Kova.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Chandragiri Fort and Tiruchanur offer profound historical insights into South India's royal dynasties paired with spiritual fulfillment.",
            },
        },
    ],
    "vijayawada": [
        # Day 1
        {
            "photos": [
                {
                    "title": "Sri Durga Malleswara Swamy Varla Devasthanam",
                    "category": "🛕 Indrakeeladri Hilltop Shrine",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Kanaka_Durga_Temple_Ghat_Road.jpg/800px-Kanaka_Durga_Temple_Ghat_Road.jpg",
                    "why_famous": "Swayambhu abode of Goddess Kanaka Durga towering atop Indrakeeladri hill on the banks of River Krishna. Famous for Navaratri celebrations and breathtaking river vistas.",
                },
                {
                    "title": "Prakasam Barrage & Bhavani Island",
                    "category": "🌉 Krishna River Landmark",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/52/Prakasam_Barrage_at_Dusk.jpg/800px-Prakasam_Barrage_at_Dusk.jpg",
                    "why_famous": "A 1.2-km historic barrage with 70 gates across the Krishna River, leading to Bhavani Island—one of India's largest natural river islands with boating cruises.",
                },
                {
                    "title": "Hotel Manorama / Quality Hotel D V Manor",
                    "category": "🏨 Central Budget Stay",
                    "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Best budget accommodation on MG Road, Governor Peta. Direct walking and auto access to ghats and station, eliminating expensive commute fees.",
                },
                {
                    "title": "Babai Hotel Legendary Ghee Idli & Butter Dosa",
                    "category": "🍽️ Heritage Breakfast Legend (Est. 1942)",
                    "url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Patronized by Telugu cultural legends since 1942. Known for pillowy soft idlis topped with a dollop of white homemade butter and fragrant podi.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Vijayawada is Andhra Pradesh's vibrant commercial heart, where River Krishna meets sacred hill ranges and culinary heritage.",
            },
        },
        # Day 2
        {
            "photos": [
                {
                    "title": "Undavalli 4-Storey Sandstone Caves",
                    "category": "🏛️ 4th-Century Rock-Cut Wonder",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Undavalli_Caves_Vijayawada.jpg/800px-Undavalli_Caves_Vijayawada.jpg",
                    "why_famous": "A monolithic 4-storey rock-cut cave system carved in the 4th-5th century, featuring a colossal 5-meter reclining statue of Lord Vishnu sculpted from a single granite rock face.",
                },
                {
                    "title": "Bapu Museum (Victoria Jubilee)",
                    "category": "🏺 Archaeological Treasure",
                    "url": "https://images.unsplash.com/photo-1518998053901-5348d3961a04?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Renovated heritage museum showcasing 1,500-year-old Buddhist sculptures, Jain icons, medieval weapons, and Telugu numismatic artifacts.",
                },
                {
                    "title": "Authentic Vijayawada Ulavacharu Biryani",
                    "category": "🍽️ Famous Andhra Cuisine",
                    "url": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Iconic regional biryani cooked with slow-simmered horse gram broth (Ulavacharu), fragrant aged basmati rice, and spices.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Undavalli Caves are a masterpiece of ancient Indian rock architecture showcasing harmony between early Buddhist and Hindu cave artisans.",
            },
        },
    ],
    "visakhapatnam": [
        # Day 1
        {
            "photos": [
                {
                    "title": "INS Kursura Submarine Museum (RK Beach)",
                    "category": "🚢 Historic War Submarine",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/INS_Kursura_%28S20%29_at_RK_Beach.jpg/800px-INS_Kursura_%28S20%29_at_RK_Beach.jpg",
                    "why_famous": "A real Soviet-built submarine that served in the 1971 Indo-Pak war, mounted right on the sand. The only submarine museum of its kind in South Asia.",
                },
                {
                    "title": "Kailasagiri Hilltop & Ropeway",
                    "category": "🚠 Coastal Panoramic Vantage",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d7/Kailasagiri_Shiva_Parvathi_Statue.jpg/800px-Kailasagiri_Shiva_Parvathi_Statue.jpg",
                    "why_famous": "Scenic hill 360 feet above sea level with aerial cable car ropeway, towering 40-foot white statues of Lord Shiva and Parvathi, and sweeping ocean views.",
                },
                {
                    "title": "Hotel Supreme / Keys Lite (Beach Road)",
                    "category": "🏨 Beachfront Budget Stay",
                    "url": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Facing the Bay of Bengal along Beach Road. Step right onto RK Beach promenade without paying for morning transit.",
                },
                {
                    "title": "Raju Gari Coastal Andhra Seafood & Meals",
                    "category": "🍽️ Famous Coastal Delicacy",
                    "url": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Celebrated for fresh Bay of Bengal fish curry (Chepala Pulusu), spiced Royyala (prawn) fry, and authentic coastal Andhra rice meals.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Vizag is the 'Jewel of the East Coast', where dramatic green Eastern Ghats meet the golden sands of the Bay of Bengal.",
            },
        },
        # Day 2
        {
            "photos": [
                {
                    "title": "Rushikonda Beach & Coastal Marine Drive",
                    "category": "🏖️ Blue Flag Certified Beach",
                    "url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Andhra's premier beach known for clean turquoise waters, water sports, and dramatic curved hill-facing coastline.",
                },
                {
                    "title": "Sri Varaha Lakshmi Narasimha Swamy (Simhachalam)",
                    "category": "🛕 11th-Century Sandalwood Shrine",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/73/Simhachalam_Temple_Gopuram.jpg/800px-Simhachalam_Temple_Gopuram.jpg",
                    "why_famous": "Ancient hill shrine in Kalinga and Chola architecture where the presiding deity remains permanently cloaked in sacred sandalwood paste.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Rushikonda Beach and Simhachalam hill offer the ultimate balance of coastal adventure and sacred heritage.",
            },
        },
    ],
    "nellore": [
        {
            "photos": [
                {
                    "title": "Sri Talpagiri Ranganathaswamy Temple",
                    "category": "🛕 600-Year-Old Riverfront Shrine",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Ranganayakulapeta_temple_Nellore.jpg/800px-Ranganayakulapeta_temple_Nellore.jpg",
                    "why_famous": "Magnificent ancient shrine on the banks of River Pennar boasting a 29-meter 7-tier Raja Gopuram and a colossal 12-foot reclining deity on Adisesha.",
                },
                {
                    "title": "Mypadu Beach & Casuarina Coastline",
                    "category": "🏖️ Pristine Golden Coast",
                    "url": "https://images.unsplash.com/photo-1519046904884-53103b34b206?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Tranquil, uncrowded golden beach along the Bay of Bengal lined with lush green casuarina groves, perfect for sunrise wading.",
                },
                {
                    "title": "Hotel Pavani Residency / Minerva Grand",
                    "category": "🏨 Central Transit Stay",
                    "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Located on Grand Trunk Road near Nellore Railway Station; best value hotel with direct connectivity to buses and famous eateries.",
                },
                {
                    "title": "World-Famous Nellore Chepala Pulusu & Malai Khaja",
                    "category": "🍽️ Legendary Andhra Specialty",
                    "url": "https://images.unsplash.com/photo-1589302168068-964664d93dc0?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Famous across India for tangy, spicy Korameenu fish curry cooked in earthen pots with raw mango. Don't miss crispy sweet Malai Khaja.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Nellore is synonymous with rich agrarian deltas, ancient river kshetras, and the finest seafood traditions in South India.",
            },
        },
    ],
    "rajahmundry": [
        {
            "photos": [
                {
                    "title": "Godavari Fourth Arch Bridge & Pushkar Ghat",
                    "category": "🌉 Sacred Riverfront & Bridge",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Godavari_Arch_Bridge.jpg/800px-Godavari_Arch_Bridge.jpg",
                    "why_famous": "Asia's second-longest bridge over water, spanning the sacred Godavari River where millions assemble for Pushkarams.",
                },
                {
                    "title": "Papikondalu Godavari River Gorge",
                    "category": "🌄 Breathtaking Canyon Cruise",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Papi_hills.jpg/800px-Papi_hills.jpg",
                    "why_famous": "Spectacular river gorge where the majestic Godavari narrows between soaring, mist-shrouded green hills of the Eastern Ghats.",
                },
                {
                    "title": "Hotel Shelton Comfort / River Bay",
                    "category": "🏨 Riverfront Budget Stay",
                    "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Positioned right near Kotipalli Bus Stand and Godavari river embankment, saving transit time for early morning boat tours.",
                },
                {
                    "title": "Atreyapuram Pootharekulu & Kotipalli Rose Milk",
                    "category": "🍽️ World-Famous GI Sweet",
                    "url": "https://images.unsplash.com/photo-1505253758473-96b7015fcd40?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Paper-thin sweet rice-starch wafers folded with pure ghee, jaggery, and dry fruits. Chilled Kotipalli Rose Milk has been a local icon since 1950.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Rajahmundry is the cultural capital of Andhra Pradesh and the birthplace of the Telugu language poet Adikavi Nannaya.",
            },
        },
    ],
    "kurnool": [
        {
            "photos": [
                {
                    "title": "Konda Reddy Buruju Fort Bastion",
                    "category": "🏰 Historic Vijayanagara Bastion",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Konda_Reddy_Buruju_Kurnool.jpg/800px-Konda_Reddy_Buruju_Kurnool.jpg",
                    "why_famous": "The historic stone bastion and fortress in the heart of Kurnool town, celebrated in Deccan history and Telugu cinema.",
                },
                {
                    "title": "Belum Caves & Subterranean Patalaganga",
                    "category": "🕳️ Second-Largest Indian Cave System",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Belum_Caves_passage.jpg/800px-Belum_Caves_passage.jpg",
                    "why_famous": "Underground limestone caves plunging 150 feet below ground with 3.5 km of passages, surreal stalactites, and musical limestone chambers.",
                },
                {
                    "title": "Hotel DVR Mansion / Maurya Inn",
                    "category": "🏨 Central Station Stay",
                    "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Budget hotel right across from the main transport hub; best base for coordinating Belum Caves and Yaganti excursions.",
                },
                {
                    "title": "Kurnool Uggani Bajji & Pala Kova",
                    "category": "🍽️ Authentic Rayalaseema Flavor",
                    "url": "https://images.unsplash.com/photo-1601050690597-df0568f70950?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "The definitive breakfast of Rayalaseema: seasoned puffed rice tossed with lemon, roasted gram, and onion, served with piping hot Mirchi Bajji.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Kurnool was Andhra State's first capital, blending ancient Vijayanagara fortresses with jaw-dropping geological cave wonders.",
            },
        },
    ],
    "kakinada": [
        {
            "photos": [
                {
                    "title": "Coringa Mangrove Wildlife Sanctuary",
                    "category": "🌿 Second-Largest Mangrove Ecosystem",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Coringa_Wildlife_Sanctuary_Mangroves.jpg/800px-Coringa_Wildlife_Sanctuary_Mangroves.jpg",
                    "why_famous": "India's second-largest mangrove forest with a 4 km canopy wooden boardwalk, boat safaris through tidal creeks, and rare fishing cats.",
                },
                {
                    "title": "Draksharamam Bheemeswara Swamy Temple",
                    "category": "🛕 Dakshina Kasi Pancharama",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Draksharamam_Temple.jpg/800px-Draksharamam_Temple.jpg",
                    "why_famous": "Monumental 9th-century Eastern Chalukyan temple with a colossal 14-foot black crystal Shiva Lingam that spans two storeys.",
                },
                {
                    "title": "Hotel SVN Grand / Royal Park",
                    "category": "🏨 Prime Town Stay",
                    "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Close to Bhanugudi Junction with easy connectivity to the bus terminal, beach road, and heritage sweet shops.",
                },
                {
                    "title": "Subbaiah Gari Butta Bhojanam & Kotaiah Kaja",
                    "category": "🍽️ Legendary 32-Item Feast",
                    "url": "https://images.unsplash.com/photo-1610057099443-fde8c4d50f91?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "The original home of 'Butta Bhojanam'—a lavish feast served from woven bamboo baskets, capped with world-famous syrup-filled Kotaiah Kaja.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Kakinada is a tranquil coastal port town celebrated for rich biodiversity, sacred Pancharama shrines, and legendary sweets.",
            },
        },
    ],
    "goa": [
        {
            "photos": [
                {
                    "title": "Fort Aguada & Calangute Beach",
                    "category": "🏰 17th-Century Portuguese Citadel",
                    "url": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Overlooking the Arabian Sea with a 4-storey lighthouse and vast freshwater cisterns built by the Portuguese in 1612.",
                },
                {
                    "title": "Zostel Goa / Lemon Tree Candolim",
                    "category": "🏨 Beach Proximity Stay",
                    "url": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Best budget accommodation near Candolim beach; easily rent scooters to explore both North and South Goa effortlessly.",
                },
                {
                    "title": "Authentic Goan Fish Curry Thali & Bebinca",
                    "category": "🍽️ Coastal Culinary Icon",
                    "url": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Coconut and kokum-infused spicy fish curry with poi bread, followed by traditional multi-layered Bebinca dessert.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Goa blends centuries of Portuguese-Latin culture with pristine tropical coastlines and vibrant beach life.",
            },
        },
    ],
    "gokarna": [
        {
            "photos": [
                {
                    "title": "Om Beach & Half Moon Beach Trek",
                    "category": "🏖️ Naturally Shaped Om Coastline",
                    "url": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Coastline naturally shaped like the sacred Hindu symbol 'Om'. Renowned for cliff hikes connecting Om Beach, Half Moon Beach, and Paradise Beach.",
                },
                {
                    "title": "Sri Mahabaleshwar Swamy Temple (Atmalinga)",
                    "category": "🛕 Ancient 4th-Century Shrine",
                    "url": "https://images.unsplash.com/photo-1544717305-2782549b5136?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Sacred classical Dravidian temple housing the Pranalinga / Atmalinga of Lord Shiva brought by Ravana, worshipped as Dakshina Kashi.",
                },
                {
                    "title": "Zostel Gokarna / Namaste Cafe",
                    "category": "🏨 Budget Cliffside Stay",
                    "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Perched on Om Beach cliffs with sea-facing dorms and budget cottages, letting you step directly onto beach hiking trails.",
                },
                {
                    "title": "Coastal Karavali Seafood Thali & Neer Dosa",
                    "category": "🍽️ Famous Coastal Karnataka Delicacy",
                    "url": "https://images.unsplash.com/photo-1610057099443-fde8c4d50f91?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Delicate lace-thin Neer Dosas with freshly ground coconut chutney, followed by spiced Konkan fish curry and chilled Kokum juice.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Gokarna is the perfect soulful alternative to bustling party beaches, combining cliff trails with ancient Atmalinga spirituality.",
            },
        },
    ],
    "munnar": [
        {
            "photos": [
                {
                    "title": "Tata Tea Museum & Mattupetty Dam Reservoir",
                    "category": "🍵 Emerald Tea Plantations",
                    "url": "https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Sprawling rolling hills of emerald green tea carpet at 1,600m altitude. Famous for speedboat cruises on Mattupetty Dam and Echo Point.",
                },
                {
                    "title": "Eravikulam National Park (Nilgiri Tahr Sanctuary)",
                    "category": "🦌 High-Altitude Wildlife Sanctuary",
                    "url": "https://images.unsplash.com/photo-1519046904884-53103b34b206?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Home to the endangered Nilgiri Tahr mountain ibex, Neelakurinji flowers that bloom once every 12 years, and Anamudi Peak (South India's highest point).",
                },
                {
                    "title": "Munnar Misty Valley / Hill View Cottages",
                    "category": "🏨 Mountain Budget Resort",
                    "url": "https://images.unsplash.com/photo-1520250497591-112f2f40a3f4?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Scenic budget stay amidst cardamom and tea estates; walking distance to Munnar town bus terminal.",
                },
                {
                    "title": "Kerala Banana Leaf Sadhya & Spiced Elaichi Chai",
                    "category": "🍽️ Traditional Malabar Feast",
                    "url": "https://images.unsplash.com/photo-1589301760014-d929f3979dbc?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Steaming red Kerala Matta rice served with Avial, Sambar, crispy banana chips, and piping hot mountain-grown cardamom tea.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Munnar offers cool mountain air, endless undulating tea estates, and misty Western Ghats viewpoints.",
            },
        },
    ],
    "hyderabad": [
        {
            "photos": [
                {
                    "title": "Charminar & Laad Bazaar (Old City)",
                    "category": "🏛️ 1591 Qutb Shahi Monument",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/71/Charminar_Hyderabad_1.jpg/800px-Charminar_Hyderabad_1.jpg",
                    "why_famous": "The 430-year-old architectural emblem of Hyderabad featuring four 56-meter grand minarets, surrounded by century-old pearl and lacquer bangle bazaars.",
                },
                {
                    "title": "Golconda Fort & Sound-and-Light Spectacle",
                    "category": "🏰 13th-Century Acoustic Fortress",
                    "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Golconda_Fort_Hyderabad.jpg/800px-Golconda_Fort_Hyderabad.jpg",
                    "why_famous": "Impregnable fortress renowned for miraculous acoustic clapping echoes heard 1 km away at the summit pavilion, and origin of the legendary Koh-i-Noor diamond.",
                },
                {
                    "title": "Hotel Central Court / Taj Tristar (Budget Comfort)",
                    "category": "🏨 Prime Metro Hub Stay",
                    "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Strategically placed next to Lakdikapool and Nampally stations with direct Metro access to Charminar and Hitec City.",
                },
                {
                    "title": "Authentic Hyderabadi Dum Biryani & Irani Chai",
                    "category": "🍽️ Royal Nizami Feast",
                    "url": "https://images.unsplash.com/photo-1563379091339-03b21ab4a4f8?w=600&auto=format&fit=crop&q=80",
                    "why_famous": "Fragrant basmati rice slow-steamed under sealed dough (Dum) with saffron, tender marinated meat, served with Mirchi ka Salan and Osmania biscuits with creamy Irani chai.",
                },
            ],
            "extended_guidance": {
                "why_visit": "Hyderabad is the City of Pearls and Nizami splendor, blending historic Deccan monuments with world-beating biryani culture.",
            },
        },
    ],
}


def _normalize_key(city_str: str) -> str:
    s = str(city_str or "").strip().lower()
    mapping = {
        "tirupathi": "tirupati",
        "vijayawada": "vijayawada",
        "bezawada": "vijayawada",
        "vizag": "visakhapatnam",
        "vishakapatnam": "visakhapatnam",
        "nellor": "nellore",
        "nellore": "nellore",
        "rajmundary": "rajahmundry",
        "rajahmundry": "rajahmundry",
        "rajamahendravaram": "rajahmundry",
        "kurnool": "kurnool",
        "kakinada": "kakinada",
        "goa": "goa",
        "gokarna": "gokarna",
        "munnar": "munnar",
        "hyderabad": "hyderabad",
        "secunderabad": "hyderabad",
        "delhi": "delhi",
        "jaipur": "jaipur",
        "agra": "agra",
        "bengaluru": "bengaluru",
        "bangalore": "bengaluru",
    }
    return mapping.get(s, s)


def get_day_photos(city: str, day_number: int) -> list[dict[str, Any]]:
    """Returns curated high-quality photos with title, category, url, and why_famous."""
    norm = _normalize_key(city)
    if norm in CITY_MEDIA_DATABASE and len(CITY_MEDIA_DATABASE[norm]) > 0:
        day_entries = CITY_MEDIA_DATABASE[norm]
        entry = day_entries[(day_number - 1) % len(day_entries)]
        return entry.get("photos", [])

    # Dynamic fallback for other destinations
    clean_city = str(city).strip().title()
    return [
        {
            "title": f"{clean_city} Heritage Landmark",
            "category": "🏛️ Famous Monument",
            "url": "https://images.unsplash.com/photo-1524492412937-b28074a5d7da?w=600&auto=format&fit=crop&q=80",
            "why_famous": f"The architectural and cultural centerpiece of {clean_city}, celebrated for its rich regional history and panoramic vistas.",
        },
        {
            "title": f"Central Residency / Hotel {clean_city}",
            "category": "🏨 Recommended Budget Stay",
            "url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=600&auto=format&fit=crop&q=80",
            "why_famous": f"Centrally situated near primary transit hubs in {clean_city}, saving private commute fees and keeping key sights within quick reach.",
        },
        {
            "title": f"Authentic {clean_city} Regional Thali & Dining",
            "category": "🍽️ Famous Local Delicacy",
            "url": "https://images.unsplash.com/photo-1610057099443-fde8c4d50f91?w=600&auto=format&fit=crop&q=80",
            "why_famous": f"Celebrated local cuisine showcasing authentic regional recipes, aromatic spices, and traditional hospitality in {clean_city}.",
        },
    ]


def enrich_itinerary_with_media(out_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Enriches each day in the itinerary dictionary with visual photos,
    ensuring every single day has high-resolution imagery and 'why famous' explanations.
    """
    if not isinstance(out_dict, dict):
        return out_dict

    days = out_dict.get("days")
    if not isinstance(days, list):
        return out_dict

    primary_city = str(out_dict.get("destination_city", "")).strip()

    for idx, day in enumerate(days):
        if not isinstance(day, dict):
            continue

        day_num = int(day.get("day_number", idx + 1))
        day_city = str(day.get("city") or primary_city or "Destination").strip()

        # Attach curated photos if not already present or empty
        if not day.get("photos"):
            day["photos"] = get_day_photos(day_city, day_num)

        # Enhance brief text if user received a 1-liner previously
        morning_text = str(day.get("morning", ""))
        if len(morning_text.split()) < 25:
            norm = _normalize_key(day_city)
            if norm == "tirupati" and day_num == 1:
                day["morning"] = (
                    "🌅 06:00 AM - 11:30 AM (Tirumala Balaji Darshan & Silathoranam Arch): "
                    "Start early at 06:00 AM to beat peak pilgrimage rush. Take the official TTD AC Electric Bus "
                    "from RTC Bus Stand (₹65/person) instead of ₹1,200 private cabs to save money. If you booked "
                    "₹300 Special Entry Darshan (SED), enter through Vaikuntam Queue Complex-1; otherwise collect the "
                    "free Slotted Sarva Darshan (SSD) token at Vishnu Nivasam. After sacred darshan of Lord Venkateswara, "
                    "collect your Tirupati Laddoo prasadam and walk to the 2.5-billion-year-old Silathoranam geological "
                    "rock arch. Enjoy breakfast at Sri Lakshmi Narayana Bhavan (Ghee Podi Dosa & Filter Coffee ₹80)."
                )
            elif norm == "tirupati" and day_num == 2:
                day["morning"] = (
                    "🌅 07:30 AM - 12:00 PM (Chandragiri 11th-Century Fort & Raja Mahal): "
                    "Board a direct APSRTC bus or shared auto (₹30) to the historic Chandragiri Fort (14 km west). "
                    "Built in the 11th century as the fourth capital of the Vijayanagara Empire, explore the 3-storey "
                    "Indo-Saracenic Raja Mahal and Rani Mahal. Climb the stone ramparts for sweeping countryside views. "
                    "Entry is only ₹25 (ASI). Tour the royal museum exhibiting medieval weapons, coins, and bronze idols."
                )

    return out_dict
