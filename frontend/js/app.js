/* ============================================================
   EvoAlpha — Main Application Logic
   ============================================================ */

(function () {
    'use strict';

    /* ----- DOM refs ----- */
    const $ = (sel) => document.querySelector(sel);
    const $$ = (sel) => document.querySelectorAll(sel);

    const heroSection = $('#hero');
    const pipelineSection = $('#pipeline-section');
    const evolutionView = $('#evolution-view');
    const resultsView = $('#results-view');

    const hypothesisInput = $('#hypothesis-input');
    const evolveBtn = $('#evolve-btn');
    const chips = $$('.chip');

    // Evolution view elements
    const evoHypText = $('#evo-hyp-text');
    const statGeneration = $('#stat-generation');
    const statStrategies = $('#stat-strategies');
    const statSharpe = $('#stat-sharpe');
    const statPnl = $('#stat-pnl');
    const evoLog = $('#evo-log');

    // Results view elements
    const resGens = $('#res-gens');
    const resTotal = $('#res-total');
    const resBestName = $('#res-best-name');
    const resBestSharpe = $('#res-best-sharpe');
    const resBestPnl = $('#res-best-pnl');
    const leaderboardBody = $('#leaderboard-body');
    const insightText = $('#insight-text');
    const newEvoBtn = $('#new-evolution-btn');
    const downloadBtn = $('#download-btn');

    /* ----- App State ----- */
    let currentPopulation = [];

    /* ----- DNA Helix instances ----- */
    let heroHelix = null;
    let evoHelix = null;

    function initHeroHelix() {
        const canvas = $('#dna-hero-canvas');
        heroHelix = new DNAHelix(canvas, {
            amplitude: Math.min(window.innerWidth * 0.15, 140),
            nodeCount: 35,
            speed: 0.012,
            nodeRadius: 2.5,
            glowIntensity: 8,
        });
        heroHelix.start();
    }

    function initEvoHelix() {
        const canvas = $('#dna-evo-canvas');
        evoHelix = new DNAHelix(canvas, {
            amplitude: Math.min(window.innerWidth * 0.12, 120),
            nodeCount: 28,
            speed: 0.03,
            nodeRadius: 3.5,
            glowIntensity: 14,
        });
        evoHelix.setMode('evolving');
        evoHelix.start();
    }

    /* ----- Input handling ----- */
    hypothesisInput.addEventListener('input', () => {
        evolveBtn.disabled = hypothesisInput.value.trim().length < 5;
    });

    hypothesisInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !evolveBtn.disabled) {
            startEvolution(hypothesisInput.value.trim());
        }
    });

    evolveBtn.addEventListener('click', () => {
        if (!evolveBtn.disabled) {
            startEvolution(hypothesisInput.value.trim());
        }
    });

    chips.forEach(chip => {
        chip.addEventListener('click', () => {
            const query = chip.dataset.query;
            hypothesisInput.value = query;
            evolveBtn.disabled = false;
            hypothesisInput.focus();
        });
    });

    if (newEvoBtn) {
        newEvoBtn.addEventListener('click', resetToHome);
    }
    
    if (downloadBtn) {
        downloadBtn.addEventListener('click', downloadStrategies);
    }

    /* ----- Strategy generation and parsing now handled by backend ----- */

    /* ----- Log helper ----- */
    function addLog(text, type = 'normal') {
        const entry = document.createElement('div');
        entry.className = 'log-entry';
        const now = new Date();
        const time = now.toLocaleTimeString('en-US', { hour12: false });
        const colorClass = type === 'success' ? 'log-success' : type === 'highlight' ? 'log-highlight' : type === 'warning' ? 'log-warning' : '';
        entry.innerHTML = `<span class="log-time">[${time}]</span> <span class="${colorClass}">${text}</span>`;
        evoLog.appendChild(entry);
        evoLog.scrollTop = evoLog.scrollHeight;
    }

    /* ----- Phase management ----- */
    function setPhase(phaseId, state) {
        const el = $(`#${phaseId}`);
        if (!el) return;
        el.classList.remove('active', 'done');
        if (state) el.classList.add(state);

        // Update connector lines too
        const phases = ['phase-parse', 'phase-load', 'phase-generate', 'phase-evolve', 'phase-explain'];
        const idx = phases.indexOf(phaseId);
        if (idx > 0 && state === 'done') {
            // Mark previous connector as done
            const lines = $$('.phase-line');
            if (lines[idx - 1]) lines[idx - 1].classList.add('done');
        }
    }

    function clearPhases() {
        $$('.phase-item').forEach(el => el.classList.remove('active', 'done'));
        $$('.phase-line').forEach(el => el.classList.remove('done'));
    }

    /* ----- Delay helper ----- */
    function wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /* ----- Main evolution orchestration (real backend via SSE) ----- */
    async function startEvolution(hypothesis) {
        // Transition to evolution view
        heroSection.classList.add('hidden');
        pipelineSection.classList.add('hidden');
        resultsView.classList.add('hidden');
        evolutionView.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Set hypothesis text
        evoHypText.textContent = `"${hypothesis}"`;

        // Clear previous state
        evoLog.innerHTML = '';
        clearPhases();
        statGeneration.textContent = '0';
        statStrategies.textContent = '0';
        statSharpe.textContent = '—';
        statPnl.textContent = '—';

        // Start evolution DNA animation
        if (evoHelix) evoHelix.destroy();
        initEvoHelix();

        // Track generation count for DNA animation
        let genCount = 0;

        // Connect to SSE endpoint
        const url = `/api/evolve?hypothesis=${encodeURIComponent(hypothesis)}`;
        const eventSource = new EventSource(url);

        eventSource.addEventListener('log', (e) => {
            const data = JSON.parse(e.data);
            addLog(data.text, data.type || 'normal');
        });

        eventSource.addEventListener('phase', (e) => {
            const data = JSON.parse(e.data);
            setPhase(data.id, data.state);
        });

        eventSource.addEventListener('stats', (e) => {
            const data = JSON.parse(e.data);
            if (data.generation !== undefined) statGeneration.textContent = data.generation;
            if (data.strategies !== undefined) statStrategies.textContent = data.strategies;
            if (data.sharpe !== undefined) statSharpe.textContent = data.sharpe.toFixed(2);
            if (data.pnl !== undefined) statPnl.textContent = `${(data.pnl * 100).toFixed(2)}%`;
        });

        eventSource.addEventListener('generation', (e) => {
            genCount++;
            // Trigger DNA mutation animation every few generations
            if (genCount % 2 === 0 && evoHelix) {
                evoHelix.setMode('mutating');
            }
        });

        eventSource.addEventListener('results', (e) => {
            const data = JSON.parse(e.data);
            eventSource.close();

            if (evoHelix) evoHelix.setMode('complete');

            // Show results with real backend data
            showResults(data);
        });

        eventSource.addEventListener('error', (e) => {
            // SSE error event (could be connection error or server-sent error)
            if (e.data) {
                const data = JSON.parse(e.data);
                addLog(`Error: ${data.message}`, 'warning');
            }
            eventSource.close();
        });

        eventSource.onerror = () => {
            // Connection-level error
            eventSource.close();
        };
    }

    /* ----- Results rendering (real backend data) ----- */
    function showResults(data) {
        const leaderboard = data.leaderboard || [];
        const best = data.best;
        const explanation = data.explanation || '';

        currentPopulation = leaderboard;
        evolutionView.classList.add('hidden');
        resultsView.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        if (evoHelix) evoHelix.destroy();

        resGens.textContent = data.generations || 0;
        resTotal.textContent = data.total_evaluated || 0;

        if (best) {
            resBestName.textContent = best.description || `${best.feature} → ${best.transform}(${best.window})`;
            resBestSharpe.textContent = best.sharpe.toFixed(3);
            resBestPnl.textContent = `${(best.slippage_pnl * 100).toFixed(2)}%`;
        }

        // Build leaderboard table
        leaderboardBody.innerHTML = '';
        leaderboard.forEach((s, i) => {
            const tr = document.createElement('tr');
            if (i === 0) tr.className = 'rank-1';
            const sharpeClass = s.sharpe > 0 ? 'positive' : 'negative';
            const pnlClass = s.pnl > 0 ? 'positive' : 'negative';
            const adjPnlClass = s.slippage_pnl > 0 ? 'positive' : 'negative';
            const ddClass = s.max_drawdown < 0 ? 'negative' : '';
            tr.innerHTML = `
                <td>#${i + 1}</td>
                <td>${s.window}</td>
                <td>${s.lag}</td>
                <td class="${sharpeClass}">${s.sharpe.toFixed(3)}</td>
                <td class="${pnlClass}">${(s.pnl * 100).toFixed(2)}%</td>
                <td class="${adjPnlClass}">${(s.slippage_pnl * 100).toFixed(2)}%</td>
                <td>${s.num_trades !== undefined ? s.num_trades : '—'}</td>
                <td class="${ddClass}">${s.max_drawdown !== undefined ? (s.max_drawdown * 100).toFixed(2) + '%' : '—'}</td>
            `;
            tr.style.animation = `fadeInUp 0.4s var(--ease-out) ${i * 0.1}s both`;
            leaderboardBody.appendChild(tr);
        });

        // Show AI-generated explanation from the backend
        if (explanation) {
            insightText.innerHTML = explanation.replace(/\n/g, '<br>');
        } else if (best) {
            insightText.textContent = `Best strategy: ${best.description} | Sharpe: ${best.sharpe.toFixed(3)} | PnL: ${(best.slippage_pnl * 100).toFixed(2)}% (after slippage)`;
        }
    }

    /* ----- Reset to home ----- */
    function resetToHome() {
        resultsView.classList.add('hidden');
        evolutionView.classList.add('hidden');
        heroSection.classList.remove('hidden');
        pipelineSection.classList.remove('hidden');
        hypothesisInput.value = '';
        evolveBtn.disabled = true;
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Restart hero helix
        if (heroHelix) heroHelix.destroy();
        initHeroHelix();
    }

    /* ----- Download Strategies -> CSV ----- */
    function downloadStrategies() {
        if (!currentPopulation || currentPopulation.length === 0) return;

        const headers = ['Rank', 'ID', 'Feature', 'Transform', 'Window', 'Lag', 'Signal Type', 'Threshold', 'Sharpe Ratio', 'PnL', 'Adj PnL (Slippage)', 'Max Drawdown', 'Num Trades', 'Description'];
        const rows = currentPopulation.map((s, i) => [
            i + 1,
            s.strategy_id || '',
            s.feature,
            s.transform,
            s.window,
            s.lag,
            s.signal_type,
            (s.threshold !== undefined ? s.threshold.toFixed(2) : ''),
            s.sharpe.toFixed(4),
            (s.pnl * 100).toFixed(4) + '%',
            (s.slippage_pnl * 100).toFixed(4) + '%',
            s.max_drawdown !== undefined ? (s.max_drawdown * 100).toFixed(2) + '%' : '',
            s.num_trades || '',
            s.description || ''
        ]);

        const csvContent = [
            headers.join(','),
            ...rows.map(e => e.join(','))
        ].join('\n');

        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', 'alphalution_strategies.csv');
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    /* ----- Init ----- */
    function init() {
        initHeroHelix();

        // Nav scroll behavior
        let lastScroll = 0;
        const nav = $('#main-nav');
        window.addEventListener('scroll', () => {
            const current = window.scrollY;
            if (current > lastScroll && current > 80) {
                nav.classList.add('nav-hidden');
            } else {
                nav.classList.remove('nav-hidden');
            }
            lastScroll = current;
        });
    }

    // Start when DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
