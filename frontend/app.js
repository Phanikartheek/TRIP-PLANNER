/**
 * AI Trip Planner - Frontend Controller
 * Supports India Domestic & International modes, currency switching (INR, USD, EUR),
 * dynamic presets, food/travel filters, and multi-agent execution with rich rendering.
 */

document.addEventListener('DOMContentLoaded', () => {
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

  // State Management
  let currentMode = 'domestic'; // 'domestic' | 'international'
  let currentCurrency = 'INR'; // 'INR' | 'USD' | 'EUR'
  let currentItinerary = null;
  let currentJobId = null;
  let progressInterval = null;

  // Currency Symbols & Configurations
  const CURRENCY_SYMBOLS = {
    INR: '₹',
    USD: '$',
    EUR: '€',
  };

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

  function formatMoney(amount, currencyCode = currentCurrency) {
    const sym = CURRENCY_SYMBOLS[currencyCode] || currencyCode;
    const num = Math.round(amount || 0);
    return `${sym}${num.toLocaleString()}`;
  }

  function updateBudgetDisplay() {
    const val = Number(budgetInput.value) || 0;
    budgetBadge.textContent = formatMoney(val, currentCurrency);
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

  // --- Slider Sync Handlers ---
  daysSlider.addEventListener('input', (e) => {
    daysBadge.textContent = `${e.target.value} Days`;
  });

  budgetInput.addEventListener('input', () => {
    updateBudgetDisplay();
  });

  // --- Form Submit & CrewAI Kickoff ---
  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const payload = {
      origin: originInput.value.trim(),
      cities: citiesInput.value.trim(),
      interests: interestsInput.value.trim(),
      trip_length: parseInt(daysSlider.value, 10),
      budget: parseFloat(budgetInput.value),
      currency: currentCurrency,
      travel_mode: currentMode,
      food_preference: getSelectedFood(),
      travel_style: travelStyleSelect.value,
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

      // Poll ${API_BASE}/api/status/{job_id} every 3 seconds until completed or failed
      let jobStatus = initData.status || 'pending';
      let itineraryData = null;

      while (jobStatus === 'pending' || jobStatus === 'running') {
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
          body: JSON.stringify({ job_id: currentJobId, feedback }),
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
          body: JSON.stringify({ job_id: currentJobId, question }),
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
      if (elapsed === 10) {
        setAgentState(agent1Card, 'completed', 'Destination Selected');
        setAgentState(agent2Card, 'running', 'Scouting Local Guide & Food');
      } else if (elapsed === 24) {
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

    const city = itinerary.destination_city || 'Featured Destination';
    const country = itinerary.destination_country || (currentMode === 'domestic' ? 'India' : '');
    const totalCost = itinerary.total_estimated_cost || 0;
    const days = itinerary.days || [];
    const packing = itinerary.packing_suggestions || [];
    const activeCurrency = itinerary.currency || currencyCode || currentCurrency;
    const transportAdvice = itinerary.local_transport_advice || [];

    destCity.textContent = city;
    destCountry.innerHTML = `📍 ${country ? country : 'India'}`;
    totalCostBadge.textContent = formatMoney(totalCost, activeCurrency);

    // Quick Action Links (Google Maps, IRCTC/Trains, Flights)
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
    `;

    // Budget Balance calculation
    const remaining = userBudget - totalCost;
    if (remaining >= 0) {
      budgetRatioVal.textContent = `${formatMoney(remaining, activeCurrency)} left`;
      budgetRatioVal.className = 'metric-value highlight';
    } else {
      budgetRatioVal.textContent = `${formatMoney(Math.abs(remaining), activeCurrency)} over`;
      budgetRatioVal.className = 'metric-value';
      budgetRatioVal.style.color = 'var(--accent-pink)';
    }

    // Render Highlights: Food
    foodHighlightList.innerHTML = '';
    // Gather food items from day descriptions or guide
    const foodKeywords = [];
    days.forEach(d => {
      const texts = [d.morning, d.afternoon, d.evening].filter(Boolean).join(' ');
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

      const dayCard = document.createElement('div');
      dayCard.className = `day-card ${idx === 0 ? 'open' : ''}`;
      dayCard.innerHTML = `
        <div class="day-card-header">
          <div class="day-tag-title">
            <span class="day-num-pill">Day ${dayNum}</span>
            <span class="day-theme-text">${escapeHtml(theme)}</span>
          </div>
          <div class="day-meta">
            ${cost ? `<span class="day-cost-tag">${cost}</span>` : ''}
            <span class="chevron-icon">▼</span>
          </div>
        </div>
        <div class="day-body">
          ${day.morning ? `
            <div class="activity-block">
              <div class="time-slot-label">🌅 Morning</div>
              <div class="activity-desc">${escapeHtml(day.morning)}</div>
            </div>` : ''}
          ${day.afternoon ? `
            <div class="activity-block">
              <div class="time-slot-label">☀️ Afternoon</div>
              <div class="activity-desc">${escapeHtml(day.afternoon)}</div>
            </div>` : ''}
          ${day.evening ? `
            <div class="activity-block">
              <div class="time-slot-label">🌙 Evening</div>
              <div class="activity-desc">${escapeHtml(day.evening)}</div>
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

    // Render Packing Suggestions
    packingGrid.innerHTML = '';
    packing.forEach((item, idx) => {
      const itemEl = document.createElement('label');
      itemEl.className = 'checklist-item';
      itemEl.innerHTML = `
        <input type="checkbox" id="pack-${idx}">
        <span class="checklist-text">${escapeHtml(item)}</span>
      `;
      const checkbox = itemEl.querySelector('input');
      checkbox.addEventListener('change', () => {
        itemEl.classList.toggle('done', checkbox.checked);
      });
      packingGrid.appendChild(itemEl);
    });

    // Show Results
    resultsSection.classList.add('active');
    resultsSection.scrollIntoView({ behavior: 'smooth' });
  }

  // --- Export Actions ---
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

  // Initial Presets Render
  renderPresets();
  updateBudgetDisplay();
});
