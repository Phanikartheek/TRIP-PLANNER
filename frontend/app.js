/**
 * AI Trip Planner - Frontend Controller
 * Supports India Domestic & International modes, currency switching (INR, USD, EUR),
 * dynamic presets, food/travel filters, and multi-agent execution with rich rendering.
 */

document.addEventListener('DOMContentLoaded', () => {
  // --- Register Service Worker for 100% Offline Access ---
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js').then((reg) => {
        console.log('✅ Service Worker registered for offline access:', reg.scope);
      }).catch((err) => {
        console.warn('Service Worker registration failed:', err);
      });
    });
  }

  // PWA Install Prompt Listener
  let deferredPrompt;
  const btnInstallPwa = document.getElementById('btn-install-pwa');
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    if (btnInstallPwa) {
      btnInstallPwa.style.display = 'inline-flex';
      btnInstallPwa.onclick = () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
              btnInstallPwa.style.display = 'none';
              showToast('📲 Trip Planner installed successfully on your device!');
            }
            deferredPrompt = null;
          });
        }
      };
    }
  });

  // Helper: WhatsApp Daily Digest Share
  window.shareDayWhatsApp = function(dayNum) {
    if (!currentItinerary || !currentItinerary.days) return;
    const day = currentItinerary.days.find(d => d.day_number === dayNum) || currentItinerary.days[dayNum - 1];
    if (!day) return;
    const theme = day.theme || `Day ${dayNum}`;
    const cName = day.city || currentItinerary.destination_city || 'City';
    let text = `🌴 *Day ${dayNum}: ${theme}*\n`;
    text += `📍 *Location:* ${cName}\n`;
    if (day.date) text += `🗓️ *Date:* ${day.date}\n`;
    if (day.weather_note) text += `🌦️ *Weather:* ${day.weather_note}\n\n`;
    if (day.morning) text += `🌅 *Morning:* ${day.morning}\n\n`;
    if (day.afternoon) text += `☀️ *Afternoon:* ${day.afternoon}\n\n`;
    if (day.evening) text += `🌆 *Evening:* ${day.evening}\n\n`;
    if (day.night) text += `🌙 *Night:* ${day.night}\n\n`;
    text += `💰 *Est. Daily Cost:* ₹${day.estimated_cost || 0}\n`;
    text += `🗺️ *Directions:* https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(theme + ' ' + cName)}`;

    window.open(`https://api.whatsapp.com/send?text=${encodeURIComponent(text)}`, '_blank');
  };

  // DOM Elements
  const form = document.getElementById('trip-form');
  const submitBtn = document.getElementById('submit-btn');
  const originInput = document.getElementById('origin');
  const citiesInput = document.getElementById('cities');
  const interestsInput = document.getElementById('interests');
  const daysSlider = document.getElementById('trip_length');
  const daysBadge = document.getElementById('days-val');
  const budgetInput = document.getElementById('budget');
  const budgetBadge = document.getElementById('budget-val');
  const budgetCurrencySymbol = document.getElementById('budget-currency-symbol');
  const travelStyleSelect = document.getElementById('travel-style-select');
  const languageSelect = document.getElementById('language-select');

  // Mode Buttons
  const modeDomesticBtn = document.getElementById('mode-domestic');
  const modeInternationalBtn = document.getElementById('mode-international');
  const presetsHeading = document.getElementById('presets-heading');
  const presetsGrid = document.getElementById('presets-grid');

  // Currency & Chips
  const currPills = document.querySelectorAll('.curr-pill');
  const interestTags = document.querySelectorAll('.interest-tag');
  const foodPills = document.querySelectorAll('.food-pill');
  const quickChips = document.querySelectorAll('.quick-chip');

  // Tracker & Results
  const trackerSection = document.getElementById('agent-tracker');
  const resultsSection = document.getElementById('results-section');
  const toastContainer = document.getElementById('toast-container');

  // Agent Step Elements
  const agent1Card = document.getElementById('agent-1');
  const agent2Card = document.getElementById('agent-2');
  const agent3Card = document.getElementById('agent-3');

  // Result Elements
  const destCity = document.getElementById('dest-city');
  const destCountry = document.getElementById('dest-country');
  const destActionsBar = document.getElementById('dest-actions-bar');
  const totalCostBadge = document.getElementById('total-cost-val');
  const budgetRatioVal = document.getElementById('budget-ratio-val');
  const foodHighlightCard = document.getElementById('food-highlight-card');
  const foodHighlightList = document.getElementById('food-highlight-list');
  const transitHighlightText = document.getElementById('transit-highlight-text');
  const daysTimeline = document.getElementById('days-timeline');
  const packingGrid = document.getElementById('packing-grid');

  // State Variables
  let currentJobData = null;

  // Backend API Base URL Configuration (Supports FastAPI on :8000, VSCode Live Server on :5500, or file:// preview)
  const API_BASE = (window.location.protocol === 'file:' || (window.location.port && window.location.port !== '8000'))
    ? 'http://127.0.0.1:8000'
    : '';

  // Backend Status Badge
  const backendStatusBadge = document.getElementById('backend-status-badge');
  const statusDot = document.getElementById('status-dot');
  const statusText = document.getElementById('status-text');

  async function checkBackendHealth() {
    if (!backendStatusBadge || !statusText) return;
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      if (res.ok) {
        const data = await res.json();
        backendStatusBadge.className = 'backend-status-badge status-connected';
        backendStatusBadge.title = `Connected to backend (Model: ${data.default_model || 'Groq'})`;
        statusText.textContent = data.groq_configured ? '🟢 Backend Connected' : '🟡 Backend Online (No API Key)';
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      backendStatusBadge.className = 'backend-status-badge status-disconnected';
      backendStatusBadge.title = `Cannot connect to backend at ${API_BASE || 'http://127.0.0.1:8000'}. Click to retry.`;
      statusText.textContent = '🔴 Backend Offline (Click to Retry)';
    }
  }

  if (backendStatusBadge) {
    backendStatusBadge.addEventListener('click', () => {
      backendStatusBadge.className = 'backend-status-badge status-checking';
      if (statusText) statusText.textContent = 'Retrying Connection...';
      checkBackendHealth();
    });
  }

  // Check health immediately and periodically
  checkBackendHealth();
  setInterval(checkBackendHealth, 15000);

  // Ensure results and tracker sections are hidden on clean load
  if (resultsSection) resultsSection.classList.remove('active');
  if (trackerSection) trackerSection.classList.remove('active');

  // State Management
  let currentMode = 'domestic'; // 'domestic' | 'international'
  let currentCurrency = 'INR'; // 'INR' | 'USD' | 'EUR'
  let currentItinerary = null;
  let currentJobId = null;
  let progressInterval = null;

  // Currency Symbols & Live Tourist Exchange Rates (relative to INR)
  const CURRENCY_SYMBOLS = {
    INR: '₹',
    USD: '$',
    EUR: '€',
    GBP: '£',
    AED: 'AED ',
  };

  const EXCHANGE_RATES = {
    INR: 1.0,
    USD: 0.012,
    EUR: 0.011,
    GBP: 0.0095,
    AED: 0.044,
  };

  let activeDisplayCurrency = 'INR';


  // Domestic Indian Destination Presets
  const DOMESTIC_PRESETS = [
    {
      id: 'himachal',
      label: '🏔️ Manali & Solang Valley (Himachal)',
      origin: 'Delhi NCR',
      cities: 'Manali, Shimla, Dharamshala',
      interests: 'snow mountains, trekking, cafe culture, paragliding',
      days: 5,
      budget: 22000,
      currency: 'INR',
      food: 'Authentic Street Food',
    },
    {
      id: 'goa-gokarna',
      label: '🏖️ Goa & Gokarna Coastal Vibes',
      origin: 'Bengaluru',
      cities: 'Goa, Gokarna, Karwar',
      interests: 'beaches, seafood, sunsets, water sports, forts',
      days: 4,
      budget: 18000,
      currency: 'INR',
      food: 'Coastal & Seafood',
    },
    {
      id: 'kerala-backwaters',
      label: '🌿 Munnar & Alleppey Backwaters',
      origin: 'Bengaluru',
      cities: 'Munnar, Alleppey, Kochi',
      interests: 'tea plantations, waterfalls, houseboat, nature',
      days: 5,
      budget: 25000,
      currency: 'INR',
      food: 'No Restrictions',
    },
    {
      id: 'rajasthan-royal',
      label: '🏰 Jaipur & Udaipur Royal Palaces',
      origin: 'Mumbai',
      cities: 'Jaipur, Udaipur, Jodhpur',
      interests: 'forts, palaces, royal heritage, photography, bazaars',
      days: 6,
      budget: 32000,
      currency: 'INR',
      food: 'Pure Vegetarian',
    },
    {
      id: 'spiritual-ganga',
      label: '🕉️ Rishikesh & Varanasi Ghats',
      origin: 'Delhi NCR',
      cities: 'Rishikesh, Haridwar, Varanasi',
      interests: 'Ganga aarti, river rafting, spirituality, yoga, temples',
      days: 5,
      budget: 20000,
      currency: 'INR',
      food: 'Pure Vegetarian',
    },
    {
      id: 'coorg-estates',
      label: '☕ Coorg & Chikmagalur Coffee Trails',
      origin: 'Bengaluru',
      cities: 'Coorg, Chikmagalur, Wayanad',
      interests: 'coffee estates, homestays, waterfalls, hiking',
      days: 3,
      budget: 15000,
      currency: 'INR',
      food: 'No Restrictions',
    },
    {
      id: 'ladakh-adventure',
      label: '❄️ Leh Ladakh & Nubra High Passes',
      origin: 'Delhi NCR',
      cities: 'Leh, Nubra Valley, Pangong Tso',
      interests: 'high mountain passes, monasteries, lakes, stargazing',
      days: 7,
      budget: 45000,
      currency: 'INR',
      food: 'No Restrictions',
    },
  ];

  // International Destination Presets
  const INTERNATIONAL_PRESETS = [
    {
      id: 'bali',
      label: '🏝️ Bali & Ubud Tropical Temples',
      origin: 'Bengaluru',
      cities: 'Bali, Lombok, Phuket',
      interests: 'beaches, surfing, food, temples, waterfalls',
      days: 6,
      budget: 1400,
      currency: 'USD',
      food: 'No Restrictions',
    },
    {
      id: 'japan',
      label: '🍣 Tokyo & Kyoto Cultural Trail',
      origin: 'Mumbai',
      cities: 'Kyoto, Tokyo, Osaka',
      interests: 'culture, ramen, temples, gardens, bullet trains',
      days: 7,
      budget: 2400,
      currency: 'USD',
      food: 'No Restrictions',
    },
    {
      id: 'europe',
      label: '🏛️ Rome & Amalfi Coast Explorer',
      origin: 'Delhi NCR',
      cities: 'Rome, Florence, Amalfi',
      interests: 'history, architecture, Italian food, art museums',
      days: 7,
      budget: 2600,
      currency: 'EUR',
      food: 'No Restrictions',
    },
    {
      id: 'dubai',
      label: '🏙️ Dubai & Abu Dhabi Luxe',
      origin: 'Mumbai',
      cities: 'Dubai, Abu Dhabi, Sharjah',
      interests: 'desert safari, skyline, shopping, theme parks',
      days: 5,
      budget: 1800,
      currency: 'USD',
      food: 'No Restrictions',
    },
    {
      id: 'swiss',
      label: '🏔️ Swiss Alps & Interlaken',
      origin: 'Bengaluru',
      cities: 'Interlaken, Lucerne, Zermatt',
      interests: 'scenic trains, snow peaks, hiking, lakes',
      days: 6,
      budget: 2800,
      currency: 'EUR',
      food: 'No Restrictions',
    },
  ];

  // --- Render Presets Based on Active Mode ---
  function renderPresets() {
    presetsGrid.innerHTML = '';
    const presets = currentMode === 'domestic' ? DOMESTIC_PRESETS : INTERNATIONAL_PRESETS;
    presetsHeading.textContent = currentMode === 'domestic' 
      ? '⚡ Curated Indian Destination Presets:' 
      : '⚡ Curated Global Gateway Presets:';

    presets.forEach(p => {
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'preset-chip';
      chip.dataset.presetId = p.id;
      chip.innerHTML = `<span>${p.label}</span>`;
      
      chip.addEventListener('click', () => {
        applyPreset(p);
      });
      
      presetsGrid.appendChild(chip);
    });
  }

  function applyPreset(p) {
    originInput.value = p.origin;
    citiesInput.value = p.cities;
    interestsInput.value = p.interests;
    daysSlider.value = p.days;
    daysBadge.textContent = `${p.days} Days`;
    budgetInput.value = p.budget;

    // Set currency
    setCurrency(p.currency);
    updateBudgetDisplay();

    // Sync interest tags
    const activeKeywords = p.interests.toLowerCase().split(',').map(s => s.trim());
    interestTags.forEach(tag => {
      const val = tag.dataset.value.toLowerCase();
      if (activeKeywords.some(k => val.includes(k) || k.includes(val))) {
        tag.classList.add('active');
      } else {
        tag.classList.remove('active');
      }
    });

    // Sync food pill
    if (p.food) {
      foodPills.forEach(fp => {
        fp.classList.toggle('active', fp.dataset.food === p.food);
      });
    }

    showToast(`✨ Loaded preset: ${p.label}`);
  }

  // Mode is locked to Domestic in Phase 1
  modeDomesticBtn.addEventListener('click', () => {
    setCurrency('INR');
    updateBudgetDisplay();
    showToast('🇮🇳 Explore India (Domestic) Mode Active');
  });

  modeInternationalBtn.addEventListener('click', (e) => {
    e.preventDefault();
    showToast('🔒 Global destinations are planned for Phase 2. Currently running India Edition (v1).');
  });

  // --- Currency Selector ---
  currPills.forEach(pill => {
    pill.addEventListener('click', () => {
      const newCurr = pill.dataset.curr;
      setCurrency(newCurr);
      // Auto adjust budget range if switching between INR and USD/EUR
      const currentVal = Number(budgetInput.value) || 0;
      if (newCurr === 'INR' && currentVal < 5000) {
        budgetInput.value = currentVal * 85;
      } else if ((newCurr === 'USD' || newCurr === 'EUR') && currentVal > 5000) {
        budgetInput.value = Math.round(currentVal / 85);
      }
      updateBudgetDisplay();
    });
  });

  function setCurrency(curr) {
    currentCurrency = curr;
    currPills.forEach(p => p.classList.toggle('active', p.dataset.curr === curr));
    const sym = CURRENCY_SYMBOLS[curr] || curr;
    budgetCurrencySymbol.textContent = sym;
  }

  function formatMoney(amount, currencyCode = activeDisplayCurrency) {
    const sym = CURRENCY_SYMBOLS[currencyCode] || currencyCode;
    let num = Number(amount) || 0;
    if (currencyCode !== 'INR' && EXCHANGE_RATES[currencyCode]) {
      num = Math.round(num * EXCHANGE_RATES[currencyCode]);
    } else {
      num = Math.round(num);
    }
    return `${sym}${num.toLocaleString()}`;
  }

  function updateBudgetDisplay() {
    const val = Number(budgetInput.value) || 0;
    budgetBadge.textContent = formatMoney(val, currentCurrency);
  }

  // --- Live Tourist Currency Switcher on Results ---
  const currencySelector = document.getElementById('currency-selector');
  if (currencySelector) {
    currencySelector.addEventListener('change', (e) => {
      activeDisplayCurrency = e.target.value;
      if (currentItinerary) {
        totalCostBadge.textContent = formatMoney(currentItinerary.total_estimated_cost || 0, activeDisplayCurrency);
        renderItinerary(currentItinerary, currentItinerary.total_estimated_cost, activeDisplayCurrency);
        showToast(`💱 Switched display currency to ${activeDisplayCurrency}`);
      }
    });
  }

  // --- 🎫 Travel Pass Modal Handlers ---
  const btnViewPass = document.getElementById('btn-view-pass');
  const travelPassModal = document.getElementById('travel-pass-modal');
  const passModalCloseBtn = document.getElementById('pass-modal-close-btn');
  const btnPrintPass = document.getElementById('btn-print-pass');

  if (btnViewPass) {
    btnViewPass.addEventListener('click', () => {
      if (!currentItinerary) {
        showToast('⚠️ Please generate or load an itinerary first to view your Travel Pass.');
        return;
      }
      const city = currentItinerary.destination_city || 'India';
      const orig = (currentJobData && currentJobData.origin) || document.getElementById('origin').value || 'Departure Hub';
      const startDate = currentItinerary.start_date || currentItinerary.travel_date || 'Day 1';
      const endDate = currentItinerary.end_date || `${(currentItinerary.days || []).length} Days`;
      const costPP = currentItinerary.cost_per_person || Math.round((currentItinerary.total_estimated_cost || 0) / Math.max(1, currentItinerary.travelers || 1));

      const titleEl = document.getElementById('pass-dest-title');
      const origEl = document.getElementById('pass-origin-city');
      const destEl = document.getElementById('pass-dest-city');
      const datesEl = document.getElementById('pass-dates');
      const costEl = document.getElementById('pass-cost-pp');
      const sightsContainer = document.getElementById('pass-sights-tags');

      if (titleEl) titleEl.textContent = `${city.toUpperCase()} EXPEDITION PASS`;
      if (origEl) origEl.textContent = orig;
      if (destEl) destEl.textContent = city;
      if (datesEl) datesEl.textContent = `${startDate} • ${endDate}`;
      if (costEl) costEl.textContent = formatMoney(costPP, activeDisplayCurrency);

      if (sightsContainer) {
        sightsContainer.innerHTML = '';
        const sights = [];
        (currentItinerary.days || []).forEach(d => {
          (d.activities || []).forEach(a => {
            if (a.title && sights.length < 5) sights.push(a.title);
          });
        });
        if (sights.length === 0) sights.push('Sightseeing & Cultural Exploration');
        sights.forEach(s => {
          const span = document.createElement('span');
          span.style.cssText = 'background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 4px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; border: 1px solid rgba(56, 189, 248, 0.3);';
          span.textContent = `📍 ${s}`;
          sightsContainer.appendChild(span);
        });
      }

      if (travelPassModal) travelPassModal.classList.remove('hidden');
    });
  }

  if (passModalCloseBtn && travelPassModal) {
    passModalCloseBtn.addEventListener('click', () => {
      travelPassModal.classList.add('hidden');
    });
  }

  if (btnPrintPass) {
    btnPrintPass.addEventListener('click', () => {
      window.print();
    });
  }


  // --- Quick Chips Handlers ---
  quickChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const target = chip.dataset.target;
      const val = chip.dataset.value;
      if (target === 'origin') {
        originInput.value = val;
        showToast(`📍 Origin set to ${val}`);
      } else if (target === 'budget') {
        // Adjust for current currency if in USD/EUR
        let numVal = Number(val);
        if (currentCurrency === 'USD' || currentCurrency === 'EUR') {
          numVal = Math.round(numVal / 85);
        }
        budgetInput.value = numVal;
        updateBudgetDisplay();
        showToast(`💵 Budget set to ${formatMoney(numVal, currentCurrency)}`);
      }
    });
  });

  // --- Interest Tags Multi-Select ---
  interestTags.forEach(tag => {
    tag.addEventListener('click', () => {
      tag.classList.toggle('active');
      syncInterestsInput();
    });
  });

  function syncInterestsInput() {
    const active = Array.from(document.querySelectorAll('.interest-tag.active')).map(t => t.dataset.value);
    interestsInput.value = active.join(', ');
  }

  // --- Food Preferences Single / Multi Select ---
  foodPills.forEach(pill => {
    pill.addEventListener('click', () => {
      foodPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      showToast(`🍲 Dietary preference: ${pill.textContent.trim()}`);
    });
  });

  function getSelectedFood() {
    const activePill = document.querySelector('.food-pill.active');
    return activePill ? activePill.dataset.food : '';
  }

  // --- Slider & Date Sync Handlers ---
  const travelDateInput = document.getElementById('travel_date');
  const returnDateInput = document.getElementById('return_date');

  function syncDatesAndDuration(source) {
    if (!travelDateInput || !returnDateInput) return;
    const startVal = travelDateInput.value;
    const returnVal = returnDateInput.value;

    if (startVal && returnVal) {
      const startDate = new Date(startVal);
      const endDate = new Date(returnVal);
      const diffTime = endDate - startDate;
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)) + 1;
      if (diffDays >= 1 && diffDays <= 30) {
        daysSlider.value = diffDays;
        daysBadge.textContent = `${diffDays} Days`;
      }
    } else if (startVal && source === 'slider') {
      const startDate = new Date(startVal);
      const numDays = parseInt(daysSlider.value, 10) || 1;
      const endDate = new Date(startDate);
      endDate.setDate(startDate.getDate() + numDays - 1);
      returnDateInput.value = endDate.toISOString().split('T')[0];
    }
  }

  if (travelDateInput) {
    travelDateInput.addEventListener('change', () => syncDatesAndDuration('start'));
  }
  if (returnDateInput) {
    returnDateInput.addEventListener('change', () => syncDatesAndDuration('return'));
  }

  daysSlider.addEventListener('input', (e) => {
    daysBadge.textContent = `${e.target.value} Days`;
    syncDatesAndDuration('slider');
  });

  // --- Smart Multi-City Auto-Check & Hint Handler ---
  const multiCityCheckbox = document.getElementById('multi_city');
  const multiCityAutoHint = document.getElementById('multi-city-auto-hint');

  function checkMultiCityAutoDetect() {
    if (!citiesInput || !multiCityCheckbox) return;
    const rawVal = citiesInput.value.trim();
    const cityList = rawVal.split(',').map(c => c.trim()).filter(Boolean);

    if (cityList.length > 1) {
      multiCityCheckbox.checked = true;
      if (multiCityAutoHint) {
        multiCityAutoHint.textContent = `✨ Multi-City Trip Auto-Enabled! The AI will sequence ALL entered cities (${cityList.join(' ➔ ')}) across your itinerary.`;
        multiCityAutoHint.style.display = 'block';
      }
    } else {
      if (multiCityAutoHint) multiCityAutoHint.style.display = 'none';
    }
  }

  if (citiesInput) {
    citiesInput.addEventListener('input', checkMultiCityAutoDetect);
    citiesInput.addEventListener('change', checkMultiCityAutoDetect);
    checkMultiCityAutoDetect();
  }

  budgetInput.addEventListener('input', () => {
    updateBudgetDisplay();
  });

  // --- Group Expense Splitter Controller ---
  const btnAddExpense = document.getElementById('btn-add-expense');
  const splitItemName = document.getElementById('split-item-name');
  const splitItemAmount = document.getElementById('split-item-amount');
  const splitPaidBy = document.getElementById('split-paid-by');
  const splitTableBody = document.getElementById('split-expenses-table-body');
  const splitSummaryBox = document.getElementById('split-summary-box');

  let groupExpenses = [];

  function renderGroupExpenses() {
    if (!splitTableBody) return;

    let totalSpent = 0;
    const paidByMap = {};

    groupExpenses.forEach((exp, idx) => {
      totalSpent += exp.amount;
      paidByMap[exp.paidBy] = (paidByMap[exp.paidBy] || 0) + exp.amount;
    });

    // Update Live Wallet Progress Bar
    const plannedBudget = (currentItinerary && currentItinerary.total_estimated_cost) ? currentItinerary.total_estimated_cost : (parseFloat(budgetInput.value) || 0);
    const plannedEl = document.getElementById('wallet-planned-cost');
    const spentEl = document.getElementById('wallet-total-spent');
    const remainingEl = document.getElementById('wallet-remaining-balance');
    const progressBar = document.getElementById('wallet-progress-bar');
    const burnStatus = document.getElementById('wallet-burn-status');

    if (plannedEl) plannedEl.textContent = `₹${plannedBudget.toLocaleString('en-IN')}`;
    if (spentEl) spentEl.textContent = `₹${totalSpent.toLocaleString('en-IN')}`;
    const rem = plannedBudget - totalSpent;
    if (remainingEl) {
      remainingEl.textContent = `₹${rem.toLocaleString('en-IN')}`;
      remainingEl.style.color = rem >= 0 ? '#a7f3d0' : '#f87171';
    }

    if (progressBar) {
      const pct = plannedBudget > 0 ? Math.min(100, Math.round((totalSpent / plannedBudget) * 100)) : 0;
      progressBar.style.width = `${pct}%`;
      if (rem < 0) {
        progressBar.style.backgroundColor = '#ef4444';
      } else if (pct > 85) {
        progressBar.style.backgroundColor = '#f59e0b';
      } else {
        progressBar.style.backgroundColor = '#10b981';
      }
    }

    if (burnStatus) {
      if (plannedBudget <= 0) {
        burnStatus.textContent = 'Track your actual spend on the trip to stay strictly within your budget!';
        burnStatus.style.color = '#94a3b8';
      } else if (rem < 0) {
        burnStatus.innerHTML = `⚠️ <strong style="color:#ef4444;">Budget Exceeded!</strong> You have spent ₹${Math.abs(rem).toLocaleString('en-IN')} more than planned.`;
      } else {
        const pctLeft = Math.round((rem / plannedBudget) * 100);
        burnStatus.innerHTML = `🟢 <strong>On Track:</strong> You still have <strong style="color:#4ade80;">₹${rem.toLocaleString('en-IN')} (${pctLeft}%)</strong> remaining.`;
      }
    }

    // Persist to localStorage
    if (currentJobId) {
      try {
        localStorage.setItem(`trip_wallet_${currentJobId}`, JSON.stringify(groupExpenses));
      } catch (e) {}
    }

    if (groupExpenses.length === 0) {
      splitTableBody.innerHTML = `
        <tr>
          <td colspan="4" style="padding: 12px; text-align: center; color: #64748b;">No group expenses added yet. Enter items above to calculate split settlements.</td>
        </tr>
      `;
      if (splitSummaryBox) splitSummaryBox.style.display = 'none';
      return;
    }

    splitTableBody.innerHTML = '';
    groupExpenses.forEach((exp, idx) => {
      const tr = document.createElement('tr');
      tr.style.borderBottom = '1px solid rgba(255,255,255,0.06)';
      tr.innerHTML = `
        <td style="padding: 8px; color: #f8fafc; font-weight: 600;">${escapeHtml(exp.name)}</td>
        <td style="padding: 8px; color: #4ade80; font-weight: 700;">₹${exp.amount.toLocaleString('en-IN')}</td>
        <td style="padding: 8px; color: #38bdf8;">${escapeHtml(exp.paidBy)}</td>
        <td style="padding: 8px;">
          <button type="button" style="background: rgba(239, 68, 68, 0.2); color: #ef4444; border: 1px solid #ef4444; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; cursor: pointer;" onclick="deleteGroupExpense(${idx})">Delete</button>
        </td>
      `;
      splitTableBody.appendChild(tr);
    });

    const people = Object.keys(paidByMap);
    const numPeople = Math.max(1, people.length);
    const perPersonShare = Math.round(totalSpent / numPeople);

    let summaryText = `💰 <strong>Total Spent:</strong> ₹${totalSpent.toLocaleString('en-IN')} | <strong>Fair Share per Person (${numPeople} travelers):</strong> ₹${perPersonShare.toLocaleString('en-IN')}<br><div style="margin-top:6px;">`;
    
    people.forEach(p => {
      const diff = paidByMap[p] - perPersonShare;
      if (diff > 0) {
        summaryText += `🟢 <strong>${p}</strong> gets back <span style="color:#4ade80;">₹${diff.toLocaleString('en-IN')}</span><br>`;
      } else if (diff < 0) {
        summaryText += `🔴 <strong>${p}</strong> owes <span style="color:#f87171;">₹${Math.abs(diff).toLocaleString('en-IN')}</span><br>`;
      } else {
        summaryText += `⚪ <strong>${p}</strong> is fully settled up!<br>`;
      }
    });
    summaryText += `</div>`;

    if (splitSummaryBox) {
      splitSummaryBox.innerHTML = summaryText;
      splitSummaryBox.style.display = 'block';
    }
  }

  window.deleteGroupExpense = function(index) {
    groupExpenses.splice(index, 1);
    renderGroupExpenses();
  };

  if (btnAddExpense) {
    btnAddExpense.onclick = () => {
      const name = splitItemName.value.trim();
      const amount = parseFloat(splitItemAmount.value);
      const paidBy = splitPaidBy.value.trim() || 'Traveler';

      if (!name || isNaN(amount) || amount <= 0) {
        showToast('⚠️ Please enter a valid expense name and positive amount.');
        return;
      }

      groupExpenses.push({ name, amount, paidBy });
      splitItemName.value = '';
      splitItemAmount.value = '';
      renderGroupExpenses();
      showToast(`✅ Added ₹${amount} expense paid by ${paidBy}!`);
    };
  }

  // --- Form Submit & CrewAI Kickoff ---
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const travelersInput = document.getElementById('travelersInput');
    const travelersVal = travelersInput ? (parseInt(travelersInput.value, 10) || 1) : 1;

    const payload = {
      origin: originInput.value.trim(),
      cities: citiesInput.value.trim(),
      interests: interestsInput.value.trim(),
      trip_length: parseInt(daysSlider.value, 10),
      budget: parseFloat(budgetInput.value),
      currency: currentCurrency,
      travelers: travelersVal,
      travel_mode: currentMode,
      food_preference: getSelectedFood(),
      travel_style: travelStyleSelect.value,
      language: languageSelect ? languageSelect.value : 'en',
      travel_date: travelDateInput ? travelDateInput.value || null : null,
      return_date: returnDateInput ? returnDateInput.value || null : null,
      multi_city: document.getElementById('multi_city') ? document.getElementById('multi_city').checked : false,
    };


    if (!payload.origin || !payload.cities || !payload.interests) {
      showToast('⚠️ Please fill in all trip requirements.');
      return;
    }

    // UI Loading State
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
      <div class="spinner" style="width:18px;height:18px;border-width:2px;"></div>
      <span>Agents Collaborating & Researching...</span>
    `;

    // Show Agent Tracker
    trackerSection.classList.add('active');
    resultsSection.classList.remove('active');
    trackerSection.scrollIntoView({ behavior: 'smooth' });

    startAgentProgressAnimation();

    try {
      currentJobData = payload;
      const response = await fetch(`${API_BASE}/api/plan-trip`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error (${response.status})`);
      }

      const initData = await response.json();
      const jobId = initData.job_id;
      if (!jobId) {
        throw new Error('No job ID returned by server.');
      }
      try { localStorage.setItem('trip_planner_last_job_id', jobId); } catch (e) {}

      // Poll ${API_BASE}/api/status/{job_id} every 3 seconds until completed or failed
      let jobStatus = initData.status || 'pending';
      let itineraryData = null;
      const maxPollAttempts = 300; // Hard circuit breaker: 300 * 3s = 900s (15 minutes, matching backend)
      let pollAttempts = 0;

      while (jobStatus === 'pending' || jobStatus === 'running') {
        pollAttempts++;
        if (pollAttempts > maxPollAttempts) {
          throw new Error('⏱️ Request timed out after 15 minutes. The server took longer than expected. Please try again.');
        }

        const elapsedSec = pollAttempts * 3;
        const elapsedMin = Math.floor(elapsedSec / 60);
        const remSec = elapsedSec % 60;
        const timeStr = elapsedMin > 0 ? `${elapsedMin}m ${remSec}s` : `${remSec}s`;
        const btnSpan = submitBtn.querySelector('span');
        if (btnSpan) {
          btnSpan.textContent = `Agents Collaborating & Researching... (${timeStr})`;
        }

        await new Promise(resolve => setTimeout(resolve, 3000));

        const statusRes = await fetch(`${API_BASE}/api/status/${jobId}`);
        if (!statusRes.ok) {
          const errData = await statusRes.json().catch(() => ({}));
          throw new Error(errData.detail || `Failed to check job status (${statusRes.status})`);
        }

        const statusData = await statusRes.json();
        jobStatus = statusData.status;

        if (jobStatus === 'complete') {
          itineraryData = statusData.result;
          currentJobId = jobId;
          break;
        } else if (jobStatus === 'failed') {
          throw new Error(statusData.error || 'Trip planning job failed on server.');
        }
      }

      currentItinerary = itineraryData;
      finishAgentProgressAnimation();
      renderItinerary(currentItinerary, payload.budget, payload.currency);
      showToast('🎉 Your AI trip itinerary is ready!');

    } catch (err) {
      console.error('Plan trip error:', err);
      const msg = err.message === 'Failed to fetch'
        ? `Could not connect to backend server. Make sure the server is running on ${API_BASE || 'http://127.0.0.1:8000'}`
        : err.message;
      showToast(`❌ Error: ${msg}`);
      resetAgentCards();
    } finally {
      submitBtn.disabled = false;
      submitBtn.innerHTML = `
        <span>✨ Plan Trip with Autonomous AI Agents</span>
      `;
    }
  });

  // --- Conversational Replanning Form Handler ---
  const revisionForm = document.getElementById('revision-form');
  const revisionInput = document.getElementById('revision-input');
  const revisionBtn = document.getElementById('revision-btn');

  if (revisionForm) {
    revisionForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const feedback = revisionInput.value.trim();
      if (!feedback) {
        showToast('⚠️ Please enter your revision request.');
        return;
      }
      if (!currentJobId) {
        showToast('⚠️ No active itinerary found to revise.');
        return;
      }

      revisionBtn.disabled = true;
      revisionBtn.innerHTML = `
        <div class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></div>
        <span>Revising Itinerary with Travel Concierge...</span>
      `;

      try {
        const response = await fetch(`${API_BASE}/api/revise-trip`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: currentJobId,
            feedback,
            language: languageSelect ? languageSelect.value : 'en'
          }),
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Revision request failed (${response.status})`);
        }

        const initData = await response.json();
        const newJobId = initData.job_id;
        let jobStatus = initData.status || 'pending';
        let updatedItinerary = null;

        while (jobStatus === 'pending' || jobStatus === 'running') {
          await new Promise(resolve => setTimeout(resolve, 3000));
          const statusRes = await fetch(`${API_BASE}/api/status/${newJobId}`);
          if (!statusRes.ok) {
            const errData = await statusRes.json().catch(() => ({}));
            throw new Error(errData.detail || `Failed to check status (${statusRes.status})`);
          }
          const statusData = await statusRes.json();
          jobStatus = statusData.status;

          if (jobStatus === 'complete') {
            updatedItinerary = statusData.result;
            currentJobId = newJobId;
            break;
          } else if (jobStatus === 'failed') {
            throw new Error(statusData.error || 'Revision job failed on server.');
          }
        }

        currentItinerary = updatedItinerary;
        const currentCurrency = currentItinerary.currency || 'INR';
        const currentBudget = Number(budgetInput.value) || currentItinerary.total_estimated_cost;
        renderItinerary(currentItinerary, currentBudget, currentCurrency);
        revisionInput.value = '';
        showToast('✨ Itinerary updated with your feedback!');

      } catch (err) {
        console.error('Revision error:', err);
        const msg = err.message === 'Failed to fetch'
          ? `Could not connect to backend server. Make sure the server is running on ${API_BASE || 'http://127.0.0.1:8000'}`
          : err.message;
        showToast(`❌ Revision Error: ${msg}`);
      } finally {
        revisionBtn.disabled = false;
        revisionBtn.innerHTML = `<span>✨ Revise Itinerary</span>`;
      }
    });
  }

  // --- Destination Q&A Form Handler ---
  const qaForm = document.getElementById('qa-form');
  const qaInput = document.getElementById('qa-input');
  const qaBtn = document.getElementById('qa-btn');
  const qaConversationThread = document.getElementById('qa-conversation-thread');
  let qaTurnCount = 0;

  if (qaForm) {
    qaForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const question = qaInput.value.trim();
      if (!question) {
        showToast('⚠️ Please enter your question.');
        return;
      }
      if (!currentJobId) {
        showToast('⚠️ Please generate a trip first before asking destination questions.');
        return;
      }

      qaBtn.disabled = true;
      qaBtn.innerHTML = `
        <div class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></div>
        <span>Consulting Local Q&A Expert...</span>
      `;

      try {
        const response = await fetch(`${API_BASE}/api/ask-question`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            job_id: currentJobId,
            question,
            language: languageSelect ? languageSelect.value : 'en'
          }),
        });

        if (!response.ok) {
          const errData = await response.json().catch(() => ({}));
          throw new Error(errData.detail || `Question request failed (${response.status})`);
        }

        const initData = await response.json();
        const qaJobId = initData.job_id;
        let jobStatus = initData.status || 'pending';
        let qaResult = null;

        while (jobStatus === 'pending' || jobStatus === 'running') {
          await new Promise(resolve => setTimeout(resolve, 3000));
          const statusRes = await fetch(`${API_BASE}/api/status/${qaJobId}`);
          if (!statusRes.ok) {
            const errData = await statusRes.json().catch(() => ({}));
            throw new Error(errData.detail || `Failed to check status (${statusRes.status})`);
          }
          const statusData = await statusRes.json();
          jobStatus = statusData.status;

          if (jobStatus === 'complete') {
            qaResult = statusData.result;
            break;
          } else if (jobStatus === 'failed') {
            throw new Error(statusData.error || 'Q&A job failed on server.');
          }
        }

        if (qaResult) {
          qaTurnCount += 1;
          const answerText = qaResult.answer || (typeof qaResult === 'string' ? qaResult : JSON.stringify(qaResult));
          const groundedClaims = Array.isArray(qaResult.grounded_claims) ? qaResult.grounded_claims : [];
          const ungroundedClaims = Array.isArray(qaResult.ungrounded_claims) ? qaResult.ungrounded_claims : [];
          const sources = Array.isArray(qaResult.sources) ? qaResult.sources : [];

          // Render Grounding Badges
          let groundingHtml = '';
          if (groundedClaims.length > 0 || ungroundedClaims.length > 0) {
            groundingHtml = `
              <div class="qa-grounding-section">
                <div class="qa-grounding-label">Fact Verification & Grounding</div>
                <div class="qa-claims-badges-wrapper">
                  ${groundedClaims.map(c => `<span class="qa-claim-badge-grounded" title="Search-verified fact">✓ ${escapeHtml(c)}</span>`).join('')}
                  ${ungroundedClaims.map(c => `<span class="qa-claim-badge-ungrounded" title="General knowledge, not search-verified">⚠ ${escapeHtml(c)}</span>`).join('')}
                </div>
              </div>
            `;
          }

          // Render Sources
          let sourcesHtml = '';
          if (sources.length > 0) {
            sourcesHtml = `
              <div class="qa-sources-list">
                <strong>Sources:</strong> ${sources.map(url => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>`).join(', ')}
              </div>
            `;
          }

          const turnCard = document.createElement('div');
          turnCard.className = 'qa-turn-card';
          turnCard.innerHTML = `
            <div class="qa-turn-header">
              <span class="qa-turn-badge">📍 Turn #${qaTurnCount} • Local Q&A Expert</span>
              <span class="qa-turn-time">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
            <div class="qa-user-query">
              <span class="qa-user-query-icon">💬</span>
              <span>${escapeHtml(question)}</span>
            </div>
            <div class="qa-agent-response">${escapeHtml(answerText)}</div>
            ${groundingHtml}
            ${sourcesHtml}
          `;

          if (qaConversationThread) {
            qaConversationThread.appendChild(turnCard);
            qaConversationThread.classList.remove('hidden');
          }

          qaInput.value = '';
          showToast(`✅ Turn #${qaTurnCount} answered!`);
        }

      } catch (err) {
        console.error('Q&A error:', err);
        const msg = err.message === 'Failed to fetch'
          ? `Could not connect to backend server. Make sure the server is running on ${API_BASE || 'http://127.0.0.1:8000'}`
          : err.message;
        showToast(`❌ Q&A Error: ${msg}`);
      } finally {
        qaBtn.disabled = false;
        qaBtn.innerHTML = `<span>🔍 Ask Question</span>`;
      }
    });
  }

  // --- Agent Progression Animation ---
  function startAgentProgressAnimation() {
    resetAgentCards();

    // Step 1 active immediately
    setAgentState(agent1Card, 'running', 'Searching & Evaluating Options');

    // Progression simulation while server executes real crew
    let elapsed = 0;
    clearInterval(progressInterval);
    progressInterval = setInterval(() => {
      elapsed += 1;
      if (elapsed === 3) {
        setAgentState(agent1Card, 'completed', 'Destination Selected');
        setAgentState(agent2Card, 'running', 'Scouting Local Guide & Food');
      } else if (elapsed === 7) {
        setAgentState(agent2Card, 'completed', 'Attractions & Transit Curated');
        setAgentState(agent3Card, 'running', 'Structuring Final Itinerary');
      }
    }, 1000);
  }

  function finishAgentProgressAnimation() {
    clearInterval(progressInterval);
    setAgentState(agent1Card, 'completed', 'Destination Selected');
    setAgentState(agent2Card, 'completed', 'Local Guide Verified');
    setAgentState(agent3Card, 'completed', 'Itinerary Finalized');
  }

  function resetAgentCards() {
    [agent1Card, agent2Card, agent3Card].forEach(card => {
      card.className = 'agent-step-card';
      const badge = card.querySelector('.agent-status-badge');
      if (badge) badge.textContent = 'Waiting';
    });
  }

  function setAgentState(card, state, label) {
    card.className = `agent-step-card ${state}`;
    const badge = card.querySelector('.agent-status-badge');
    if (badge) badge.textContent = label;
  }

  // --- Render Itinerary Results ---
  function renderItinerary(itinerary, userBudget, currencyCode) {
    if (!itinerary) return;

    // Render Countdown Banner with Departure & Return Dates
    const tDate = itinerary.start_date || itinerary.travel_date || (currentJobData && currentJobData.travel_date);
    const endDate = itinerary.end_date;
    const cBanner = document.getElementById('countdown-banner');
    const cText = document.getElementById('countdown-text');
    if (tDate && cBanner && cText) {
      const today = new Date(); today.setHours(0,0,0,0);
      const target = new Date(tDate); target.setHours(0,0,0,0);
      const diffDays = Math.ceil((target - today) / 86400000);
      const rangeLabel = endDate ? `Departure: ${tDate} • Return: ${endDate}` : `Departure: ${tDate}`;
      if (diffDays > 0) cText.textContent = `🗓️ ${diffDays} day${diffDays === 1 ? '' : 's'} until your trip starts! (${rangeLabel})`;
      else if (diffDays === 0) cText.textContent = `✈️ Your trip starts today! (${rangeLabel})`;
      else cText.textContent = `✈️ Trip departure was on ${tDate} (${rangeLabel})`;
      cBanner.style.display = 'block';
    } else if (cBanner) {
      cBanner.style.display = 'none';
    }

    // Render Budget Overrun Alert Banner
    const bBanner = document.getElementById('budget-alert-banner');
    const bText = document.getElementById('budget-alert-text');
    if (itinerary.budget_alert && bBanner && bText) {
      bText.textContent = `⚠️ ${itinerary.budget_alert}`;
      bBanner.style.display = 'block';
    } else if (bBanner) {
      bBanner.style.display = 'none';
    }

    const city = itinerary.destination_city || 'Featured Destination';
    const country = itinerary.destination_country || (currentMode === 'domestic' ? 'India' : '');
    const totalCost = itinerary.total_estimated_cost || 0;
    const days = itinerary.days || [];
    const packing = itinerary.packing_suggestions || [];
    const activeCurrency = itinerary.currency || currencyCode || currentCurrency;
    const transportAdvice = itinerary.local_transport_advice || [];

    // Load persisted wallet expenses for this job
    if (currentJobId) {
      try {
        const saved = localStorage.getItem(`trip_wallet_${currentJobId}`);
        groupExpenses = saved ? JSON.parse(saved) : [];
      } catch (e) {
        groupExpenses = [];
      }
    } else {
      groupExpenses = [];
    }
    renderGroupExpenses();

    if (itinerary.cities_visited && itinerary.cities_visited.length > 1) {
      destCity.textContent = `${city} (Route: ${itinerary.cities_visited.join(' ➔ ')})`;
    } else {
      destCity.textContent = city;
    }
    destCountry.innerHTML = `📍 ${country ? country : 'India'}`;
    totalCostBadge.textContent = formatMoney(totalCost, activeCurrency);

    // Quick Action Links (Google Maps, IRCTC/Trains, Flights, WhatsApp Share)
    destActionsBar.innerHTML = `
      <a href="https://www.google.com/maps/search/${encodeURIComponent(city)}" target="_blank" rel="noopener" class="dest-action-link">
        🗺️ Google Maps
      </a>
      <a href="https://www.google.com/travel/flights?q=flights+to+${encodeURIComponent(city)}" target="_blank" rel="noopener" class="dest-action-link">
        ✈️ Search Flights
      </a>
      ${currentMode === 'domestic' ? `
        <a href="https://www.irctc.co.in/nget/train-search" target="_blank" rel="noopener" class="dest-action-link">
          🚆 IRCTC / Trains
        </a>
      ` : ''}
      <button type="button" id="btn-share-whatsapp" class="dest-action-link" style="background: linear-gradient(135deg, #25D366, #128C7E); color: white; border: none; cursor: pointer; font-weight: 700;">
        📲 Share to WhatsApp
      </button>
    `;

    const btnWhatsapp = document.getElementById('btn-share-whatsapp');
    if (btnWhatsapp) {
      btnWhatsapp.onclick = () => {
        let msg = `✈️ *AI TRIP PLANNER ITINERARY*\n`;
        msg += `📍 *Destination:* ${city}\n`;
        if (itinerary.start_date && itinerary.end_date) {
          msg += `📅 *Dates:* ${itinerary.start_date} to ${itinerary.end_date} (${days.length} Days)\n`;
        } else {
          msg += `📅 *Duration:* ${days.length} Days\n`;
        }
        msg += `💰 *Estimated Spend:* ${formatMoney(totalCost, activeCurrency)}\n`;
        if (itinerary.recommended_stay && itinerary.recommended_stay.name) {
          msg += `🏨 *Stay:* ${itinerary.recommended_stay.name}\n`;
        }
        msg += `\n*Daily Schedule Highlights:*\n`;
        days.slice(0, 4).forEach((d, idx) => {
          msg += `• *Day ${idx + 1} (${d.city || city}):* ${d.theme || 'Exploration'}\n`;
        });
        msg += `\nView complete itinerary online: ${window.location.origin}`;
        const waUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(msg)}`;
        window.open(waUrl, '_blank');
      };
    }

    // --- Render Interactive Leaflet Map ---
    const renderMap = () => {
      const mapContainer = document.getElementById('map-container');
      if (!mapContainer || typeof L === 'undefined') return;

      if (window.activeTripMap) {
        window.activeTripMap.remove();
        window.activeTripMap = null;
      }

      const cityCoords = {
        'tirupati': [13.6288, 79.4192],
        'vijayawada': [16.5062, 80.6480],
        'nellore': [14.4426, 79.9865],
        'nellor': [14.4426, 79.9865],
        'guntur': [16.3067, 80.4365],
        'visakhapatnam': [17.6868, 83.2185],
        'vizag': [17.6868, 83.2185],
        'goa': [15.2993, 74.1240],
        'north goa': [15.5494, 73.7535],
        'south goa': [15.1500, 73.9800],
        'old goa': [15.5033, 73.9114],
        'panjim': [15.4909, 73.8278],
        'gokarna': [14.5479, 74.3188],
        'mumbai': [19.0760, 72.8777],
        'bengaluru': [12.9716, 77.5946],
        'bangalore': [12.9716, 77.5946],
        'mysuru': [12.2958, 76.6394],
        'mysore': [12.2958, 76.6394],
        'hyderabad': [17.3850, 78.4867],
        'chennai': [13.0827, 80.2707],
        'delhi': [28.6139, 77.2090],
        'munnar': [10.0889, 77.0595],
        'kochi': [9.9312, 76.2673],
        'jaipur': [26.9124, 75.7873],
        'udaipur': [24.5854, 73.7125],
        'varanasi': [25.3176, 82.9739],
        'rishikesh': [30.0869, 78.2676],
        'manali': [32.2432, 77.1892],
        'shimla': [31.1048, 77.1734],
        'agra': [27.1767, 78.0081]
      };

      const getCityCoords = (cStr) => {
        if (!cStr) return [16.5062, 80.6480];
        const lower = String(cStr).toLowerCase().trim();
        if (cityCoords[lower]) return cityCoords[lower];
        for (const [k, pt] of Object.entries(cityCoords)) {
          if (lower.includes(k) || k.includes(lower)) return pt;
        }
        return [16.5062, 80.6480];
      };

      let baseCity = (city || 'vijayawada').toLowerCase().trim();
      let coords = getCityCoords(baseCity);

      const map = L.map('map-container').setView(coords, 10);
      window.activeTripMap = map;

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 18
      }).addTo(map);

      const routeLatLngs = [];

      const citiesList = itinerary.cities_visited || [city];
      citiesList.forEach((cName, idx) => {
        const cPos = getCityCoords(cName);
        routeLatLngs.push(cPos);

        L.marker(cPos).addTo(map)
          .bindPopup(`<b>📍 ${escapeHtml(cName)}</b><br>Destination Stop ${idx + 1} on your itinerary`)
          .openPopup();
      });

      if (routeLatLngs.length > 1) {
        const polyline = L.polyline(routeLatLngs, { color: '#38bdf8', weight: 4, opacity: 0.85, dashArray: '8, 8' }).addTo(map);
        map.fitBounds(polyline.getBounds(), { padding: [40, 40] });
      }
    };

    setTimeout(renderMap, 300);

    // Render Smart Geographic Route Corridor & Distance Breakdown
    function renderRouteCorridor(routeAnalysis, originCity) {
      const corridorCard = document.getElementById('route-corridor-card');
      const flowContainer = document.getElementById('corridor-flow-container');
      const badgeTotalDist = document.getElementById('badge-total-distance');
      const badgeSavedDist = document.getElementById('badge-distance-saved');
      const summaryText = document.getElementById('corridor-summary-text');
      const subtitle = document.getElementById('corridor-subtitle');

      if (!corridorCard || !flowContainer) return;

      if (!routeAnalysis || !routeAnalysis.legs || routeAnalysis.legs.length === 0) {
        corridorCard.style.display = 'none';
        return;
      }

      corridorCard.style.display = 'block';
      const startHub = routeAnalysis.start_hub || originCity || 'Departure Hub';
      if (subtitle) {
        subtitle.textContent = `Starts from ${escapeHtml(startHub)}, visiting nearest destinations first along the natural geographic corridor.`;
      }

      if (badgeTotalDist) {
        badgeTotalDist.textContent = `📏 ${Math.round(routeAnalysis.total_distance_km || 0)} km Total Corridor`;
      }
      if (badgeSavedDist) {
        const saved = Math.round(routeAnalysis.distance_saved_km || 0);
        if (saved > 0) {
          badgeSavedDist.textContent = `⚡ Saved ${saved} km & ~${routeAnalysis.time_saved_hours || 0} hrs Backtracking!`;
          badgeSavedDist.style.display = 'inline-block';
        } else {
          badgeSavedDist.textContent = `⚡ 0 km Backtracking (Optimal Route)`;
          badgeSavedDist.style.display = 'inline-block';
        }
      }

      flowContainer.innerHTML = '';
      const legs = routeAnalysis.legs || [];

      legs.forEach((leg, idx) => {
        const legRow = document.createElement('div');
        legRow.style.cssText = 'background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 12px 16px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px;';

        const isFirst = idx === 0;
        const isLast = idx === legs.length - 1;
        const badgeColor = isFirst ? '#10b981' : (isLast ? '#f59e0b' : '#38bdf8');
        const badgeBg = isFirst ? 'rgba(16, 185, 129, 0.15)' : (isLast ? 'rgba(245, 158, 11, 0.15)' : 'rgba(56, 189, 248, 0.15)');

        legRow.innerHTML = `
          <div style="display: flex; align-items: center; gap: 12px; min-width: 240px;">
            <div style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor}; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 0.85rem;">
              ${idx + 1}
            </div>
            <div>
              <div style="font-weight: 700; color: #f8fafc; font-size: 0.95rem;">
                ${escapeHtml(leg.from_city)} ➔ <span style="color: ${badgeColor};">${escapeHtml(leg.to_city)}</span>
              </div>
              <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 2px;">
                ${escapeHtml(leg.recommended_option || 'Transit Train / Bus')}
              </div>
            </div>
          </div>

          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="text-align: right;">
              <div style="font-weight: 800; color: #f8fafc; font-size: 0.92rem;">
                ${escapeHtml(leg.travel_duration || (Math.round(leg.distance_km) + ' km'))}
              </div>
              <div style="font-size: 0.75rem; color: #94a3b8;">
                ${Math.round(leg.distance_km || 0)} km • Est. ₹${Math.round(leg.estimated_cost_per_person || 150)}/person
              </div>
            </div>
            <span style="font-size: 0.72rem; font-weight: 700; padding: 4px 8px; border-radius: 6px; background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor};">
              ${escapeHtml(leg.proximity_badge || 'Corridor Leg')}
            </span>
          </div>
        `;
        flowContainer.appendChild(legRow);
      });

      if (summaryText) {
        summaryText.textContent = routeAnalysis.corridor_summary || '';
      }
    }

    renderRouteCorridor(itinerary.route_analysis, (currentJobData && currentJobData.origin) || originInput.value.trim());

    // Render Inter-City Transit Recommendation Card (Multi-Leg & Single-Leg Support)
    const intercityCard = document.getElementById('intercity-transit-card');

    if (intercityCard) {
      const it = itinerary.intercity_transport;
      const legs = (it && it.route_legs && Array.isArray(it.route_legs) && it.route_legs.length > 0) ? it.route_legs : null;

      if (legs && legs.length > 0) {
        const titleEl = intercityCard.querySelector('h3');
        if (titleEl) titleEl.textContent = `🚀 Inter-City Travel & Route Guide (${legs.length} Sequential Journey Legs)`;
        const originName = (currentJobData && currentJobData.origin) ? currentJobData.origin : 'Origin';
        const routeText = document.getElementById('intercity-route-text');
        if (routeText) routeText.textContent = `(${originName} ➔ ${(itinerary.cities_visited || [city]).join(' ➔ ')})`;

        let multiHTML = `
          <div style="font-size: 0.88rem; color: #94a3b8; margin-bottom: 14px;">
            ✨ Recommended sequential transit connections for every destination stop in your itinerary:
          </div>
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
            ${legs.map((leg, idx) => `
              <div style="background: rgba(15, 23, 42, 0.6); padding: 14px 16px; border-radius: 10px; border: 1px solid rgba(56, 189, 248, 0.3);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                  <span style="font-size: 0.85rem; font-weight: 700; color: #38bdf8; background: rgba(56,189,248,0.15); padding: 2px 10px; border-radius: 8px;">
                    Leg ${idx + 1}: ${escapeHtml(leg.route_title || (leg.from_city + ' ➔ ' + leg.to_city))}
                  </span>
                  <span style="font-size: 0.78rem; font-weight: 700; color: #4ade80;">${formatMoney(leg.estimated_cost_per_person || 150, activeCurrency)} / person</span>
                </div>
                <div style="font-weight: 700; color: #f8fafc; font-size: 0.95rem; margin-bottom: 4px;">
                  🚆 ${escapeHtml(leg.recommended_option || 'Intercity Express Transit')}
                </div>
                <div style="font-size: 0.8rem; color: #cbd5e1; margin-bottom: 6px;">
                  ⏱️ <strong>Duration:</strong> ${escapeHtml(leg.travel_duration || '3 hrs')}
                </div>
                <div style="font-size: 0.82rem; color: #94a3b8; line-height: 1.4;">
                  ${escapeHtml(leg.why_recommended || '')}
                </div>
                <div style="font-size: 0.78rem; color: #38bdf8; margin-top: 6px; background: rgba(56,189,248,0.08); padding: 6px 8px; border-radius: 6px;">
                  🚏 <strong>Station Connection:</strong> ${escapeHtml(leg.local_connect_tips || 'Prepaid auto or cab to hotel.')}
                </div>
                <div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px;">
                  <a href="https://www.confirmtkt.com/rbooking-d/trains/from/${encodeURIComponent(leg.from_city)}/to/${encodeURIComponent(leg.to_city)}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.74rem; color: #38bdf8; text-decoration: none; background: rgba(56, 189, 248, 0.12); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(56, 189, 248, 0.3);">
                    <span>🚆 Check Trains (ConfirmTkt) ↗</span>
                  </a>
                  <a href="https://www.redbus.in/bus-tickets/${encodeURIComponent(leg.from_city)}-to-${encodeURIComponent(leg.to_city)}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.74rem; color: #f87171; text-decoration: none; background: rgba(239, 68, 68, 0.12); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(239, 68, 68, 0.3);">
                    <span>🚌 Check Buses (RedBus) ↗</span>
                  </a>
                  <a href="https://www.google.com/travel/flights?q=flights%20from%20${encodeURIComponent(leg.from_city)}%20to%20${encodeURIComponent(leg.to_city)}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.74rem; color: #a78bfa; text-decoration: none; background: rgba(168, 85, 247, 0.12); padding: 4px 8px; border-radius: 6px; border: 1px solid rgba(168, 85, 247, 0.3);">
                    <span>✈️ Compare Flights ↗</span>
                  </a>
                </div>
              </div>
            `).join('')}
          </div>
        `;

        // Update body or container
        const optionText = document.getElementById('intercity-option-text');
        if (optionText) {
          const parentGrid = optionText.closest('.metric-card-body') || intercityCard;
          parentGrid.innerHTML = multiHTML;
        } else {
          intercityCard.innerHTML = `
            <div class="metric-card-header">
              <h3 style="margin: 0; font-size: 1.1rem; color: #f8fafc;">🚀 Inter-City Travel & Route Guide (${legs.length} Sequential Journey Legs)</h3>
            </div>
            <div style="padding: 16px;">${multiHTML}</div>
          `;
        }
        intercityCard.style.display = 'block';
      } else if (it && (it.recommended_option || it.mode)) {
        const originName = (currentJobData && currentJobData.origin) ? currentJobData.origin : '';
        const routeText = document.getElementById('intercity-route-text');
        const modeBadge = document.getElementById('intercity-mode-badge');
        const optionText = document.getElementById('intercity-option-text');
        const costText = document.getElementById('intercity-cost-text');
        const durationText = document.getElementById('intercity-duration-text');
        const whyText = document.getElementById('intercity-why-text');
        const connectText = document.getElementById('intercity-connect-text');

        let actualMode = (it.mode || 'Transit').trim();
        if (it.recommended_option && /flight|indigo|air india|akasa|spicejet/i.test(it.recommended_option)) {
          actualMode = 'Flight';
        } else if (it.recommended_option && /train|express|vande bharat|shatabdi|superfast|irctc/i.test(it.recommended_option)) {
          actualMode = 'Train';
        } else if (it.recommended_option && /bus|volvo|ksrtc|apsrtc|redbus/i.test(it.recommended_option)) {
          actualMode = 'Bus';
        }
        const modeIcon = actualMode.toLowerCase() === 'flight' ? '✈️' : (actualMode.toLowerCase() === 'bus' ? '🚌' : '🚆');

        if (routeText) routeText.textContent = originName ? `(${originName} ➔ ${city})` : `(to ${city})`;
        if (modeBadge) modeBadge.textContent = `${modeIcon} ${actualMode} Recommended`;
        if (optionText) optionText.textContent = it.recommended_option || 'Direct Route Options';
        if (costText) costText.textContent = it.estimated_cost_per_person ? formatMoney(it.estimated_cost_per_person, activeCurrency) + " / person" : 'Varies by class';
        if (durationText) durationText.textContent = it.travel_duration || 'Standard Transit Time';
        if (whyText) whyText.innerHTML = `<strong>Why Recommended:</strong> ${escapeHtml(it.why_recommended || '')}`;
        if (connectText) connectText.innerHTML = `<strong>🚏 Arrival & Hotel Connection:</strong> ${escapeHtml(it.local_connect_tips || 'Take local app-cab or station prepaid auto to your accommodation.')}`;

        intercityCard.style.display = 'block';
      } else {
        intercityCard.style.display = 'none';
      }
    }

    // Budget Balance calculation
    const remaining = userBudget - totalCost;
    if (remaining >= 0) {
      budgetRatioVal.textContent = `${formatMoney(remaining, activeCurrency)} left`;
      budgetRatioVal.className = 'metric-value highlight';
      budgetRatioVal.style.color = '#4ade80';
    } else {
      budgetRatioVal.textContent = `${formatMoney(Math.abs(remaining), activeCurrency)} over`;
      budgetRatioVal.className = 'metric-value';
      budgetRatioVal.style.color = '#f87171';

      if (!itinerary.budget_alert && bBanner && bText) {
        bText.textContent = `⚠️ Estimated trip cost (${formatMoney(totalCost, activeCurrency)}) exceeds your target budget (${formatMoney(userBudget, activeCurrency)}) by ${formatMoney(Math.abs(remaining), activeCurrency)}.`;
        bBanner.style.display = 'block';
      }
    }

    // Render Highlights: Food
    foodHighlightList.innerHTML = '';
    // Gather food items from day descriptions or guide
    const foodKeywords = [];
    days.forEach(d => {
      const texts = [d.morning, d.afternoon, d.evening, d.night].filter(Boolean).join(' ');
      const matches = texts.match(/(?:try|eat|dinner at|lunch at|snack on|delicacy|taste)\s+([^.,;]+)/gi);
      if (matches) {
        matches.forEach(m => foodKeywords.push(m.trim()));
      }
    });

    if (foodKeywords.length > 0) {
      foodKeywords.slice(0, 4).forEach(item => {
        const li = document.createElement('li');
        li.textContent = item.replace(/^(try|taste|eat)\s+/i, '');
        foodHighlightList.appendChild(li);
      });
    } else {
      const defaultFoods = currentMode === 'domestic' 
        ? ['Iconic Regional Thali & Local Curries', 'Authentic Street Food & Chaat', 'Local specialty breakfast & Chai/Coffee']
        : ['Signature local street delicacies', 'Authentic neighborhood dining gems', 'Traditional desserts and beverages'];
      defaultFoods.forEach(f => {
        const li = document.createElement('li');
        li.textContent = f;
        foodHighlightList.appendChild(li);
      });
    }

    // Render Highlights: Transit
    if (transportAdvice && transportAdvice.length > 0) {
      transitHighlightText.innerHTML = transportAdvice.map(t => `<p style="margin-bottom:0.4rem;">🚆 ${escapeHtml(t)}</p>`).join('');
    } else {
      transitHighlightText.innerHTML = currentMode === 'domestic'
        ? `<p>🚆 <strong>Recommended Transit</strong>: Check Vande Bharat / Superfast Express trains for scenic travel, or book app-cabs/auto-rickshaws for short local city hops.</p>`
        : `<p>✈️ <strong>Recommended Transit</strong>: Book local metro day-passes or convenient airport transfers for hassle-free city transit.</p>`;
    }

    // Render Days Timeline
    daysTimeline.innerHTML = '';
    days.forEach((day, idx) => {
      const dayNum = day.day_number || idx + 1;
      const theme = day.theme || `Day ${dayNum} Exploration`;
      const cost = (day.estimated_cost !== undefined && day.estimated_cost !== null)
        ? formatMoney(day.estimated_cost, activeCurrency)
        : '';

      // Render cost badge with tooltip if cost_breakdown exists
      const costItems = day.cost_breakdown || [];
      let costTagHtml = '';
      if (cost) {
        if (costItems.length > 0) {
          const breakdownHtml = costItems.map(item => `
            <div class="cost-tooltip-item">
              <span>${escapeHtml(item.item || item.name || 'Expense')}</span>
              <strong>${formatMoney(item.amount || 0, activeCurrency)}</strong>
            </div>
          `).join('');
          costTagHtml = `
            <div class="day-cost-wrapper">
              <span class="day-cost-tag" style="cursor:pointer;" title="Hover/tap for expense details">${cost} ℹ️</span>
              <div class="cost-tooltip">
                <div class="cost-tooltip-title">Day ${dayNum} Cost Breakdown</div>
                ${breakdownHtml}
              </div>
            </div>
          `;
        } else {
          costTagHtml = `<span class="day-cost-tag">${cost}</span>`;
        }
      }

      let displayCity = day.city || '';
      if (!displayCity && itinerary.cities_visited && Array.isArray(itinerary.cities_visited) && itinerary.cities_visited.length > 1) {
        const themeLower = (theme || '').toLowerCase();
        for (const c of itinerary.cities_visited) {
          const cLower = String(c).toLowerCase().trim();
          if (
            themeLower.includes(cLower) ||
            (cLower.startsWith('nellor') && themeLower.includes('nellor')) ||
            (cLower.startsWith('tirupati') && (themeLower.includes('tirupati') || themeLower.includes('tirumala'))) ||
            (cLower.startsWith('vijayawada') && (themeLower.includes('vijayawada') || themeLower.includes('bezawada'))) ||
            (cLower.startsWith('guntur') && themeLower.includes('guntur'))
          ) {
            displayCity = c;
            break;
          }
        }
      }

      const dayCard = document.createElement('div');
      dayCard.className = `day-card ${idx === 0 ? 'open' : ''}`;
      dayCard.innerHTML = `
        <div class="day-card-header">
          <div class="day-tag-title">
            <span class="day-num-pill">Day ${dayNum}</span>
            ${day.date ? `<span class="day-date-pill" style="background: rgba(168, 85, 247, 0.15); color: #c084fc; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; margin-left: 4px;">🗓️ ${escapeHtml(day.date)}</span>` : ''}
            <span class="day-theme-text" style="margin-left: 6px;">${escapeHtml(theme)}</span>
            ${displayCity ? `<span class="day-city-badge" style="background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 8px; border-radius: 4px; font-size: 0.78rem; font-weight: 600; margin-left: 6px;">📍 ${escapeHtml(displayCity)}</span>` : ''}
          </div>
          <div class="day-meta">
            ${costTagHtml}
            <span class="chevron-icon">▼</span>
          </div>
        </div>
        <div class="day-body">
          <div style="display: flex; justify-content: flex-end; margin-bottom: 10px;">
            <button type="button" class="btn-secondary" style="font-size: 0.78rem; padding: 4px 10px; background: rgba(37, 211, 102, 0.15); border: 1px solid rgba(37, 211, 102, 0.35); color: #4ade80; border-radius: 6px; cursor: pointer;" onclick="event.stopPropagation(); shareDayWhatsApp(${dayNum})">
              <span>💬 Send Day ${dayNum} to WhatsApp</span>
            </button>
          </div>
          ${day.weather_note ? `
            <div class="weather-note-banner" style="background: rgba(59, 130, 246, 0.12); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 6px; padding: 6px 12px; margin-bottom: 12px; font-size: 0.85rem; color: #60a5fa; display: flex; align-items: center; gap: 6px;">
              <span>🌦️</span> <strong>Weather Forecast Note:</strong> ${escapeHtml(day.weather_note)}
            </div>` : ''}
          ${day.morning ? `
            <div class="activity-block">
              <div class="time-slot-label">🌅 Morning (Breakfast / Fresh Up / Sightseeing)</div>
              <div class="activity-desc">${escapeHtml(day.morning)}</div>
              <div style="margin-top: 6px;">
                <a href="https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(day.morning.slice(0, 80) + ' ' + (displayCity || city))}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #38bdf8; text-decoration: none; background: rgba(56, 189, 248, 0.1); padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25);">
                  <span>🗺️ Directions in Google Maps ↗</span>
                </a>
              </div>
            </div>` : ''}
          ${day.afternoon ? `
            <div class="activity-block">
              <div class="time-slot-label">☀️ Afternoon (Regional Lunch & Sights)</div>
              <div class="activity-desc">${escapeHtml(day.afternoon)}</div>
              <div style="margin-top: 6px;">
                <a href="https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(day.afternoon.slice(0, 80) + ' ' + (displayCity || city))}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #38bdf8; text-decoration: none; background: rgba(56, 189, 248, 0.1); padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25);">
                  <span>🗺️ Directions in Google Maps ↗</span>
                </a>
              </div>
            </div>` : ''}
          ${day.evening ? `
            <div class="activity-block">
              <div class="time-slot-label">🌆 Evening (Tea / Snacks & Markets)</div>
              <div class="activity-desc">${escapeHtml(day.evening)}</div>
              <div style="margin-top: 6px;">
                <a href="https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(day.evening.slice(0, 80) + ' ' + (displayCity || city))}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 4px; font-size: 0.75rem; color: #38bdf8; text-decoration: none; background: rgba(56, 189, 248, 0.1); padding: 3px 8px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.25);">
                  <span>🗺️ Directions in Google Maps ↗</span>
                </a>
              </div>
            </div>` : ''}
          ${day.night ? `
            <div class="activity-block" style="border-left-color: #a855f7;">
              <div class="time-slot-label" style="color: #c084fc;">🌙 Night (Famous Dinner & Stroll)</div>
              <div class="activity-desc">${escapeHtml(day.night)}</div>
            </div>` : ''}
        </div>
      `;

      // Accordion toggle
      const header = dayCard.querySelector('.day-card-header');
      header.addEventListener('click', () => {
        dayCard.classList.toggle('open');
      });

      daysTimeline.appendChild(dayCard);
    });

    // Render Packing Suggestions with API Persistence
    const loadChecklist = async () => {
      let checklistItems = [];
      if (currentJobId) {
        try {
          const res = await fetch(`${API_BASE}/api/trip/${currentJobId}/checklist`);
          if (res.ok) {
            const data = await res.json();
            checklistItems = data.checklist || [];
          }
        } catch (e) {
          console.warn('Failed to fetch checklist state:', e);
        }
      }
      if (!checklistItems || checklistItems.length === 0) {
        checklistItems = (itinerary.packing_suggestions || []).map(item => ({ item, checked: false }));
      }
      packingGrid.innerHTML = '';
      checklistItems.forEach((itemObj, idx) => {
        const itemText = typeof itemObj === 'string' ? itemObj : itemObj.item;
        const isChecked = typeof itemObj === 'object' && itemObj.checked;
        const itemEl = document.createElement('label');
        itemEl.className = `checklist-item${isChecked ? ' done' : ''}`;
        itemEl.innerHTML = `
          <input type="checkbox" id="pack-${idx}" ${isChecked ? 'checked' : ''}>
          <span class="checklist-text">${escapeHtml(itemText)}</span>
        `;
        const checkbox = itemEl.querySelector('input');
        checkbox.addEventListener('change', async () => {
          itemEl.classList.toggle('done', checkbox.checked);
          if (currentJobId) {
            try {
              await fetch(`${API_BASE}/api/trip/${currentJobId}/checklist`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item: itemText, checked: checkbox.checked }),
              });
            } catch (err) {
              console.error('Failed to update checklist item:', err);
            }
          }
        });
        packingGrid.appendChild(itemEl);
      });
    };
    loadChecklist();

    // Render Emergency Info Card
    const emCard = document.getElementById('emergency-card');
    const emBadge = document.getElementById('emergency-grounded-badge');
    const emWarn = document.getElementById('emergency-warning-note');
    const emNat = document.getElementById('emergency-national-num');
    const emHospName = document.getElementById('emergency-hospital-name');
    const emHospArea = document.getElementById('emergency-hospital-area');
    const emPolName = document.getElementById('emergency-police-name');
    const emPolArea = document.getElementById('emergency-police-area');

    if (itinerary.emergency_info && emCard) {
      emCard.style.display = 'block';
      const em = itinerary.emergency_info;
      if (emNat) emNat.textContent = em.national_emergency_number || '112';

      if (em.nearest_hospital && em.nearest_hospital.name) {
        if (emHospName) emHospName.textContent = em.nearest_hospital.name;
        if (emHospArea) emHospArea.textContent = `📍 ${em.nearest_hospital.area || city}`;
      } else {
        if (emHospName) emHospName.textContent = 'City General Hospital';
        if (emHospArea) emHospArea.textContent = `📍 ${city}`;
      }

      if (em.nearest_police_station && em.nearest_police_station.name) {
        if (emPolName) emPolName.textContent = em.nearest_police_station.name;
        if (emPolArea) emPolArea.textContent = `📍 ${em.nearest_police_station.area || city}`;
      } else {
        if (emPolName) emPolName.textContent = 'Central Police Station';
        if (emPolArea) emPolArea.textContent = `📍 ${city}`;
      }

      // Wire Emergency Navigation Radar links
      const hospNav = document.getElementById('emergency-hospital-nav');
      const polNav = document.getElementById('emergency-police-nav');
      const hospQuery = (em.nearest_hospital && em.nearest_hospital.name) ? `${em.nearest_hospital.name} ${em.nearest_hospital.area || city}` : `hospital near ${city}`;
      const polQuery = (em.nearest_police_station && em.nearest_police_station.name) ? `${em.nearest_police_station.name} ${em.nearest_police_station.area || city}` : `police station near ${city}`;
      if (hospNav) hospNav.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(hospQuery)}`;
      if (polNav) polNav.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(polQuery)}`;

      if (em.grounded) {
        if (emBadge) { emBadge.style.display = 'inline-block'; emBadge.textContent = '✓ Verified Search Results'; }
        if (emWarn) emWarn.style.display = 'none';
      } else {
        if (emBadge) emBadge.style.display = 'none';
        if (emWarn) emWarn.style.display = 'block';
      }
    } else if (emCard) {
      emCard.style.display = 'none';
    }

    // Render Local Phrasebook Card
    const pbCard = document.getElementById('phrasebook-card');
    const pbBody = document.getElementById('phrasebook-table-body');
    if (itinerary.local_phrasebook && itinerary.local_phrasebook.length > 0 && pbCard && pbBody) {
      pbCard.style.display = 'block';
      pbBody.innerHTML = itinerary.local_phrasebook.map(entry => `
        <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
          <td style="padding: 8px 12px; font-weight: 600; color: #f8fafc;">${escapeHtml(entry.phrase_english)}</td>
          <td style="padding: 8px 12px; color: #38bdf8; font-weight: 700;">${escapeHtml(entry.phrase_local)}</td>
          <td style="padding: 8px 12px; color: #cbd5e1; font-style: italic;">"${escapeHtml(entry.pronunciation)}"</td>
        </tr>
      `).join('');
    } else if (pbCard) {
      pbCard.style.display = 'none';
    }

    // Render Local Festivals & Events Card
    const evCard = document.getElementById('events-card');
    const evBadge = document.getElementById('events-grounded-badge');
    const evWarn = document.getElementById('events-warning-note');
    const evContainer = document.getElementById('events-container');
    if (itinerary.local_events && itinerary.local_events.length > 0 && evCard && evContainer) {
      evCard.style.display = 'block';
      if (itinerary.events_grounded) {
        if (evBadge) { evBadge.style.display = 'inline-block'; evBadge.textContent = '✓ Verified Event Search'; }
        if (evWarn) evWarn.style.display = 'none';
      } else {
        if (evBadge) evBadge.style.display = 'none';
        if (evWarn) evWarn.style.display = 'block';
      }
      evContainer.innerHTML = itinerary.local_events.map(ev => `
        <div style="background: rgba(15, 23, 42, 0.6); padding: 14px 16px; border-radius: 8px; border: 1px solid rgba(245, 158, 11, 0.2);">
          <div style="font-weight: 700; color: #fbbf24; font-size: 0.95rem;">${escapeHtml(ev.name)}</div>
          <div style="font-size: 0.8rem; color: #94a3b8; font-weight: 600; margin: 2px 0 6px 0;">🗓️ ${escapeHtml(ev.date_or_period)}</div>
          <div style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.4;">${escapeHtml(ev.description)}</div>
        </div>
      `).join('');
    } else if (evCard) {
      evCard.style.display = 'none';
    }

    // Render Local Etiquette Guide Card
    const etCard = document.getElementById('etiquette-card');
    const etContainer = document.getElementById('etiquette-container');
    if (itinerary.local_etiquette && itinerary.local_etiquette.length > 0 && etCard && etContainer) {
      etCard.style.display = 'block';
      etContainer.innerHTML = itinerary.local_etiquette.map(item => `
        <div style="background: rgba(15, 23, 42, 0.6); padding: 14px 16px; border-radius: 8px; border: 1px solid rgba(168, 85, 247, 0.2);">
          <div style="font-weight: 700; color: #e9d5ff; font-size: 0.88rem; text-transform: uppercase; margin-bottom: 4px;">📍 ${escapeHtml(item.category)}</div>
          <div style="font-size: 0.86rem; color: #cbd5e1; line-height: 1.4;">${escapeHtml(item.advice)}</div>
        </div>
      `).join('');
    } else if (etCard) {
      etCard.style.display = 'none';
    }

    // Render Nearby Day Trips Card
    const dtCard = document.getElementById('daytrips-card');
    const dtContainer = document.getElementById('daytrips-container');
    if (itinerary.nearby_day_trips && itinerary.nearby_day_trips.length > 0 && dtCard && dtContainer) {
      dtCard.style.display = 'block';
      dtContainer.innerHTML = itinerary.nearby_day_trips.map(trip => `
        <div style="background: rgba(15, 23, 42, 0.6); padding: 14px 16px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.2);">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
            <div style="font-weight: 700; color: #6ee7b7; font-size: 0.95rem;">${escapeHtml(trip.name)}</div>
            <span style="font-size: 0.76rem; font-weight: 600; padding: 2px 8px; border-radius: 10px; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);">${escapeHtml(trip.distance_from_destination)}</span>
          </div>
          <div style="font-size: 0.85rem; color: #cbd5e1; line-height: 1.4; margin-top: 4px;">${escapeHtml(trip.why_visit)}</div>
        </div>
      `).join('');
    } else if (dtCard) {
      dtCard.style.display = 'none';
    }

    // Render Local City Commute & Vehicle Rental Options (Multi-City & City-Specific)
    const localCommuteCard = document.getElementById('local-commute-card');
    if (localCommuteCard) {
      const cityList = (itinerary.cities_visited && itinerary.cities_visited.length > 0) ? itinerary.cities_visited : [city];
      
      const cityCommuteDb = {
        'tirupati': {
          bike: '₹350 - ₹500 / day',
          bikeTip: 'Rentals available near Railway Station & Alipiri checkpost. Helmet mandatory.',
          auto: '₹400 - ₹700 / day',
          autoTip: 'Shared & private autos connect station, Alipiri, & Tirumala uphill buses.',
          bus: '₹30 - ₹80 / day',
          busTip: 'APSRTC Free & express buses frequent Alipiri & temple routes.',
          cab: '₹1,600 - ₹2,200 / day',
          cabTip: 'Prepaid AC cabs for temple tour (Kanipakam, Srikalahasti, Chandragiri).'
        },
        'vijayawada': {
          bike: '₹450 - ₹650 / day',
          bikeTip: 'Available near Junction Station & PNBS Bus Stand.',
          auto: '₹500 - ₹800 / day',
          autoTip: 'Ola, Uber & meter autos connect Kanaka Durga Temple, Prakasam Barrage & Undavalli.',
          bus: '₹50 - ₹100 / day',
          busTip: 'APSRTC Metro Express city buses cover Besant Road & Benz Circle.',
          cab: '₹1,800 - ₹2,500 / day',
          cabTip: 'Full day AC cab recommended for Amaravati & Mangalagiri trips.'
        },
        'nellore': {
          bike: '₹400 - ₹550 / day',
          bikeTip: 'Available near RTC Complex & Atmakur Bus Stand.',
          auto: '₹450 - ₹750 / day',
          autoTip: 'Local autos connect Ranganathaswamy Temple & Penna riverfront.',
          bus: '₹40 - ₹90 / day',
          busTip: 'Frequent RTC buses connecting city center to Mypadu Beach.',
          cab: '₹1,700 - ₹2,300 / day',
          cabTip: 'AC Sedan cab recommended for 25km scenic Mypadu Beach drive.'
        }
      };

      let commuteHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px;">
          <div style="display: flex; align-items: center; gap: 8px; font-weight: 700; color: #c084fc; font-size: 1.1rem;">
            <span>🚗</span> Local City Commute & Vehicle Rental Options (${cityList.length} Visited Cities)
          </div>
          <span style="font-size: 0.78rem; font-weight: 600; padding: 3px 10px; border-radius: 12px; background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3);">
            City-Specific Comparison
          </span>
        </div>
      `;

      cityList.forEach(cName => {
        const cKey = cName.toLowerCase().trim();
        const info = cityCommuteDb[cKey] || {
          bike: '₹400 - ₹600 / day',
          bikeTip: `Best for solo travelers exploring ${escapeHtml(cName)} market streets.`,
          auto: '₹500 - ₹800 / day',
          autoTip: `Point-to-point autos & app cabs connecting ${escapeHtml(cName)} sights.`,
          bus: '₹50 - ₹120 / day',
          busTip: `City bus pass for budget transit across ${escapeHtml(cName)}.`,
          cab: '₹1,800 - ₹2,500 / day',
          cabTip: `Full-day AC cab for relaxed family sightseeing in ${escapeHtml(cName)}.`
        };

        commuteHTML += `
          <div style="margin-bottom: 20px;">
            <div style="font-size: 0.95rem; font-weight: 700; color: #e9d5ff; margin-bottom: 10px; padding-bottom: 4px; border-bottom: 1px dashed rgba(168,85,247,0.3);">
              📍 City Local Commute Rates: <strong>${escapeHtml(cName)}</strong>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
              <div style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 10px; border: 1px solid rgba(168, 85, 247, 0.2);">
                <div style="font-weight: 700; color: #e9d5ff; font-size: 0.88rem; margin-bottom: 4px;">🛵 Scooter / Bike (${escapeHtml(cName)})</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #c084fc;">${info.bike}</div>
                <p style="font-size: 0.78rem; color: #cbd5e1; margin-top: 6px; line-height: 1.35;">${escapeHtml(info.bikeTip)}</p>
              </div>
              <div style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 10px; border: 1px solid rgba(168, 85, 247, 0.2);">
                <div style="font-weight: 700; color: #e9d5ff; font-size: 0.88rem; margin-bottom: 4px;">🛺 Auto / App Cabs (${escapeHtml(cName)})</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #c084fc;">${info.auto}</div>
                <p style="font-size: 0.78rem; color: #cbd5e1; margin-top: 6px; line-height: 1.35;">${escapeHtml(info.autoTip)}</p>
              </div>
              <div style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 10px; border: 1px solid rgba(168, 85, 247, 0.2);">
                <div style="font-weight: 700; color: #e9d5ff; font-size: 0.88rem; margin-bottom: 4px;">🚌 City Bus Pass (${escapeHtml(cName)})</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #c084fc;">${info.bus}</div>
                <p style="font-size: 0.78rem; color: #cbd5e1; margin-top: 6px; line-height: 1.35;">${escapeHtml(info.busTip)}</p>
              </div>
              <div style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: 10px; border: 1px solid rgba(168, 85, 247, 0.2);">
                <div style="font-weight: 700; color: #e9d5ff; font-size: 0.88rem; margin-bottom: 4px;">🚘 Full-Day Cab (${escapeHtml(cName)})</div>
                <div style="font-size: 1.05rem; font-weight: 800; color: #c084fc;">${info.cab}</div>
                <p style="font-size: 0.78rem; color: #cbd5e1; margin-top: 6px; line-height: 1.35;">${escapeHtml(info.cabTip)}</p>
              </div>
            </div>
          </div>
        `;
      });

      localCommuteCard.innerHTML = commuteHTML;
    }

    // Render Recommended Stay (Multi-City & Single-City Support)
    const stayCard = document.getElementById('stay-card');
    const stayTierBadge = document.getElementById('stay-tier-badge');
    const stayNameText = document.getElementById('stay-name-text');
    const stayPriceText = document.getElementById('stay-price-text');
    const stayAreaText = document.getElementById('stay-area-text');
    const stayWhyText = document.getElementById('stay-why-text');

    const recStays = itinerary.recommended_stays;
    const recStay = itinerary.recommended_stay;

    if (stayCard) {
      const stayBody = stayCard.querySelector('.stay-card-body');
      if (recStays && Array.isArray(recStays) && recStays.length > 1) {
        const titleEl = stayCard.querySelector('h3');
        if (titleEl) titleEl.textContent = 'Recommended Accommodation (Multi-City Stays for All Destinations)';
        if (stayBody) {
          stayBody.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px;">
              ${recStays.map(s => `
                <div style="background: rgba(15, 23, 42, 0.6); padding: 16px; border-radius: 10px; border: 1px solid rgba(56, 189, 248, 0.3);">
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span style="font-size: 0.8rem; font-weight: 700; color: #38bdf8; background: rgba(56,189,248,0.15); padding: 2px 8px; border-radius: 6px;">📍 ${escapeHtml(s.city || city)}</span>
                    <span style="font-size: 0.78rem; color: #4ade80; font-weight: 700;">${formatMoney(s.estimated_price_per_night || 800, activeCurrency)} / night</span>
                  </div>
                  <h4 style="font-size: 1.02rem; font-weight: 700; color: #f8fafc; margin: 6px 0 4px 0;">${escapeHtml(s.name)}</h4>
                  <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 6px;">${escapeHtml(s.address_or_area || 'Central Hub')}</div>
                  <p style="font-size: 0.82rem; color: #cbd5e1; margin: 0 0 8px 0; line-height: 1.4;">${escapeHtml(s.why_recommended || 'Comfortable budget accommodation.')}</p>
                  <a href="https://www.google.com/travel/hotels?q=${encodeURIComponent((s.name || 'Hotel') + ' ' + (s.city || city))}" target="_blank" rel="noopener noreferrer" style="display:inline-block; font-size:0.75rem; color:#38bdf8; text-decoration:none; background:rgba(56,189,248,0.1); padding:4px 10px; border-radius:6px; border:1px solid rgba(56,189,248,0.25);">🏨 Check Rates & Availability ↗</a>
                </div>
              `).join('')}
            </div>
          `;
        }
        stayCard.classList.remove('hidden');
      } else if (recStay) {
        if (stayTierBadge) stayTierBadge.textContent = recStay.category || 'Budget-Matched Stay';
        if (stayNameText) stayNameText.textContent = recStay.name || 'Top-Rated Accommodation';
        if (stayPriceText) stayPriceText.textContent = `${formatMoney(recStay.estimated_price_per_night || (userBudget * 0.25 / (itinerary.trip_length_days || 1)), activeCurrency)} / night`;
        if (stayAreaText) stayAreaText.textContent = `📍 ${recStay.address_or_area || (city + ' Central')}`;
        if (stayWhyText) stayWhyText.textContent = recStay.why_recommended || `Matches your budget tier perfectly while keeping you accessible to main sights.`;
        if (stayCard) stayCard.classList.remove('hidden');
      } else {
        let fallbackCat = userBudget <= 5000 ? 'Budget Hostel / Homestay' : (userBudget <= 25000 ? 'Comfort 3-Star Hotel' : 'Luxury 5-Star Hotel');
        let approxStayPrice = Math.round((userBudget * 0.28) / (itinerary.trip_length_days || 1));
        if (stayTierBadge) stayTierBadge.textContent = fallbackCat;
        if (stayNameText) stayNameText.textContent = `${city} Recommended ${fallbackCat}`;
        if (stayPriceText) stayPriceText.textContent = `${formatMoney(approxStayPrice, activeCurrency)} / night`;
        if (stayAreaText) stayAreaText.textContent = `📍 ${city} Prime Area`;
        if (stayWhyText) stayWhyText.textContent = `Carefully selected stay matched to your overall budget of ${formatMoney(userBudget, activeCurrency)}.`;
        if (stayCard) stayCard.classList.remove('hidden');
      }
    }

    // Render Smart Budget Upgrades (+₹2,000 to ₹3,000)
    const upgradeCard = document.getElementById('upgrade-card');
    const upgradeAmountBadge = document.getElementById('upgrade-amount-badge');
    const upgradeHotelText = document.getElementById('upgrade-hotel-text');
    const upgradeDiningText = document.getElementById('upgrade-dining-text');
    const upgradeAttractionText = document.getElementById('upgrade-attraction-text');
    const upgradeTipText = document.getElementById('upgrade-tip-text');

    const upgrades = itinerary.budget_upgrade_insights;
    const upgradeAmt = upgrades ? (upgrades.extra_amount || 2500) : 2500;
    const formattedUpgradeAmt = formatMoney(upgradeAmt, activeCurrency);

    if (upgradeAmountBadge) {
      upgradeAmountBadge.textContent = `+${formattedUpgradeAmt} Apply Budget Upgrade ⚡`;
      upgradeAmountBadge.onclick = () => {
        const curBudget = parseFloat(budgetInput.value) || userBudget || 5000;
        const newBudget = curBudget + upgradeAmt;
        budgetInput.value = newBudget;
        updateBudgetDisplay();
        budgetInput.scrollIntoView({ behavior: 'smooth', block: 'center' });
        budgetInput.focus();
        showToast(`⚡ Applied +${formattedUpgradeAmt} Budget Upgrade! Click "Plan Trip" to see your upgraded luxury itinerary.`);
      };
    }

    if (upgrades) {
      if (upgradeHotelText) upgradeHotelText.textContent = upgrades.hotel_upgrade || `Upgrade your stay to a higher-rated boutique hotel with free breakfast.`;
      if (upgradeDiningText) upgradeDiningText.textContent = upgrades.dining_upgrade || `Enjoy iconic rooftop dining & regional tasting platters.`;
      if (upgradeAttractionText) upgradeAttractionText.textContent = upgrades.attraction_upgrade || `Unlock entry to premium heritage light & sound shows and boat cruises.`;
      if (upgradeTipText) upgradeTipText.innerHTML = `<strong>Concierge Advice:</strong> ${escapeHtml(upgrades.summary_tip || `Spending an extra ${formattedUpgradeAmt} dramatically enhances your comfort and unlocks iconic highlights in ${city}!`)}`;
    } else {
      if (upgradeHotelText) upgradeHotelText.textContent = `Upgrade from basic rooms/dorms to a highly-rated 3-Star Boutique Hotel with AC & breakfast.`;
      if (upgradeDiningText) upgradeDiningText.textContent = `Experience signature dining at top-rated heritage restaurants and famous scenic view cafes in ${city}.`;
      if (upgradeAttractionText) upgradeAttractionText.textContent = `Add evening sunset boat cruise, sound & light show tickets, and private auto/cab transfers.`;
      if (upgradeTipText) upgradeTipText.innerHTML = `<strong>Concierge Advice:</strong> If you increase your budget by just <strong>+${formattedUpgradeAmt}</strong>, you unlock private rooms, iconic dining, and hassle-free transit in ${city}!`;
    }
    if (upgradeCard) upgradeCard.classList.remove('hidden');

    // Render Smart Trip Duration Extension Insights Card
    const extCard = document.getElementById('duration-extension-card');
    const extCardTitle = document.getElementById('ext-card-title');
    const extCardSubtitle = document.getElementById('ext-card-subtitle');
    const extApplyBtn = document.getElementById('ext-apply-btn');
    const extAttractionsText = document.getElementById('ext-attractions-text');
    const extFoodText = document.getElementById('ext-food-text');
    const extPaceText = document.getElementById('ext-pace-text');
    const extTipText = document.getElementById('ext-tip-text');

    const curLength = itinerary.trip_length_days || parseInt(daysSlider.value, 10) || 4;
    const extInsight = itinerary.duration_extension_insights;
    const addDays = extInsight ? (extInsight.suggested_extra_days || 2) : 2;
    const newLength = curLength + addDays;

    if (extCardTitle) extCardTitle.textContent = `Smart Trip Extension (Extend from ${curLength} Days ➔ ${newLength} Days)`;
    if (extCardSubtitle) extCardSubtitle.textContent = `Discover what extra sights, food gems, and relaxed pacing you unlock by adding +${addDays} days:`;
    if (extApplyBtn) {
      extApplyBtn.textContent = `+${addDays} Days Extension 🚀`;
      extApplyBtn.onclick = () => {
        daysSlider.value = newLength;
        daysBadge.textContent = `${newLength} Days`;
        syncDatesAndDuration('slider');
        daysSlider.scrollIntoView({ behavior: 'smooth', block: 'center' });
        showToast(`⚡ Trip extended to ${newLength} Days! Click "Plan Trip" to generate your expanded itinerary.`);
      };
    }

    if (extInsight) {
      if (extAttractionsText) extAttractionsText.textContent = extInsight.unlocked_attractions;
      if (extFoodText) extFoodText.textContent = extInsight.unlocked_food;
      if (extPaceText) extPaceText.textContent = extInsight.pace_benefit;
      if (extTipText) extTipText.innerHTML = `<strong>Concierge Recommendation:</strong> ${escapeHtml(extInsight.summary_tip)}`;
    } else {
      if (extAttractionsText) extAttractionsText.textContent = `Explore 4 additional iconic landmarks and hidden nature spots without rushing.`;
      if (extFoodText) extFoodText.textContent = `Savor signature thalis, authentic street food lanes, and famous regional dessert spots.`;
      if (extPaceText) extPaceText.textContent = `Reduces schedule stress from 4 rushed sights/day to a comfortable 2 sights/day with zero hurry.`;
      if (extTipText) extTipText.innerHTML = `<strong>Concierge Recommendation:</strong> Extending your trip by +${addDays} days transforms your holiday into a rich, memorable, and relaxed experience!`;
    }
    if (extCard) extCard.style.display = 'block';

    // Render Similar Travelers Also Visited Recommendations
    const loadRecommendations = async () => {
      const recsSection = document.getElementById('recommendations-section');
      const recsGrid = document.getElementById('recommendations-grid');
      if (!recsSection || !recsGrid || !currentJobId) return;

      try {
        const res = await fetch(`${API_BASE}/api/trip/${currentJobId}/recommendations`);
        if (res.ok) {
          const data = await res.json();
          const recs = data.recommendations || [];
          if (recs.length > 0) {
            recsGrid.innerHTML = '';
            recs.forEach(rec => {
              const card = document.createElement('div');
              card.className = 'recommendation-card';
              card.style.cssText = 'background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; padding: 15px; display: flex; flex-direction: column; justify-content: space-between;';
              
              const highlights = (rec.theme_highlights || []).slice(0, 2).map(h => `<li>${escapeHtml(h)}</li>`).join('');
              
              card.innerHTML = `
                <div>
                  <h4 style="margin: 0 0 5px 0; color: #38bdf8;">📍 ${escapeHtml(rec.destination_city)}, ${escapeHtml(rec.destination_country)}</h4>
                  <div style="font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px;">
                    ${rec.trip_length_days} Days | ${formatMoney(rec.total_estimated_cost, rec.currency)}
                  </div>
                  ${highlights ? `<ul style="margin: 5px 0 10px 18px; padding: 0; font-size: 0.82rem; color: #cbd5e1;">${highlights}</ul>` : ''}
                </div>
                <a href="/share.html?id=${rec.job_id}" target="_blank" rel="noopener" style="display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38bdf8; text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 0.85rem; font-weight: 600; text-align: center; margin-top: 10px;">
                  🔗 View Itinerary
                </a>
              `;
              recsGrid.appendChild(card);
            });
            recsSection.style.display = 'block';
          } else {
            recsSection.style.display = 'none';
          }
        }
      } catch (err) {
        console.warn('Failed to fetch recommendations:', err);
      }
    };
    loadRecommendations();

    // Show Results
    resultsSection.classList.add('active');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
  }

  // --- Export Actions ---
  const btnShareLink = document.getElementById('btn-copy-share-link');
  if (btnShareLink) {
    btnShareLink.addEventListener('click', () => {
      if (!currentJobId) {
        showToast('❌ No active trip found to share', 'error');
        return;
      }
      const shareUrl = `${window.location.origin}/share.html?id=${currentJobId}`;
      navigator.clipboard.writeText(shareUrl)
        .then(() => showToast('🔗 Shareable trip link copied to clipboard!'))
        .catch(() => showToast('❌ Failed to copy link to clipboard', 'error'));
    });
  }

  // --- Mobile Touch Tap Listener for Cost Breakdown Tooltips ---
  document.addEventListener('click', (e) => {
    const wrapper = e.target.closest('.day-cost-wrapper');
    if (wrapper) {
      // Toggle active class on tap for mobile screens
      const isAlreadyActive = wrapper.classList.contains('active');
      document.querySelectorAll('.day-cost-wrapper.active').forEach(w => w.classList.remove('active'));
      if (!isAlreadyActive) {
        wrapper.classList.add('active');
      }
    } else {
      document.querySelectorAll('.day-cost-wrapper.active').forEach(w => w.classList.remove('active'));
    }
  });

  document.getElementById('btn-copy-json').addEventListener('click', () => {
    if (!currentItinerary) return;
    navigator.clipboard.writeText(JSON.stringify(currentItinerary, null, 2))
      .then(() => showToast('📋 JSON copied to clipboard!'))
      .catch(() => showToast('❌ Failed to copy to clipboard'));
  });

  document.getElementById('btn-download-md').addEventListener('click', () => {
    if (!currentItinerary) return;
    const mdContent = generateMarkdown(currentItinerary);
    const blob = new Blob([mdContent], { type: 'text/markdown;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `itinerary-${(currentItinerary.destination_city || 'trip').toLowerCase().replace(/\s+/g, '-')}.md`;
    link.click();
    URL.revokeObjectURL(url);
    showToast('📥 Markdown itinerary downloaded!');
  });

  document.getElementById('btn-print').addEventListener('click', () => {
    window.print();
  });

  function generateMarkdown(itinerary) {
    const activeCurr = itinerary.currency || currentCurrency;
    let md = `# Trip Itinerary: ${itinerary.destination_city || 'Destination'} (${itinerary.destination_country || ''})\n\n`;
    md += `- **Duration**: ${itinerary.trip_length_days || 'N/A'} Days\n`;
    const totalCost = itinerary.total_estimated_cost || 0;
    md += `- **Estimated Total Cost**: ${formatMoney(totalCost, activeCurr)}\n\n`;
    md += `## Daily Schedule\n\n`;

    (itinerary.days || []).forEach(day => {
      md += `### Day ${day.day_number}: ${day.theme}\n`;
      const dayCost = day.estimated_cost;
      if (dayCost !== undefined && dayCost !== null) md += `*Estimated Daily Cost: ${formatMoney(dayCost, activeCurr)}*\n\n`;
      if (day.morning) md += `- **Morning**: ${day.morning}\n`;
      if (day.afternoon) md += `- **Afternoon**: ${day.afternoon}\n`;
      if (day.evening) md += `- **Evening**: ${day.evening}\n`;
      md += `\n`;
    });

    if (itinerary.packing_suggestions && itinerary.packing_suggestions.length > 0) {
      md += `## Packing Checklist\n\n`;
      itinerary.packing_suggestions.forEach(item => {
        md += `- [ ] ${item}\n`;
      });
    }

    return md;
  }

  // --- Voice Input (Speech-to-Text via Groq Whisper) ---
  const btnVoiceRecord = document.getElementById('btn-voice-record');
  const voiceStatusContainer = document.getElementById('voice-recording-status');
  const voiceStatusText = document.getElementById('voice-status-text');
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;

  if (btnVoiceRecord) {
    btnVoiceRecord.addEventListener('click', async () => {
      if (isRecording) {
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
          mediaRecorder.stop();
        }
        return;
      }

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        showToast('❌ Microphone recording is not supported in this browser.');
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        mediaRecorder = new MediaRecorder(stream);

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) audioChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
          stream.getTracks().forEach(t => t.stop());
          isRecording = false;
          btnVoiceRecord.textContent = '🎙️ Speak Preferences';
          btnVoiceRecord.style.background = 'linear-gradient(135deg, #059669, #0d9488)';

          if (voiceStatusText) voiceStatusText.textContent = 'Transcribing audio... Please wait.';
          showToast('⏳ Transcribing audio with Groq Whisper...');

          const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
          const formData = new FormData();
          formData.append('file', audioBlob, 'voice_input.webm');

          try {
            const res = await fetch(`${API_BASE}/api/transcribe-audio`, {
              method: 'POST',
              body: formData,
            });

            if (!res.ok) {
              const errData = await res.json().catch(() => ({}));
              throw new Error(errData.detail || 'Audio transcription failed');
            }

            const data = await res.json();
            if (data.transcript) {
              if (interestsInput.value.trim()) {
                interestsInput.value = `${interestsInput.value.trim()}, ${data.transcript}`;
              } else {
                interestsInput.value = data.transcript;
              }
              showToast('✅ Audio transcribed successfully!');
            } else {
              showToast('⚠️ No speech detected in audio clip.');
            }
          } catch (err) {
            console.error('Transcription error:', err);
            showToast(`❌ ${err.message || 'Voice transcription failed'}`);
          } finally {
            if (voiceStatusContainer) voiceStatusContainer.style.display = 'none';
          }
        };

        mediaRecorder.start();
        isRecording = true;
        btnVoiceRecord.textContent = '⏹️ Stop Recording';
        btnVoiceRecord.style.background = '#ef4444';
        if (voiceStatusText) voiceStatusText.textContent = 'Recording audio... Speak now. Click button again to stop.';
        if (voiceStatusContainer) voiceStatusContainer.style.display = 'flex';

      } catch (err) {
        console.error('Microphone permission error:', err);
        showToast('❌ Microphone permission denied or unavailable.');
        if (voiceStatusContainer) voiceStatusContainer.style.display = 'none';
      }
    });
  }

  // --- Photo-based Destination Inspiration ---
  const btnPhotoInspire = document.getElementById('btn-photo-inspire');
  const photoUploadInput = document.getElementById('photo-upload-input');
  const photoCard = document.getElementById('photo-inspire-card');
  const photoLoading = document.getElementById('photo-inspire-loading');
  const photoContent = document.getElementById('photo-inspire-content');
  const photoSceneText = document.getElementById('photo-scene-text');
  const photoReasoningText = document.getElementById('photo-reasoning-text');
  const photoChipsContainer = document.getElementById('photo-chips-container');

  if (btnPhotoInspire && photoUploadInput) {
    btnPhotoInspire.addEventListener('click', () => {
      photoUploadInput.click();
    });

    photoUploadInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      if (photoCard) photoCard.style.display = 'block';
      if (photoLoading) photoLoading.style.display = 'block';
      if (photoContent) photoContent.style.display = 'none';

      const formData = new FormData();
      formData.append('file', file);

      try {
        const res = await fetch(`${API_BASE}/api/inspire-from-photo`, {
          method: 'POST',
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || 'Photo analysis failed');
        }

        const data = await res.json();
        if (photoSceneText) photoSceneText.textContent = data.detected_scene || 'Scene analyzed';
        if (photoReasoningText) photoReasoningText.textContent = data.reasoning || '';

        if (photoChipsContainer) {
          photoChipsContainer.innerHTML = '';
          (data.suggested_destinations || []).forEach(city => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'interest-tag active';
            chip.style.cssText = 'background: #0284c7; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 0.85rem; font-weight: 600;';
            chip.textContent = `📍 ${city}`;
            chip.addEventListener('click', () => {
              if (citiesInput) {
                citiesInput.value = city;
                showToast(`✨ Destination pre-filled with ${city}!`);
              }
            });
            photoChipsContainer.appendChild(chip);
          });
        }

        if (photoLoading) photoLoading.style.display = 'none';
        if (photoContent) photoContent.style.display = 'block';
        showToast('📷 Photo analyzed successfully!');
      } catch (err) {
        console.error('Photo inspiration error:', err);
        showToast(`❌ ${err.message || 'Photo analysis failed'}`);
        if (photoCard) photoCard.style.display = 'none';
      } finally {
        photoUploadInput.value = '';
      }
    });
  }

  // --- Helper: Toast Notification ---
  function showToast(msg) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // --- PDF Export Handler ---
  const btnDownloadPdf = document.getElementById('btn-download-pdf');
  if (btnDownloadPdf) {
    btnDownloadPdf.addEventListener('click', () => {
      if (!currentJobId) {
        showToast('⚠️ No active trip itinerary found to export.');
        return;
      }
      window.open(`/api/trip/${currentJobId}/pdf`, '_blank');
      showToast('📄 Downloading printable PDF...');
    });
  }

  // --- Calendar .ics Export Handler ---
  const btnDownloadCalendar = document.getElementById('btn-download-calendar');
  if (btnDownloadCalendar) {
    btnDownloadCalendar.addEventListener('click', () => {
      if (!currentJobId) {
        showToast('⚠️ No active trip itinerary found to export.');
        return;
      }
      window.open(`/api/trip/${currentJobId}/calendar.ics`, '_blank');
      showToast('📅 Exporting calendar schedule (.ics)...');
    });
  }

  // --- Auth & Magic Link Modal Handlers ---
  const authHeaderWidget = document.getElementById('auth-header-widget');
  const loginModal = document.getElementById('login-modal');
  const loginForm = document.getElementById('login-form');
  const loginEmailInput = document.getElementById('login-email-input');
  const modalCloseBtn = document.getElementById('modal-close-btn');
  const loginMsg = document.getElementById('login-msg');

  async function checkAuth() {
    try {
      const res = await fetch('/api/auth/me');
      if (res.ok) {
        const data = await res.json();
        if (authHeaderWidget) {
          authHeaderWidget.innerHTML = `
            <a href="/my-trips" class="user-badge" style="text-decoration:none;">👤 ${escapeHtml(data.email)} (My Trips)</a>
            <button type="button" class="btn-auth" id="btn-logout" style="background:rgba(255,255,255,0.06);border-color:rgba(255,255,255,0.2);color:#94a3b8;">Logout</button>
          `;
          document.getElementById('btn-logout').addEventListener('click', async () => {
            await fetch('/api/auth/logout', { method: 'POST' });
            window.location.reload();
          });
        }
      } else {
        if (authHeaderWidget) {
          authHeaderWidget.innerHTML = `<button type="button" class="btn-auth" id="btn-login-modal">🔑 Login / Sign In</button>`;
          document.getElementById('btn-login-modal').addEventListener('click', () => {
            if (loginModal) loginModal.classList.remove('hidden');
          });
        }
      }
    } catch (e) {
      console.warn('Auth check error:', e);
    }
  }

  if (modalCloseBtn && loginModal) {
    modalCloseBtn.addEventListener('click', () => loginModal.classList.add('hidden'));
  }

  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = loginEmailInput.value.trim();
      if (!email) return;

      const submitBtn = document.getElementById('send-magic-link-btn');
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<span>Sending...</span>`;

      try {
        const res = await fetch('/api/auth/request-login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        const data = await res.json();
        if (res.ok) {
          loginMsg.className = 'login-msg';
          loginMsg.style.color = '#4ade80';
          if (data.verify_url) {
            loginMsg.innerHTML = `
              <div>${escapeHtml(data.message)}</div>
              <div style="margin-top:12px;">
                <a href="${escapeHtml(data.verify_url)}" class="btn primary small" style="display:inline-block; text-decoration:none; padding:8px 16px; border-radius:8px; font-weight:600; background:linear-gradient(135deg, #6366f1, #8b5cf6); color:#ffffff; box-shadow: 0 4px 12px rgba(99,102,241,0.4);">⚡ Click Here to Sign In Now</a>
              </div>
            `;
          } else {
            loginMsg.textContent = data.message;
          }
          loginMsg.classList.remove('hidden');
          showToast('📧 Magic login link dispatched!');
        } else {
          loginMsg.className = 'login-msg';
          loginMsg.style.color = '#f87171';
          loginMsg.textContent = data.error || data.detail || 'Failed to send login link.';
          loginMsg.classList.remove('hidden');
        }
      } catch (err) {
        console.error(err);
        showToast('❌ Error sending magic link');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<span>✨ Send Magic Login Link</span>`;
      }
    });
  }

  // --- Manual Token Verification Handler ---
  const verifyTokenForm = document.getElementById('verify-token-form');
  const tokenInput = document.getElementById('token-input');
  const tokenMsg = document.getElementById('token-msg');
  const verifyTokenBtn = document.getElementById('verify-token-btn');

  if (verifyTokenForm) {
    verifyTokenForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const rawToken = tokenInput.value.trim();
      if (!rawToken) return;

      verifyTokenBtn.disabled = true;
      verifyTokenBtn.innerHTML = `<span>Verifying...</span>`;

      try {
        const res = await fetch('/api/auth/verify-token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token: rawToken }),
        });
        const data = await res.json();
        if (res.ok) {
          tokenMsg.className = 'login-msg';
          tokenMsg.style.color = '#4ade80';
          tokenMsg.textContent = '✅ Token verified! Redirecting to My Trips...';
          tokenMsg.classList.remove('hidden');
          showToast('🎉 Logged in successfully!');
          setTimeout(() => {
            window.location.href = '/my-trips';
          }, 800);
        } else {
          tokenMsg.className = 'login-msg';
          tokenMsg.style.color = '#f87171';
          tokenMsg.textContent = data.detail || 'Invalid or expired token.';
          tokenMsg.classList.remove('hidden');
        }
      } catch (err) {
        console.error(err);
        showToast('❌ Failed to verify token');
      } finally {
        verifyTokenBtn.disabled = false;
        verifyTokenBtn.innerHTML = `<span>🔓 Verify & Sign In</span>`;
      }
    });
  }

  // Handle URL Query Params (e.g. auth_error, job_id)
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.has('auth_error')) {
    const err = urlParams.get('auth_error');
    if (err === 'invalid_or_expired_token') {
      showToast('❌ Invalid or expired magic link. Please request a new one.');
    } else if (err === 'login_required') {
      showToast('🔑 Please sign in to view your saved trips.');
    }
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  // Auto-load trip if job_id passed in URL or recent job stored
  let targetJobId = urlParams.get('job_id') || urlParams.get('id');
  if (!targetJobId) {
    try {
      targetJobId = localStorage.getItem('trip_planner_last_job_id');
    } catch (e) {}
  }
  if (targetJobId) {
    (async () => {
      try {
        showToast('🔄 Loading your itinerary...');
        const res = await fetch(`${API_BASE}/api/status/${targetJobId}`);
        if (res.ok) {
          const data = await res.json();
          if (data.status === 'complete' && data.result) {
            currentJobId = targetJobId;
            currentItinerary = data.result;
            finishAgentProgressAnimation();
            renderItinerary(data.result, data.result.total_estimated_cost, data.result.currency || 'INR');
            showToast('🎉 Loaded your AI trip itinerary!');
          } else if (data.status === 'running' || data.status === 'pending') {
            showToast('⏳ Trip generation in progress...');
          }
        }
      } catch (e) {
        console.warn('Failed to load initial job:', e);
      }
    })();
  }

  // Initial Presets & Auth Check Render
  renderPresets();
  updateBudgetDisplay();
  checkAuth();
});
